import os
import base64
import zipfile
import io
from datetime import datetime
from decimal import Decimal
from django.conf import settings
from .security_utils import get_master_key, descifrar_archivo
from .models import FielContratista, Nomina, Empleado

# Importaciones correctas para satcfdi v4.x
try:
    from satcfdi.models import Signer
    from satcfdi.pacs.sat import SAT, TipoDescargaMasivaTerceros, _SATRequest
    from satcfdi.cfdi import CFDI
    from lxml import etree
except ImportError:
    Signer = None
    SAT = None
    CFDI = None
    _SATRequest = object
    etree = None

class _SafeCFDIDescargaMasiva(_SATRequest):
    xml_name = 'descarga.xml'
    soap_url = 'https://cfdidescargamasiva.clouda.sat.gob.mx/DescargaMasivaService.svc'
    soap_action = 'http://DescargaMasivaTerceros.sat.gob.mx/IDescargaMasivaTercerosService/Descargar'
    solicitud_xpath = '{*}Body/{*}PeticionDescargaMasivaTercerosEntrada/{*}peticionDescarga'

    def process_response(self, response):
        header = response.find('.//{*}respuesta')
        paquete = response.find('.//{*}Paquete')

        res_dict = {}
        if header is not None:
            if 'CodEstatus' in header.attrib:
                res_dict['CodEstatus'] = header.attrib['CodEstatus']
            if 'Mensaje' in header.attrib:
                res_dict['Mensaje'] = header.attrib['Mensaje']

        zip_b64 = paquete.text if (paquete is not None and paquete.text) else None
        return res_dict, zip_b64

