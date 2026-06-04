from django.contrib import admin
from .models import (
    Empleado, Contrato, Contratista, Beneficiario, Nomina,
    FielContratista, SolicitudDescargaSAT
)

class SolicitudDescargaSATAdmin(admin.ModelAdmin):
    list_display = ('id_solicitud', 'contratista', 'estado', 'fecha_creacion')
    list_filter = ('estado', 'empresa', 'contratista')
    search_fields = ('id_solicitud', 'contratista__nombre_razon_social')

class FielContratistaAdmin(admin.ModelAdmin):
    list_display = ('contratista', 'rfc_fiel', 'ultima_actualizacion')
    search_fields = ('rfc_fiel', 'contratista__nombre_razon_social')

class EmpleadoAdmin(admin.ModelAdmin):
    list_display = ('num_empleado', 'nombre', 'apellido_paterno', 'puesto', 'departamento', 'estado')
    list_filter = ('estado', 'departamento', 'empresa')
    search_fields = ('nombre', 'apellido_paterno', 'num_empleado', 'rfc', 'curp')

class ContratoAdmin(admin.ModelAdmin):
    list_display = ('folio', 'beneficiario', 'tipo_contrato', 'fecha_inicio', 'fecha_fin', 'estado')
    list_filter = ('estado', 'tipo_contrato', 'empresa')
    search_fields = ('folio', 'beneficiario__nombre_razon_social', 'notas')

class ContratistaAdmin(admin.ModelAdmin):
    list_display = ('rfc', 'nombre_razon_social', 'correo', 'telefono', 'representante_legal')
    list_filter = ('empresa', 'entidad_federativa')
    search_fields = ('rfc', 'nombre_razon_social', 'representante_legal')

class BeneficiarioAdmin(admin.ModelAdmin):
    list_display = ('rfc', 'nombre_razon_social', 'correo', 'telefono')
    list_filter = ('empresa', 'entidad_federativa')
    search_fields = ('rfc', 'nombre_razon_social')

class NominaAdmin(admin.ModelAdmin):
    list_display = ('folio', 'nombre', 'periodo', 'tipo_nomina', 'fecha_pago', 'sueldo_gravado')
    list_filter = ('tipo_nomina', 'empresa', 'fecha_pago')
    search_fields = ('folio', 'nombre', 'rfc', 'uuid')

# Registro seguro con manejo de excepciones para evitar bloqueos por duplicidad
def safe_register(model, admin_class):
    try:
        admin.site.register(model, admin_class)
    except admin.sites.AlreadyRegistered:
        # Si ya estÃ¡ registrado, desregistramos e intentamos de nuevo para asegurar los cambios
        admin.site.unregister(model)
        admin.site.register(model, admin_class)

safe_register(SolicitudDescargaSAT, SolicitudDescargaSATAdmin)
safe_register(FielContratista, FielContratistaAdmin)
safe_register(Empleado, EmpleadoAdmin)
safe_register(Contrato, ContratoAdmin)
safe_register(Contratista, ContratistaAdmin)
safe_register(Beneficiario, BeneficiarioAdmin)
safe_register(Nomina, NominaAdmin)
