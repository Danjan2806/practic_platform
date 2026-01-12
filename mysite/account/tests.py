from django.test import TestCase, Client, override_settings
from django.urls import reverse
from django.contrib.auth.models import User
from django.core.files.uploadedfile import SimpleUploadedFile
from datetime import date, timedelta
from decimal import Decimal
from django.db import connection
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
    @classmethod
    def setUpTestData(cls):
        cls.role_guest = Role.objects.create(id=1, name="Гость")
        cls.role_user = Role.objects.create(id=2, name="Пользователь")

        with connection.cursor() as cursor:
            cursor.execute(
                "SELECT setval(pg_get_serial_sequence('account_role','id'), 2)"
            )
    
    def setUp(self):
        # Профиль (ВАЖНО: role_id)
        self.profile = Profile.objects.create(
            first_name="Иван",
            second_name="Иванов",
            phone_number="1234567890",
            email="ivan@example.com",
            role_id=2
        )

        # Тип комнаты и комната
        self.room_type = RoomType.objects.create(
            name="Стандарт",
            description="Описание"
        )
        self.room = Room.objects.create(
            number=101,
            room_type=self.room_type
        )

        # Тариф
        self.tariff = Tariff.objects.create(
            room_type=self.room_type,
            title="Стандартный тариф",
            price_per_night=Decimal("1000.00"),
            cancellation="Без штрафа"
        )

    # проверяет корректную строковую репрезентацию профиля (__str__).
    def test_profile_str(self):
        expected = (
            f'Профиль {self.profile.user.username}'
            if self.profile.user
            else f'Гостевой профиль: {self.profile.first_name} {self.profile.second_name}'
        )
        self.assertEqual(str(self.profile), expected)

    # гарантирует корректное отображение номера комнаты и типа в интерфейсе и админке.
    def test_room_str(self):
        self.assertEqual(
            str(self.room),
            f'Комната №{self.room.number} — {self.room.room_type.name}'
        )

    # проверяет читабельное отображение тарифа (тип комнаты + название тарифа).
    def test_tariff_str(self):
        self.assertEqual(
            str(self.tariff),
            f"{self.room_type.name} — {self.tariff.title}"
        )

    # проверяет метод Order.calculate_total_price().
    def test_order_total_price(self):
        # Удобство
        convenience = Conveniences.objects.create(
            name="Wi-Fi",
            price=Decimal("100.00")
        )

        # Заказ
        order = Order.objects.create(
            order_number="F2026011100001",
            creator=self.profile,
            room=self.room,
            tariff=self.tariff,
            check_in=date.today(),
            check_out=date.today() + timedelta(days=2)
        )

        order.conveniences.set([convenience])
        order.refresh_from_db()

        nights = (order.check_out - order.check_in).days
        expected_price = (
            self.tariff.price_per_night * nights
            + convenience.price
        )

        self.assertEqual(order.calculate_total_price(), expected_price)


# ------------------------------
# FORMS TESTS
# Валидная регистрация, проверка несовпадения паролей.
# ------------------------------
class FormsTestCase(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username="testuser", email="test@example.com", password="123456")
        self.role_guest, _ = Role.objects.get_or_create(name="Гость")

    # проверяет что форма регистрации валидна при корректных данных.
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

    # проверяет что форма отклоняет несовпадающие пароли.
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

# # ------------------------------
# # VIEWS TESTS
# # Проверка работы home_view, register_view, create_order_view (в том числе для гостя)
# # ------------------------------
# @override_settings(EMAIL_BACKEND='django.core.mail.backends.locmem.EmailBackend')
# class ViewsTestCase(TestCase):
#     @classmethod
#     def setUpTestData(cls):
#         cls.role_guest = Role.objects.create(id=1, name="Гость")
#         cls.role_user = Role.objects.create(id=2, name="Пользователь")

#         with connection.cursor() as cursor:
#             cursor.execute(
#                 "SELECT setval(pg_get_serial_sequence('account_role','id'), 2)"
#             )

#     def setUp(self):
#         # Авторизованный пользователь
#         self.user_profile = Profile.objects.create(
#             first_name="Иван",
#             second_name="Иванов",
#             email="ivan@example.com",
#             phone_number="1234567890",
#             role_id=2
#         )

#         # Даты
#         self.check_in = date.today()
#         self.check_out = self.check_in + timedelta(days=2)

#         # Комната и тариф
#         self.room_type = RoomType.objects.create(name="Стандарт", description="Описание")
#         self.room = Room.objects.create(number=101, room_type=self.room_type)
#         self.tariff = Tariff.objects.create(
#             room_type=self.room_type,
#             title="Стандартный тариф",
#             price_per_night=Decimal('1000.00'),
#             cancellation="Без штрафа"
#         )

#         # Клиент для тестов
#         self.client = Client()

#         # Данные для гостя
#         self.guest_data = {
#             "first_name": "Гость",
#             "last_name": "Тест",
#             "email": "guest@example.com",
#             "phone_number": "111",
#             "wishes": "Без окон",
#             "arrival_time": "14:00"
#         }

#     def test_create_order_view_guest(self):
#         url = reverse('create_order', args=[self.room_type.id, self.tariff.id])
#         response = self.client.post(
#             url + f'?check_in={self.check_in}&check_out={self.check_out}',
#             data=self.guest_data
#         )
#         self.assertEqual(response.status_code, 302)  # редирект на страницу благодарности

#     def test_register_view_post(self):
#         url = reverse('register')
#         post_data = {
#             "username": "newuser",
#             "first_name": "Новый",
#             "last_name": "Пользователь",
#             "email": "newuser@example.com",
#             "phone_number": "222",
#             "password": "testpassword123",
#             "password_confirm": "testpassword123"
#         }
#         response = self.client.post(url, data=post_data)
#         # Проверяем ошибки формы, если они есть
#         if response.status_code != 302:
#             self.assertEqual(response.status_code, 302)
#             self.assertRedirects(response, reverse('login'))
#         self.assertIn(response.status_code, [200, 302])
        
# ------------------------------
# SIGNALS / SIDE EFFECT TESTS
# Удаление файла чека при удалении Order.
# ------------------------------
class SignalsTestCase(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.role_guest = Role.objects.create(id=1, name="Гость")
        cls.role_user = Role.objects.create(id=2, name="Пользователь")

        with connection.cursor() as cursor:
            cursor.execute(
                "SELECT setval(pg_get_serial_sequence('account_role','id'), 2)"
            )

    def setUp(self):
        self.profile = Profile.objects.create(
            first_name="Иван",
            second_name="Иванов",
            phone_number="1234567890",
            email="ivan@example.com",
            role_id=1
        )

        self.room_type = RoomType.objects.create(name="Стандарт", description="Описание")
        self.room = Room.objects.create(number=101, room_type=self.room_type)
        self.tariff = Tariff.objects.create(
            room_type=self.room_type, title="Тариф", price_per_night=1000, cancellation="Условия"
        )

    # проверяет что файл чека удаляется с диска при удалении заказа.
    def test_post_delete_receipt_file(self):
        order = Order.objects.create(
            order_number="F2026011100001",
            creator=self.profile,
            room=self.room,
            tariff=self.tariff,
            check_in=date.today(),
            check_out=date.today() + timedelta(days=1)
        )
        relative_path = generate_order_receipt(order)
        order.receipt_file = relative_path
        order.save()
        full_path = os.path.join(settings.MEDIA_ROOT, relative_path)
        self.assertTrue(os.path.exists(full_path))

        order.delete()
        self.assertFalse(os.path.exists(full_path))