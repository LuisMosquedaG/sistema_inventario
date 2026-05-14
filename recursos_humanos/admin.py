from django.contrib import admin
from .models import Empleado, Contrato, Contratista, Beneficiario

@admin.register(Empleado)
class EmpleadoAdmin(admin.ModelAdmin):
    list_display = ('num_empleado', 'nombre', 'apellido_paterno', 'puesto', 'departamento', 'estado')
    list_filter = ('estado', 'departamento', 'empresa')
    search_fields = ('nombre', 'apellido_paterno', 'num_empleado', 'rfc', 'curp')

@admin.register(Contrato)
class ContratoAdmin(admin.ModelAdmin):
    list_display = ('folio', 'beneficiario', 'tipo_contrato', 'fecha_inicio', 'fecha_fin', 'estado')
    list_filter = ('estado', 'tipo_contrato', 'empresa')
    search_fields = ('folio', 'beneficiario__nombre_razon_social', 'notas')

@admin.register(Contratista)
class ContratistaAdmin(admin.ModelAdmin):
    list_display = ('rfc', 'nombre_razon_social', 'correo', 'telefono', 'representante_legal')
    list_filter = ('empresa', 'entidad_federativa')
    search_fields = ('rfc', 'nombre_razon_social', 'representante_legal')

@admin.register(Beneficiario)
class BeneficiarioAdmin(admin.ModelAdmin):
    list_display = ('rfc', 'nombre_razon_social', 'correo', 'telefono')
    list_filter = ('empresa', 'entidad_federativa')
    search_fields = ('rfc', 'nombre_razon_social')
