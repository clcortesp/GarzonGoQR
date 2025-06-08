from django import forms
from django.core.validators import RegexValidator
from .models import Order


class CheckoutForm(forms.ModelForm):
    """
    Formulario para el proceso de checkout
    """
    
    # Validador para teléfono
    phone_validator = RegexValidator(
        regex=r'^\+?1?\d{9,15}$',
        message="Ingrese un número de teléfono válido. Ej: +57 300 123 4567"
    )
    
    class Meta:
        model = Order
        fields = [
            'customer_name',
            'customer_phone', 
            'customer_email',
            'order_type',
            'table_number',
            'delivery_address',
            'payment_method',
            'customer_notes'
        ]
        
        widgets = {
            'customer_name': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'Ingrese su nombre completo',
                'required': True
            }),
            'customer_phone': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': '+57 300 123 4567',
                'type': 'tel'
            }),
            'customer_email': forms.EmailInput(attrs={
                'class': 'form-control',
                'placeholder': 'correo@ejemplo.com'
            }),
            'order_type': forms.Select(attrs={
                'class': 'form-select',
                'id': 'id_order_type'
            }),
            'table_number': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'Ej: Mesa 5',
                'id': 'id_table_number'
            }),
            'delivery_address': forms.Textarea(attrs={
                'class': 'form-control',
                'rows': 3,
                'placeholder': 'Dirección completa de entrega',
                'id': 'id_delivery_address'
            }),
            'payment_method': forms.Select(attrs={
                'class': 'form-select'
            }),
            'customer_notes': forms.Textarea(attrs={
                'class': 'form-control',
                'rows': 3,
                'placeholder': 'Instrucciones especiales, alergias, etc.'
            })
        }
        
        labels = {
            'customer_name': 'Nombre completo',
            'customer_phone': 'Teléfono',
            'customer_email': 'Correo electrónico',
            'order_type': 'Tipo de pedido',
            'table_number': 'Número de mesa',
            'delivery_address': 'Dirección de entrega',
            'payment_method': 'Método de pago',
            'customer_notes': 'Notas especiales'
        }
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        
        # Hacer campos obligatorios
        self.fields['customer_name'].required = True
        self.fields['customer_phone'].required = True
        self.fields['order_type'].required = True
        self.fields['payment_method'].required = True
        
        # Aplicar validador de teléfono
        self.fields['customer_phone'].validators = [self.phone_validator]
    
    def clean(self):
        cleaned_data = super().clean()
        order_type = cleaned_data.get('order_type')
        table_number = cleaned_data.get('table_number')
        delivery_address = cleaned_data.get('delivery_address')
        
        # Validar campos según el tipo de pedido
        if order_type == 'dine_in' and not table_number:
            raise forms.ValidationError({
                'table_number': 'El número de mesa es obligatorio para pedidos en el restaurante.'
            })
        
        if order_type == 'delivery' and not delivery_address:
            raise forms.ValidationError({
                'delivery_address': 'La dirección de entrega es obligatoria para pedidos a domicilio.'
            })
        
        return cleaned_data


class OrderStatusUpdateForm(forms.ModelForm):
    """
    Formulario para actualizar el estado de una orden (para el restaurante)
    """
    
    class Meta:
        model = Order
        fields = ['status', 'estimated_preparation_time', 'internal_notes']
        
        widgets = {
            'status': forms.Select(attrs={
                'class': 'form-select'
            }),
            'estimated_preparation_time': forms.NumberInput(attrs={
                'class': 'form-control',
                'min': '5',
                'max': '180',
                'step': '5'
            }),
            'internal_notes': forms.Textarea(attrs={
                'class': 'form-control',
                'rows': 3,
                'placeholder': 'Notas internas del restaurante...'
            })
        }
        
        labels = {
            'status': 'Estado del pedido',
            'estimated_preparation_time': 'Tiempo estimado (minutos)',
            'internal_notes': 'Notas internas'
        }


class CustomerReviewForm(forms.ModelForm):
    """
    Formulario para que el cliente deje una reseña
    """
    
    class Meta:
        model = Order
        fields = ['rating', 'review']
        
        widgets = {
            'rating': forms.Select(
                choices=[(i, f"{i} estrella{'s' if i > 1 else ''}") for i in range(1, 6)],
                attrs={'class': 'form-select'}
            ),
            'review': forms.Textarea(attrs={
                'class': 'form-control',
                'rows': 4,
                'placeholder': 'Comparte tu experiencia con este pedido...'
            })
        }
        
        labels = {
            'rating': 'Calificación',
            'review': 'Reseña'
        } 