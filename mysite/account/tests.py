from django.test import TestCase, Client
from django.urls import reverse
from django.contrib.auth.models import User
from django.core.files.uploadedfile import SimpleUploadedFile
from django.utils import timezone
from datetime import date, timedelta
import os

from .models import Profile, Role, RoomType, Room, Tariff, Order, Conveniences, RoomTypeImage
from .forms import RegistrationForm, EditProfileForm, OrderEditForm
from .email_utils import generate_order_receipt
from django.conf import settings

# ------------------------------
# MODELS TESTS
# Проверка __str__, подсчёт общей цены заказа.
# ------------------------------
class ModelsTestCase(TestCase):
    def setUp(self):
        self.role = Role.objects.create(name="Гость")
        self.profile = Profile.objects.create(
            first_name="Иван", second_name="Иванов",
            phone_number="1234567890",
            email="ivan@example.com",
            role=self.role
        )
        self.room_type = RoomType.objects.create(name="Стандарт", description="Описание")
        self.room = Room.objects.create(number=101, room_type=self.room_type)
        self.tariff = Tariff.objects.create(
            room_type=self.room_type,
            title="Стандартный тариф",
            price_per_night=1000,
            cancellation="Без штрафа"
        )

    def test_profile_str(self):
        self.assertEqual(str(self.profile), f'Профиль {self.profile.user.username}' if self.profile.user else f'Гостевой профиль: {self.profile.first_name} {self.profile.second_name}')

    def test_room_str(self):
        self.assertEqual(str(self.room), f'Комната №{self.room.number} — {self.room.room_type.name}')

    def test_tariff_str(self):
        self.assertEqual(str(self.tariff), f"{self.room_type.name} — {self.tariff.title}")

    def test_order_total_price(self):
        convenience = Conveniences.objects.create(name="Wi-Fi", price=100)
        order = Order.objects.create(
            order_number="F2026011100001",
            creator=self.profile,
            room=self.room,
            tariff=self.tariff,
            check_in=date.today(),
            check_out=date.today() + timedelta(days=2)
        )
        order.conveniences.add(convenience)
        expected_price = 2 * self.tariff.price_per_night + 100
        self.assertEqual(order.calculate_total_price(), expected_price)

# ------------------------------
# FORMS TESTS
# Валидная регистрация, проверка несовпадения паролей.
# ------------------------------
class FormsTestCase(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username="testuser", email="test@example.com", password="123456")
        self.role = Role.objects.create(name="Гость")

    def test_registration_form_valid(self):
        form_data = {
            "first_name": "Пётр",
            "last_name": "Петров",
            "phone_number": "111222333",
            "email": "petr@example.com",
            "password": "12345678",
            "password_confirm": "12345678"
        }
        form = RegistrationForm(data=form_data)
        self.assertTrue(form.is_valid())

    def test_registration_form_password_mismatch(self):
        form_data = {
            "first_name": "Пётр",
            "last_name": "Петров",
            "phone_number": "111222333",
            "email": "petr2@example.com",
            "password": "12345678",
            "password_confirm": "87654321"
        }
        form = RegistrationForm(data=form_data)
        self.assertFalse(form.is_valid())
        self.assertIn('Пароли не совпадают.', form.errors.get('__all__')[0])

# ------------------------------
# VIEWS TESTS
# Проверка работы home_view, register_view, create_order_view (в том числе для гостя)
# ------------------------------
class ViewsTestCase(TestCase):
    def setUp(self):
        self.client = Client()
        self.role = Role.objects.create(name="Гость")
        self.user = User.objects.create_user(username="user1", email="user1@example.com", password="pass1234")
        self.profile = Profile.objects.create(user=self.user, first_name="Иван", second_name="Иванов", phone_number="123", email="user1@example.com", role=self.role)
        self.room_type = RoomType.objects.create(name="Стандарт", description="Описание")
        self.room = Room.objects.create(number=101, room_type=self.room_type)
        self.tariff = Tariff.objects.create(room_type=self.room_type, title="Тариф", price_per_night=1000, cancellation="Условия")

    def test_home_view_status(self):
        response = self.client.get(reverse('home'))
        self.assertEqual(response.status_code, 200)
        self.assertIn('available_room_types', response.context)

    def test_register_view_post(self):
        form_data = {
            "first_name": "Пётр",
            "last_name": "Петров",
            "phone_number": "123456",
            "email": "new@example.com",
            "password": "12345678",
            "password_confirm": "12345678"
        }
        response = self.client.post(reverse('register'), data=form_data)
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "email_sent")

    def test_create_order_view_guest(self):
        url = reverse('create_order', args=[self.room_type.id, self.tariff.id])
        check_in = (date.today() + timedelta(days=1)).isoformat()
        check_out = (date.today() + timedelta(days=2)).isoformat()
        data = {
            "first_name": "Гость",
            "last_name": "Гостев",
            "email": "guest@example.com",
            "phone_number": "111222",
        }
        response = self.client.post(f"{url}?check_in={check_in}&check_out={check_out}", data=data)
        self.assertEqual(response.status_code, 302)  # редирект на thank_you
        self.assertTrue(Order.objects.filter(creator__email="guest@example.com").exists())

# ------------------------------
# SIGNALS / SIDE EFFECT TESTS
# Удаление файла чека при удалении Order.
# ------------------------------
class SignalsTestCase(TestCase):
    def setUp(self):
        self.role = Role.objects.create(name="Гость")
        self.profile = Profile.objects.create(first_name="Иван", second_name="Иванов", phone_number="123", email="user@example.com", role=self.role)
        self.room_type = RoomType.objects.create(name="Стандарт", description="Описание")
        self.room = Room.objects.create(number=101, room_type=self.room_type)
        self.tariff = Tariff.objects.create(room_type=self.room_type, title="Тариф", price_per_night=1000, cancellation="Условия")

    def test_post_delete_receipt_file(self):
        order = Order.objects.create(
            order_number="F2026011100001",
            creator=self.profile,
            room=self.room,
            tariff=self.tariff,
            check_in=date.today(),
            check_out=date.today() + timedelta(days=1)
        )
        # сгенерируем файл
        relative_path = generate_order_receipt(order)
        order.receipt_file = relative_path
        order.save()
        full_path = os.path.join(settings.MEDIA_ROOT, relative_path)
        self.assertTrue(os.path.exists(full_path))

        order.delete()
        self.assertFalse(os.path.exists(full_path))