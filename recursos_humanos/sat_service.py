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
    from satcfdi.pacs.sat import SAT, TipoDescargaMasivaTerceros
    from satcfdi.cfdi import CFDI
except ImportError:
    Signer = None
    SAT = None
    CFDI = None

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
            'estado': str(res.get('EstadoSolicitud')),
            'codigo': res.get('CodEstatus'),
            'paquetes': res.get('IdsPaquetes', [])
        }

    def descargar_e_integrar(self, id_solicitud, paquetes, password, empresa_actual, sucursal_id=None):
        signer = self.get_signer(password)
        sat = SAT(signer=signer)
        count = 0
        all_files = []
        for p_id in paquetes:
            _, zip_b64 = sat.recover_comprobante_download(id_paquete=p_id)
            if zip_b64:
                zip_bytes = base64.b64decode(zip_b64)
                c, f = self._procesar_zip_xml(zip_bytes, empresa_actual, sucursal_id)
                count += c
                all_files.extend(f)
        return count, all_files

    def _procesar_zip_xml(self, zip_bytes, empresa_actual, sucursal_id):
        count = 0
        files_list = []
        with zipfile.ZipFile(io.BytesIO(zip_bytes)) as z:
            for xml_name in z.namelist():
                files_list.append(xml_name)
                if xml_name.lower().endswith('.xml') and not xml_name.endswith('/'):
                    with z.open(xml_name) as f:
                        if self._parsear_y_guardar_xml(f.read(), empresa_actual, sucursal_id):
                            count += 1
        return count, files_list

    def _parsear_y_guardar_xml(self, xml_content, empresa_actual, sucursal_id):
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
            
            try:
                f_pago = datetime.strptime(f_pago_str, '%Y-%m-%d').date() if f_pago_str else None
                f_ini = datetime.strptime(f_ini_str, '%Y-%m-%d').date() if f_ini_str else None
                f_fin = datetime.strptime(f_fin_str, '%Y-%m-%d').date() if f_fin_str else None
            except:
                f_pago = f_ini = f_fin = None

            dias = Decimal(get_attr(nomina_node, 'NumDiasPagados', '0'))
            
            # Buscar empleado local
            empleado = Empleado.objects.filter(empresa=empresa_actual, rfc=rfc_receptor).first()

            Nomina.objects.update_or_create(
                empresa=empresa_actual,
                uuid=uuid_val,
                defaults={
                    'sucursal_id': sucursal_id,
                    'empleado': empleado,
                    'periodo': f"SAT {f_pago.strftime('%m/%Y')}" if f_pago else "SAT S/F",
                    'tipo_nomina': get_attr(nomina_node, 'TipoNomina', 'O'),
                    'folio': get_attr(root, 'Folio'),
                    'serie': get_attr(root, 'Serie'),
                    'fecha_pago': f_pago,
                    'fecha_inicial_pago': f_ini,
                    'fecha_final_pago': f_fin,
                    'dias_pagados': dias,
                    'rfc': rfc_receptor,
                    'nombre': nombre_receptor,
                    'rfc_contratista': rfc_emisor,
                    'sueldo_gravado': Decimal(get_attr(root, 'Total', '0')),
                }
            )
            return True
        except Exception as e:
            print(f"Fallo en parseo: {e}")
            return False
