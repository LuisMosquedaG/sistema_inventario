from django import forms
from .models import Cliente

class ClienteForm(forms.ModelForm):
    class Meta:
        model = Cliente
        # ==========================================
        # LISTA COMPLETA DE CAMPOS
        # Incluimos Clasificación, Dirección Fiscal y Dirección de Envío
        # ==========================================
        fields = [
            # 1. Clasificación
            'estado', 
            'tipo', 
            'relacion',
            
            # 2. Datos Personales y Fiscales
            'nombre', 
            'apellidos', 
            'razon_social', 
            'rfc', 
            'email', 
            'telefono',
            
            # 3. Dirección Fiscal (Corregido 'estado' por 'estado_dir')
            'calle', 
            'numero_ext', 
            'numero_int', 
            'colonia', 
            'estado_dir',  # <-- IMPORTANTE: Aquí debe ser estado_dir
            'cp',
            
            # 4. Dirección de Envío (NUEVOS CAMPOS)
            'envio_calle', 
            'envio_numero_ext', 
            'envio_numero_int', 
            'envio_colonia', 
            'envio_estado', 
            'envio_cp',
            'envio_quien_recibe',
            'envio_telefono',
            'envio_correo',
            'envio_notas'
        ]
        
        widgets = {
            # --- Clasificación ---
            'estado': forms.Select(attrs={'class': 'form-select form-select-sm'}),
            'tipo': forms.Select(attrs={'class': 'form-select form-select-sm'}),
            'relacion': forms.Select(attrs={'class': 'form-select form-select-sm'}),

            # --- Personales ---
            'nombre': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Nombre(s)'}),
            'apellidos': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Apellidos'}),
            'razon_social': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Ej. Mi Empresa S.A. de C.V.'}),
            'rfc': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'RFC (13 caracteres)', 'maxlength': '13'}),
            'email': forms.EmailInput(attrs={'class': 'form-control', 'placeholder': 'correo@ejemplo.com'}),
            'telefono': forms.TextInput(attrs={'class': 'form-control', 'placeholder': '555-0123'}),
            
            # --- Dirección Fiscal ---
            'calle': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Calle'}),
            'numero_ext': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Número Ext'}),
            'numero_int': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Número Int'}),
            'colonia': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Colonia'}),
            'estado_dir': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Estado'}),
            'cp': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'C.P.'}),

            # --- Dirección de Envío (Nuevos Widgets) ---
            'envio_calle': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Calle Envío'}),
            'envio_numero_ext': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Número Ext'}),
            'envio_numero_int': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Número Int'}),
            'envio_colonia': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Colonia'}),
            'envio_estado': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Estado'}),
            'envio_cp': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'C.P.'}),
            'envio_quien_recibe': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Quién recibe'}),
            'envio_telefono': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Teléfono'}),
            'envio_correo': forms.EmailInput(attrs={'class': 'form-control', 'placeholder': 'Correo'}),
            'envio_notas': forms.Textarea(attrs={'class': 'form-control', 'rows': 2, 'placeholder': 'Notas de envío'}),
        }

    def clean(self):
        cleaned_data = super().clean()
        nombre = cleaned_data.get("nombre")
        razon_social = cleaned_data.get("razon_social")

        # Validación lógica: O uno o el otro
        if not nombre and not razon_social:
            raise forms.ValidationError("Debes ingresar al menos un Nombre o una Razón Social.")

        return cleaned_data