class SATService:
    def __init__(self, contratista):
        self.contratista = contratista
        self.fiel_record = FielContratista.objects.get(contratista=contratista)
        self.master_key = get_master_key()

    @staticmethod
    def obtener_info_certificado(cer_bytes):
        """Extrae RFC y vigencia de los bytes de un certificado .cer"""
        try:
            from satcfdi.models import Certificate
            from satcfdi.models.certificate import CertificateType
            cert = Certificate.load_certificate(cer_bytes)
            
            valido_hasta_raw = cert.certificate.get_notAfter().decode('ascii')
            valido_hasta = datetime.strptime(valido_hasta_raw, '%Y%m%d%H%M%SZ')
            
            es_fiel = False
            try:
                es_fiel = (cert.type == CertificateType.Fiel)
            except:
                es_fiel = cert.certificate.get_extension_count() >= 4

            return {
                'success': True,
                'rfc': str(cert.rfc),
                'nombre': cert.legal_name,
                'valido_hasta': valido_hasta,
                'serie': cert.certificate_number,
                'es_fiel': es_fiel
            }
        except Exception as e:
            return {'success': False, 'error': f"Error al leer certificado: {str(e)}"}

    def get_signer(self, password):
        if not Signer:
            raise Exception("Librería satcfdi no instalada correctamente.")
            
        cer_bytes = descifrar_archivo(self.fiel_record.certificado_cifrado, self.fiel_record.data_key_cifrada, self.master_key)
        key_bytes = descifrar_archivo(self.fiel_record.llave_privada_cifrada, self.fiel_record.data_key_cifrada, self.master_key)
        
        return Signer.load(certificate=cer_bytes, key=key_bytes, password=password)

    def solicitar_descarga(self, password, fecha_inicio, fecha_fin, estatus='vigente'):
        signer = self.get_signer(password)
        sat = SAT(signer=signer)
        res = sat.recover_comprobante_emitted_request(
            fecha_inicial=fecha_inicio,
            fecha_final=fecha_fin,
            rfc_emisor=self.contratista.rfc,
            tipo_comprobante='N',
            estado_comprobante='1' if estatus == 'vigente' else '0',
            tipo_solicitud=TipoDescargaMasivaTerceros.CFDI
        )
        if res.get('CodEstatus') == '5000':
            return res.get('IdSolicitud')
        else:
            raise Exception(f"SAT Error {res.get('CodEstatus')}: {res.get('Mensaje')}")

    def verificar_estatus(self, id_solicitud, password):
        signer = self.get_signer(password)
        sat = SAT(signer=signer)
        res = sat.recover_comprobante_status(id_solicitud=id_solicitud)
        return {
            'estado': str(res.get('EstadoSolicitud', '')),
            'codigo': res.get('CodEstatus'),
            'codigo_estado': res.get('CodigoEstadoSolicitud'),
            'numero_cfdis': res.get('NumeroCFDIs', 0),
            'mensaje': res.get('Mensaje', ''),
            'paquetes': res.get('IdsPaquetes', []) or []
        }

    def descargar_e_integrar(self, id_solicitud, paquetes, password, empresa_actual, sucursal_id=None, estatus_cfdi='vigente'):
        signer = self.get_signer(password)
        sat = SAT(signer=signer)
        count = 0
        all_files = []
        errores_paquetes = []
        for p_id in paquetes:
            try:
                req = _SafeCFDIDescargaMasiva(
                    signer=sat.signer,
                    arguments={
                        'RfcSolicitante': sat.signer.rfc,
                        'IdPaquete': p_id,
                    }
                )
                header, zip_b64 = sat._execute_req(req, needs_token_fn=sat._get_token_comprobante)
                if zip_b64:
                    zip_bytes = base64.b64decode(zip_b64)
                    c, f = self._procesar_zip_xml(zip_bytes, empresa_actual, sucursal_id, estatus_cfdi=estatus_cfdi)
                    count += c
                    all_files.extend(f)
                else:
                    msg = header.get('Mensaje', 'Sin contenido de paquete') if isinstance(header, dict) else ''
                    cod = header.get('CodEstatus', '') if isinstance(header, dict) else ''
                    errores_paquetes.append(f"Paquete {p_id}: {cod} {msg}")
            except Exception as e:
                import traceback
                print(f"Error al descargar paquete {p_id}:\n{traceback.format_exc()}")
                errores_paquetes.append(f"Paquete {p_id}: {str(e)}")
        return count, all_files, errores_paquetes

    def _procesar_zip_xml(self, zip_bytes, empresa_actual, sucursal_id, estatus_cfdi='vigente'):
        count = 0
        files_list = []
        try:
            with zipfile.ZipFile(io.BytesIO(zip_bytes)) as z:
                for xml_name in z.namelist():
                    files_list.append(xml_name)
                    if xml_name.lower().endswith('.xml') and not xml_name.endswith('/'):
                        try:
                            with z.open(xml_name) as f:
                                if SATService._parsear_y_guardar_xml(f.read(), empresa_actual, sucursal_id, estatus_cfdi=estatus_cfdi):
                                    count += 1
                        except Exception as xml_err:
                            print(f"Error procesando {xml_name}: {xml_err}")
        except Exception as zerr:
            print(f"Error abriendo ZIP descargado: {zerr}")
        return count, files_list

    @staticmethod
    def _parsear_y_guardar_xml(xml_content, empresa_actual, sucursal_id, estatus_cfdi='vigente'):
        """Lógica robusta para extraer datos de Nómina de un CFDI."""
        try:
            # Usamos lxml para búsqueda manual por si satcfdi no encuentra el nodo
            from lxml import etree
            root = etree.fromstring(xml_content)
            
            # Buscar el nodo Nomina en cualquier namespace
            nomina_node = root.find('.//{*}Nomina')
            if nomina_node is None: return False

            # Ahora usamos satcfdi para extraer datos de forma estructurada
            cfdi = CFDI.from_string(xml_content)
            
            # Extraer UUID (Obligatorio)
            timbre = root.find('.//{*}TimbreFiscalDigital')
            if timbre is None: return False
            uuid_val = timbre.get('UUID')
            if not uuid_val: return False

            # Datos de Emisor y Receptor
            emisor = root.find('.//{*}Emisor')
            receptor = root.find('.//{*}Receptor')
            
            rfc_emisor = emisor.get('Rfc', '') if emisor is not None else ''
            rfc_receptor = receptor.get('Rfc', '') if receptor is not None else ''
            nombre_receptor = receptor.get('Nombre', '') if receptor is not None else ''

            # Datos de Nómina
            def get_attr(node, attr, default=''):
                return node.get(attr, default)

            f_pago_str = get_attr(nomina_node, 'FechaPago')
            f_ini_str = get_attr(nomina_node, 'FechaInicialPago')
            f_fin_str = get_attr(nomina_node, 'FechaFinalPago')
            
            def parse_date(d_str):
                if not d_str: return None
                try:
                    return datetime.strptime(d_str[:10], '%Y-%m-%d').date()
                except:
                    return None
            
            f_pago = parse_date(f_pago_str)
            f_ini = parse_date(f_ini_str)
            f_fin = parse_date(f_fin_str)

            # Extraer fecha de emision y fecha de timbrado (certificacion)
            def parse_datetime(dt_str):
                if not dt_str: return None
                dt = None
                try:
                    dt = datetime.fromisoformat(dt_str)
                except:
                    for fmt in ('%Y-%m-%dT%H:%M:%S', '%Y-%m-%d %H:%M:%S'):
                        try:
                            dt = datetime.strptime(dt_str, fmt)
                            break
                        except:
                            continue
                if dt:
                    from django.utils import timezone
                    if timezone.is_naive(dt):
                        return timezone.make_aware(dt)
                    return dt
                return None

            fecha_emision_str = root.get('Fecha')
            fecha_cert_str = timbre.get('FechaTimbrado')
            fecha_emision = parse_datetime(fecha_emision_str)
            fecha_certificacion = parse_datetime(fecha_cert_str)

            dias = Decimal(get_attr(nomina_node, 'NumDiasPagados', '0'))
            
            # Los datos de CURP y NSS están en el nodo Receptor DENTRO del nodo Nomina
            nomina_receptor = nomina_node.find('.//{*}Receptor')
            curp_val = get_attr(nomina_receptor, 'Curp', '') if nomina_receptor is not None else ''
            nss_val = get_attr(nomina_receptor, 'NumSeguridadSocial', '') if nomina_receptor is not None else ''
            
            # Buscar empleado local
            empleado = Empleado.objects.filter(empresa=empresa_actual, rfc=rfc_receptor).first()

            # Inicializar variables de percepciones
            vacaciones_exento = Decimal('0.00')
            vacaciones_dignas_exento = Decimal('0.00')
            aguinaldo_exento = Decimal('0.00')
            
            sueldo_gravado = Decimal('0.00')
            vacaciones_gravado = Decimal('0.00')
            vacaciones_dignas_gravado = Decimal('0.00')
            aguinaldo_gravado = Decimal('0.00')

            percepciones_detalladas_dict = {}

            percepciones_node = nomina_node.find('.//{*}Percepciones')
            if percepciones_node is not None:
                for perc in percepciones_node.findall('.//{*}Percepcion'):
                    tipo = get_attr(perc, 'TipoPercepcion', '')
                    if not tipo:
                        continue
                    
                    try:
                        imp_gravado = Decimal(get_attr(perc, 'ImporteGravado', '0'))
                    except:
                        imp_gravado = Decimal('0.00')
                        
                    try:
                        imp_exento = Decimal(get_attr(perc, 'ImporteExento', '0'))
                    except:
                        imp_exento = Decimal('0.00')
                    
                    # Sum to our detailed dict
                    if tipo not in percepciones_detalladas_dict:
                        percepciones_detalladas_dict[tipo] = {'gravado': 0.0, 'exento': 0.0}
                    
                    percepciones_detalladas_dict[tipo]['gravado'] += float(imp_gravado)
                    percepciones_detalladas_dict[tipo]['exento'] += float(imp_exento)

                    # Clasificar las percepciones
                    concepto = get_attr(perc, 'Concepto', '').upper()
                    if "AGUINALDO" in concepto or tipo == '002':
                        aguinaldo_gravado += imp_gravado
                        aguinaldo_exento += imp_exento
                    elif "VACACIONES DIGNAS" in concepto:
                        vacaciones_dignas_gravado += imp_gravado
                        vacaciones_dignas_exento += imp_exento
                    elif "VACACIONES" in concepto or tipo == '021':
                        vacaciones_gravado += imp_gravado
                        vacaciones_exento += imp_exento
                    elif tipo == '001':
                        sueldo_gravado += imp_gravado

            # Validar que existan percepciones con importe mayor a 0 en el sistema
            total_percepciones_xml = sum(
                Decimal(str(v.get('gravado', 0))) + Decimal(str(v.get('exento', 0)))
                for v in percepciones_detalladas_dict.values()
            )
            total_legacy = (
                sueldo_gravado + vacaciones_exento + vacaciones_dignas_exento +
                aguinaldo_exento + vacaciones_gravado + vacaciones_dignas_gravado +
                aguinaldo_gravado
            )
            if max(total_percepciones_xml, total_legacy) <= Decimal('0.00'):
                # Omitir XMLs sin percepciones registradas o con importe en $0.00 (otros tipos de timbres/ajustes)
                return False

            deducciones_detalladas_dict = {}
            deducciones_node = nomina_node.find('.//{*}Deducciones')
            if deducciones_node is not None:
                for ded in deducciones_node.findall('.//{*}Deduccion'):
                    tipo = get_attr(ded, 'TipoDeduccion', '')
                    if not tipo:
                        continue
                    try:
                        imp_ded = Decimal(get_attr(ded, 'Importe', '0'))
                    except:
                        imp_ded = Decimal('0.00')
                    
                    if tipo not in deducciones_detalladas_dict:
                        deducciones_detalladas_dict[tipo] = {'importe': 0.0}
                    deducciones_detalladas_dict[tipo]['importe'] += float(imp_ded)

            try:
                sbc_val = Decimal(get_attr(nomina_receptor, 'SalarioBaseCotApor', '0') or '0')
            except:
                sbc_val = Decimal('0.00')

            try:
                sdi_val = Decimal(get_attr(nomina_receptor, 'SalarioDiarioIntegrado', '0') or '0')
            except:
                sdi_val = Decimal('0.00')

            defaults_nomina = {
                'sucursal_id': sucursal_id,
                'empleado': empleado,
                'estado': estatus_cfdi,
                'periodo': f"SAT Bimestre {(f_pago.month + 1) // 2} {f_pago.year}" if f_pago else "SAT S/F",
                'tipo_nomina': get_attr(nomina_node, 'TipoNomina', 'O'),
                'folio': get_attr(root, 'Folio'),
                'serie': get_attr(root, 'Serie'),
                'fecha_emision': fecha_emision,
                'fecha_certificacion': fecha_certificacion,
                'fecha_pago': f_pago,
                'fecha_inicial_pago': f_ini,
                'fecha_final_pago': f_fin,
                'dias_pagados': dias,
                'rfc': rfc_receptor,
                'curp': curp_val,
                'nss': nss_val,
                'nombre': nombre_receptor,
                'rfc_contratista': rfc_emisor,
                'sbc': sbc_val,
                'sdi': sdi_val,
                'sueldo_gravado': sueldo_gravado,
                'vacaciones_exento': vacaciones_exento,
                'vacaciones_dignas_exento': vacaciones_dignas_exento,
                'aguinaldo_exento': aguinaldo_exento,
                'vacaciones_gravado': vacaciones_gravado,
                'vacaciones_dignas_gravado': vacaciones_dignas_gravado,
                'aguinaldo_gravado': aguinaldo_gravado,
                'percepciones_detalladas': percepciones_detalladas_dict,
                'deducciones_detalladas': deducciones_detalladas_dict,
            }

            nomina_existente = Nomina.objects.filter(empresa=empresa_actual, uuid=uuid_val).first()
            if nomina_existente:
                for k, v in defaults_nomina.items():
                    setattr(nomina_existente, k, v)
                nomina_existente.save()
            else:
                Nomina.objects.create(
                    empresa=empresa_actual,
                    uuid=uuid_val,
                    **defaults_nomina
                )
            return True
        except Exception as e:
            import traceback
            print(f"Fallo en parseo de nómina: {e}\n{traceback.format_exc()}")
            return False
