from django.db import models
from panel.models import Empresa  # <--- IMPORTANTE

class Cliente(models.Model):
    # 1. Datos de la Persona
    nombre = models.CharField(max_length=100, verbose_name="Nombre")
    apellidos = models.CharField(max_length=100, verbose_name="Apellidos")
    
    # --- NUEVO CAMPO: MULTI-TENANCY ---
    empresa = models.ForeignKey(Empresa, on_delete=models.CASCADE, null=True, blank=True, verbose_name="Empresa (Tenant)")
    
    # 2. Datos Fiscales
    razon_social = models.CharField(max_length=200, blank=True, null=True, verbose_name="Razón Social")
    rfc = models.CharField(max_length=13, blank=True, null=True, verbose_name="RFC")
    
    # 3. Datos de Contacto Principal
    email = models.EmailField(blank=True, null=True, verbose_name="Correo Electrónico")
    telefono = models.CharField(max_length=20, blank=True, null=True, verbose_name="Teléfono")
    
    # 4. DATOS DE DIRECCIÓN
    calle = models.CharField(max_length=200, blank=True, null=True, verbose_name="Calle")
    numero_ext = models.CharField(max_length=10, blank=True, null=True, verbose_name="Número Exterior")
    numero_int = models.CharField(max_length=10, blank=True, null=True, verbose_name="Número Interior")
    colonia = models.CharField(max_length=100, blank=True, null=True, verbose_name="Colonia")
    estado_dir = models.CharField(max_length=100, blank=True, null=True, verbose_name="Estado (Ubicación)")
    cp = models.CharField(max_length=10, blank=True, null=True, verbose_name="Código Postal")
    
    # --- 5. DATOS DE DIRECCIÓN DE ENVÍO (NUEVOS) ---
    envio_calle = models.CharField(max_length=200, blank=True, null=True, verbose_name="Calle Envío")
    envio_numero_ext = models.CharField(max_length=10, blank=True, null=True, verbose_name="Número Ext. Envío")
    envio_numero_int = models.CharField(max_length=10, blank=True, null=True, verbose_name="Número Int. Envío")
    envio_colonia = models.CharField(max_length=100, blank=True, null=True, verbose_name="Colonia Envío")
    envio_estado = models.CharField(max_length=100, blank=True, null=True, verbose_name="Estado Envío")
    envio_cp = models.CharField(max_length=10, blank=True, null=True, verbose_name="CP Envío")
    
    envio_quien_recibe = models.CharField(max_length=150, blank=True, null=True, verbose_name="Quién Recibe")
    envio_telefono = models.CharField(max_length=20, blank=True, null=True, verbose_name="Teléfono Recibe")
    envio_correo = models.EmailField(blank=True, null=True, verbose_name="Correo Recibe")
    envio_notas = models.TextField(blank=True, null=True, verbose_name="Notas de Envío")

    creado_en = models.DateTimeField(auto_now_add=True, verbose_name="Registrado el")
    
    # 6. CLASIFICACIÓN DEL CLIENTE
    ESTADO_OPCIONES = (
        ('activo', 'Activo'),
        ('suspendido', 'Suspendido'),
        ('inactivo', 'Inactivo'),
    )

    TIPO_OPCIONES = (
        ('prospecto', 'Prospecto'),
        ('cliente_nuevo', 'Cliente Nuevo'),
        ('cliente_activo', 'Cliente Activo'),
        ('cliente_inactivo', 'Cliente Inactivo'),
        ('vip', 'VIP'),
    )

    RELACION_OPCIONES = (
        ('directo', 'Directo'),
        ('referido', 'Referido'),
        ('revendedor', 'Revendedor'),
    )

    estado = models.CharField(max_length=20, choices=ESTADO_OPCIONES, default='activo', verbose_name="Estado")
    tipo = models.CharField(max_length=20, choices=TIPO_OPCIONES, default='prospecto', verbose_name="Tipo")
    relacion = models.CharField(max_length=20, choices=RELACION_OPCIONES, default='directo', verbose_name="Relación")
    
    creado_en = models.DateTimeField(auto_now_add=True, verbose_name="Registrado el")

    def __str__(self):
        return self.nombre_completo

    @property
    def nombre_completo(self):
        """Devuelve Razón Social si existe, sino Nombre + Apellidos"""
        if self.razon_social:
            return self.razon_social
        return f"{self.nombre} {self.apellidos}".strip()

    class Meta:
        verbose_name = "Cliente"
        verbose_name_plural = "Clientes"


class ContactoCliente(models.Model):
    # Nota: Contacto no necesita campo 'empresa' porque pertenece a un Cliente, 
    # y el Cliente ya pertenece a una empresa.
    cliente = models.ForeignKey(Cliente, on_delete=models.CASCADE, related_name='contactos')
    
    nombre_completo = models.CharField(max_length=200, verbose_name="Nombre Completo")
    telefono_1 = models.CharField(max_length=20, blank=True, null=True, verbose_name="Teléfono 1")
    telefono_2 = models.CharField(max_length=20, blank=True, null=True, verbose_name="Teléfono 2")
    correo_1 = models.EmailField(blank=True, null=True, verbose_name="Correo 1")
    correo_2 = models.EmailField(blank=True, null=True, verbose_name="Correo 2")
    notas = models.TextField(blank=True, null=True, verbose_name="Notas")
    
    creado_en = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return self.nombre_completo

    class Meta:
        verbose_name = "Contacto"
        verbose_name_plural = "Contactos"