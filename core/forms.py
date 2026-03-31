from django import forms
from .models import Producto

class ProductoForm(forms.ModelForm):
    """
    Formulario para la creación y edición de Productos.
    Maneja automáticamente la validación de campos requeridos y tipos de datos.
    """
    class Meta:
        model = Producto
        # Excluimos 'empresa' porque se asigna dinámicamente en la vista
        # basándose en el usuario logueado.
        exclude = ['empresa'] 

    # Podemos agregar validaciones personalizadas aquí si quisiéramos
    # Por ejemplo, asegurar que el precio de venta sea mayor al costo:
    def clean(self):
        cleaned_data = super().clean()
        costo = cleaned_data.get("precio_costo")
        venta = cleaned_data.get("precio_venta")

        if costo and venta and venta < costo:
            raise forms.ValidationError("El precio de venta no puede ser menor al costo.")
        
        return cleaned_data