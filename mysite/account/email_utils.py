from django.core.signing import TimestampSigner, BadSignature, SignatureExpired
from django.core.mail import send_mail
from django.urls import reverse
from django.conf import settings
import os

signer = TimestampSigner()

def send_confirmation_email(user):
    token = signer.sign(user.pk)
    url = settings.SITE_URL + reverse('confirm_email', args=[token])
    subject = "Подтверждение Email"
    message = f"Здравствуйте, {user.first_name}!\n\nПерейдите по ссылке, чтобы подтвердить свою почту: {url}"
    send_mail(subject, message, settings.DEFAULT_FROM_EMAIL, [user.email])

def generate_order_receipt(order):
    filename = f"receipt_{order.order_number}.txt"
    filepath = os.path.join(settings.MEDIA_ROOT, 'receipts', filename)

    os.makedirs(os.path.dirname(filepath), exist_ok=True)

    with open(filepath, 'w', encoding='utf-8') as f:
        f.write(f"Чек бронирования #{order.order_number}\n")
        f.write(f"Дата создания: {order.created_at.strftime('%Y-%m-%d %H:%M') if order.created_at else '—'}\n\n")
        if order.creator:
            full_name = f"{order.creator.first_name} {order.creator.second_name}".strip()
            email = order.creator.user.email if order.creator.user else order.creator.email
        else:
            full_name = "Неизвестный заказчик"
            email = "—"
        f.write(f"Заказчик: {full_name} ({email})\n")
        f.write(f"Телефон: {order.creator.phone_number}\n\n")
        f.write(f"Номер: {order.room.number} ({order.room.room_type.name})\n")
        f.write(f"Тариф: {order.tariff.title}\n")
        f.write(f"Заезд: {order.check_in} (с {order.arrival_time})\n")
        f.write(f"Выезд: {order.check_out}\n")
        f.write(f"Ночей: {(order.check_out - order.check_in).days}\n")
        f.write("Удобства:\n")

        # Сначала пробуем использовать удобства, явно указанные в заказе
        conveniences = order.conveniences.all()

        # Если они отсутствуют, берём из room_type
        if not conveniences:
            conveniences = order.room.room_type.conveniences.all()

        # Если всё равно пусто — пишем прочерк
        if conveniences:
            for conv in conveniences:
                f.write(f" - {conv.name}\n")
        else:
            f.write(" - —\n")
        f.write(f"\nПожелания: {order.wishes or '—'}\n")
        f.write(f"\nОбщая цена: {order.total_price} ₽\n")

    return f'receipts/{filename}'  # относительный путь для FileField