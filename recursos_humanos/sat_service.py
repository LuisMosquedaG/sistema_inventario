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

    def get_signer(self, password):
        """Descifra los archivos FIEL en memoria y retorna el objeto Signer de satcfdi."""
        if not Signer:
            raise Exception("Librería satcfdi no instalada correctamente en el servidor.")
            
        cer_bytes = descifrar_archivo(self.fiel_record.certificado_cifrado, self.fiel_record.data_key_cifrada, self.master_key)
        key_bytes = descifrar_archivo(self.fiel_record.llave_privada_cifrada, self.fiel_record.data_key_cifrada, self.master_key)
        
        return Signer.load(
            certificate=cer_bytes,
            key=key_bytes,
            password=password
        )

    def solicitar_descarga(self, password, fecha_inicio, fecha_fin, estatus='vigente'):
        """Envía la solicitud real al Web Service del SAT usando satcfdi v4."""
        signer = self.get_signer(password)
        sat = SAT(signer=signer)
        
        # Mapeo de estatus para v4
        # En v4 se usan strings o enums. Si no se especifica, por defecto es CFDI.
        
        # Solicitar emitidos (Nóminas que la empresa emite)
        res = sat.recover_comprobante_emitted_request(
            fecha_inicial=fecha_inicio,
            fecha_final=fecha_fin,
            rfc_emisor=self.contratista.rfc, # RFC del Contratista
            rfc_receptor=None, # Queremos todos los receptores (empleados)
            tipo_comprobante='N', # N = Nómina
            estado_comprobante='1' if estatus == 'vigente' else '0', # 1=Vigente, 0=Cancelado
            tipo_solicitud=TipoDescargaMasivaTerceros.CFDI
        )
        
        if res.get('CodEstatus') == '5000':
            return res.get('IdSolicitud')
        else:
            raise Exception(f"SAT Error {res.get('CodEstatus')}: {res.get('Mensaje')}")

    def verificar_estatus(self, id_solicitud, password):
        """Consulta el estado de una solicitud previa."""
        signer = self.get_signer(password)
        sat = SAT(signer=signer)
        res = sat.recover_comprobante_status(id_solicitud=id_solicitud)
        
        # v4 retorna un dict con 'EstadoSolicitud', 'CodEstatus', 'IdsPaquetes'
        return {
            'estado': str(res.get('EstadoSolicitud')), # '3' = Terminada
            'codigo': res.get('CodEstatus'),
            'paquetes': res.get('IdsPaquetes', [])
        }

    def descargar_e_integrar(self, id_solicitud, paquetes, password, empresa_actual, sucursal_id=None):
        """Baja los paquetes ZIP, los procesa y crea los registros de nómina."""
        signer = self.get_signer(password)
        sat = SAT(signer=signer)
        
        count = 0
        for p_id in paquetes:
            # v4 retorna (info_dict, zip_content_bytes)
            _, zip_bytes = sat.recover_comprobante_download(id_paquete=p_id)
            if zip_bytes:
                count += self._procesar_zip_xml(zip_bytes, empresa_actual, sucursal_id)
            
        return count

    def _procesar_zip_xml(self, zip_bytes, empresa_actual, sucursal_id):
        """Extrae XMLs del ZIP y los parsea."""
        count = 0
        with zipfile.ZipFile(io.BytesIO(zip_bytes)) as z:
            for xml_name in z.namelist():
                if xml_name.endswith('.xml'):
                    with z.open(xml_name) as f:
                        xml_data = f.read()
                        if self._parsear_y_guardar_xml(xml_data, empresa_actual, sucursal_id):
                            count += 1
        return count

    def _parsear_y_guardar_xml(self, xml_content, empresa_actual, sucursal_id):
        """Lógica de extracción de datos del CFDI de Nómina."""
        try:
            cfdi = CFDI.from_string(xml_content)
            
            # Verificar si tiene complemento de nómina
            complemento = cfdi.get('Complemento')
            if not complemento or 'Nomina' not in complemento:
                return False

            nomina_data = complemento['Nomina']
            emisor = cfdi['Emisor']
            receptor = cfdi['Receptor']
            timbre = complemento['TimbreFiscalDigital']
            
            # Buscar empleado por RFC
            rfc_emp = receptor['Rfc']
            empleado = Empleado.objects.filter(empresa=empresa_actual, rfc=rfc_emp).first()
            
            # Crear o actualizar registro
            Nomina.objects.update_or_create(
                empresa=empresa_actual,
                uuid=timbre['UUID'],
                defaults={
                    'sucursal_id': sucursal_id,
                    'empleado': empleado,
                    'periodo': f"SAT {nomina_data['FechaPago'].strftime('%m/%Y')}",
                    'tipo_nomina': nomina_data['TipoNomina'],
                    'folio': cfdi.get('Folio', ''),
                    'serie': cfdi.get('Serie', ''),
                    'fecha_pago': nomina_data['FechaPago'],
                    'fecha_inicial_pago': nomina_data['FechaInicialPago'],
                    'fecha_final_pago': nomina_data['FechaFinalPago'],
                    'dias_pagados': Decimal(str(nomina_data['NumDiasPagados'])),
                    'rfc': rfc_emp,
                    'nombre': receptor['Nombre'],
                    'rfc_contratista': emisor['Rfc'],
                    'sueldo_gravado': Decimal(str(cfdi['Total'])), 
                }
            )
            return True
        except Exception as e:
            print(f"Error parseando XML: {e}")
            return False
