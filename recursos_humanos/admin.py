from django.contrib import admin
from .models import Empleado, Contrato

@admin.register(Empleado)
class EmpleadoAdmin(admin.ModelAdmin):
    list_display = ('num_empleado', 'nombre', 'apellido_paterno', 'puesto', 'departamento', 'estado')
    list_filter = ('estado', 'departamento', 'empresa')
    search_fields = ('nombre', 'apellido_paterno', 'num_empleado', 'rfc', 'curp')

@admin.register(Contrato)
class ContratoAdmin(admin.ModelAdmin):
    list_display = ('id', 'empleado', 'tipo_contrato', 'fecha_inicio', 'fecha_fin', 'estado')
    list_filter = ('estado', 'tipo_contrato', 'empresa')
    search_fields = ('empleado__nombre', 'empleado__apellido_paterno', 'notas')
