from django import forms
from django.contrib.auth.models import User
from .models import Profile, Conveniences, Room, RoomTypeImage, RoomType, Tariff, Order, room_type_image_upload_to
from django.core.exceptions import ValidationError


class LoginForm(forms.Form):
    email = forms.CharField()
    password = forms.CharField(widget=forms.PasswordInput)

class RegistrationForm(forms.Form):
    first_name = forms.CharField(label='Имя', max_length=30, required=True)
    last_name = forms.CharField(label='Фамилия', max_length=30, required=True)
    phone_number = forms.CharField(label='Телефон', max_length=20, required=True)
    email = forms.EmailField(label='Почта', required=True)
    password = forms.CharField(
        widget=forms.PasswordInput(attrs={'autocomplete': 'new-password'}),
        label='Пароль',
        required=True
    )
    password_confirm = forms.CharField(
        widget=forms.PasswordInput(attrs={'autocomplete': 'new-password'}),
        label='Подтверждение пароля',
        required=True
    )

    def clean_email(self):
        email = self.cleaned_data.get('email')
        if email:
            email = email.strip().lower()
            if User.objects.filter(email__iexact=email).exists():
                raise ValidationError('Пользователь с таким email уже существует.')
        return email

    def clean(self):
        cleaned_data = super().clean()
        pw = cleaned_data.get('password')
        pw_confirm = cleaned_data.get('password_confirm')
        if pw and pw_confirm and pw != pw_confirm:
            raise ValidationError('Пароли не совпадают.')
        return cleaned_data

class EditProfileForm(forms.ModelForm):
    date_of_birth = forms.DateField(
        label='Дата рождения',
        required=False,
        widget=forms.DateInput(
            attrs={'type': 'date'},
            format='%Y-%m-%d'              # <- формат для рендеринга value
        ),
        input_formats=['%Y-%m-%d'],        # <- формат для парсинга POST
    )

    class Meta:
        model = Profile
        fields = [
            'first_name', 'second_name',
            'phone_number', 'email',
            'date_of_birth',
        ]

class OrderEditForm(forms.ModelForm):
    class Meta:
        model = Order
        fields = ['tariff', 'check_in', 'check_out', 'wishes', 'arrival_time']
        widgets = {
            'check_in': forms.DateInput(attrs={'type': 'date'}),
            'check_out': forms.DateInput(attrs={'type': 'date'}),
            'arrival_time': forms.TimeInput(attrs={'type': 'time'}),
        }
        labels = {
            'check_in': 'Дата заезда',
            'check_out': 'Дата выезда',
            'tariff': 'Тариф',
            'arrival_time': 'Время заезда',
            'wishes': 'Пожелания',
        }