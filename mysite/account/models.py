from django.db import models
from django.conf import settings
from datetime import timedelta, date
from .email_utils import generate_order_receipt
from django.db.models.signals import post_delete
from django.dispatch import receiver
import os

class Role(models.Model):
    name = models.CharField('Наименование', blank=False, null=False, max_length=50)

    created_at = models.DateTimeField(auto_now_add=True)
    deleted_at = models.DateTimeField(blank=True, null=True)

    def __str__(self):
        return f'Роль {self.name}'


class Profile(models.Model):
    user = models.OneToOneField(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, null=True, blank=True)
    first_name = models.CharField(blank=False, null=False, max_length=255, verbose_name="Имя")
    second_name = models.CharField(blank=False, null=False, max_length=255, verbose_name="Фамилия")
    phone_number = models.CharField(blank=False, null=False, max_length=20, verbose_name="Телефон")
    date_of_birth = models.DateField(blank=True, null=True)
    email = models.EmailField(blank=False, null=False, max_length=255, verbose_name="Электронная почта")
    email_confirmed = models.BooleanField(default=False)
    role = models.ForeignKey(Role, on_delete=models.CASCADE)
    is_guest = models.BooleanField(default=False)

    created_at = models.DateTimeField(blank=True, null=True, auto_now_add=True)
    deleted_at = models.DateTimeField(blank=True, null=True)

    def save(self, *args, **kwargs):
        super().save(*args, **kwargs)
        # Если есть связанный пользователь, синхронизируем данные
        if self.user:
            updated = False
            if self.user.first_name != self.first_name:
                self.user.first_name = self.first_name
                updated = True
            if self.user.last_name != self.second_name:
                self.user.last_name = self.second_name
                updated = True
            if self.user.email != self.email:
                self.user.email = self.email
                updated = True
            if updated:
                self.user.save()

    def __str__(self):
        if self.user:
            return f'Профиль {self.user.username}'
        return f'Гостевой профиль: {self.first_name} {self.second_name}'


class Conveniences(models.Model):
    name = models.CharField(blank=False, null=False, max_length=255)
    icon = models.CharField(max_length=100, blank=True, null=True, help_text="CSS класс иконки или путь к изображению")
    price = models.DecimalField(max_digits=10, decimal_places=2, default=0)

    def __str__(self):
        return self.name


class RoomType(models.Model):
    name = models.CharField(max_length=255)  # Название типа (например, "Стандарт", "Люкс")
    description = models.TextField()  # Общее описание для типа
    conveniences = models.ManyToManyField(Conveniences, blank=True)
    capacity = models.PositiveIntegerField(default=1)  # Вместимость
    main_image = models.ImageField(upload_to='room_types/', null=True, blank=True)

    def __str__(self):
        return self.name


class Room(models.Model):
    number = models.PositiveIntegerField()  # Например, "101", "102A"
    room_type = models.ForeignKey(RoomType, on_delete=models.CASCADE, related_name='rooms')
    
    def __str__(self):
        return f'Комната №{self.number} — {self.room_type.name}'


def room_type_image_upload_to(instance, filename):
    return f"room_types/room_type_{instance.room_type.id}/{filename}"

class RoomTypeImage(models.Model):
    room_type = models.ForeignKey(RoomType, on_delete=models.CASCADE, related_name='images')
    image = models.ImageField(upload_to=room_type_image_upload_to)

    def delete(self, *args, **kwargs):
        if self.image and os.path.isfile(self.image.path):
            os.remove(self.image.path)
        super().delete(*args, **kwargs)

    def __str__(self):
        return f'Image for RoomType {self.room_type.name}'


class Tariff(models.Model):
    BED_TYPE_CHOICES = [
        ('double', 'Двуспальная кровать'),
        ('single_two', 'Две одноместные кровати'),
        ('queen', 'Кровать queen size'),
        ('king', 'Кровать king size'),
    ]

    room_type = models.ForeignKey(RoomType, on_delete=models.CASCADE, related_name='tariffs')
    title = models.CharField(max_length=255)
    price_per_night = models.DecimalField(max_digits=8, decimal_places=2)
    includes_breakfast = models.BooleanField(default=False)
    bed_type = models.CharField(max_length=255, choices=BED_TYPE_CHOICES, default='double')
    cancellation = models.CharField(help_text="Условия отмены", max_length=2000)

    def cancellation_deadline(self):
        """Возвращает дату, до которой можно отменить бронирование без штрафа"""
        return Order.check_in - timedelta(days=1)

    def __str__(self):
        return f"{self.room_type.name} — {self.title}"


class Order(models.Model):
    # Номер заказа имеет формат FYYYYMMDD{№} где № это число из 5 символов начиная с 00001
    order_number = models.CharField('Номер заказа', blank=False, null=False, max_length=14)
    creator = models.ForeignKey(Profile, on_delete=models.CASCADE)
    room = models.ForeignKey(Room, on_delete=models.CASCADE)
    tariff = models.ForeignKey(Tariff, on_delete=models.PROTECT)
    conveniences = models.ManyToManyField(Conveniences, blank=True)
    check_in = models.DateField()
    check_out = models.DateField()
    wishes = models.TextField(blank=True, null=True, verbose_name="Пожелания")
    total_price = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    created_at = models.DateTimeField(blank=True, null=True, auto_now_add=True)
    deleted_at = models.DateTimeField(blank=True, null=True)
    arrival_time = models.TimeField(blank=True, null=True)
    receipt_file = models.FileField(
        upload_to='receipts/',
        blank=True,
        null=True,
        verbose_name="Файл чека"
    )

    def calculate_total_price(self):
        nights = (self.check_out - self.check_in).days
        room_cost = self.tariff.price_per_night * nights
        conveniences_cost = sum(convenience.price for convenience in self.conveniences.all()) 
        return room_cost + conveniences_cost

    def save(self, *args, **kwargs):
        is_update = self.pk is not None  # True, если заказ уже существует

        super().save(*args, **kwargs)

        # Сначала удалить старый файл, если он есть
        if is_update and self.receipt_file and os.path.isfile(self.receipt_file.path):
            try:
                os.remove(self.receipt_file.path)
            except Exception as e:
                print(f"Не удалось удалить старый чек: {e}")

        # Сгенерировать новый чек
        relative_path = generate_order_receipt(self)

        # Обновить поле receipt_file, если изменилось
        self.receipt_file = relative_path
        super().save(update_fields=["receipt_file"])


@receiver(post_delete, sender=Order)
def delete_receipt_file(sender, instance, **kwargs):
    if instance.receipt_file and os.path.isfile(instance.receipt_file.path):
        try:
            os.remove(instance.receipt_file.path)
        except Exception as e:
            print(f"Ошибка при удалении чека: {e}")
# Create your models here.
