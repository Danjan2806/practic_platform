import os
import sys
import django
from django.urls import reverse, NoReverseMatch

print("sys.path:", sys.path)
print("cwd:", os.getcwd())

# Добавляем корень проекта в sys.path
PROJECT_ROOT = os.path.dirname(os.path.abspath(__file__))
sys.path.append(PROJECT_ROOT)

# Указываем настройки Django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'mysite.mysite.settings')

# Инициализация Django
django.setup()
print("Django успешно инициализирован\n")

from django.test import Client

client = Client()

# Список именованных эндпоинтов с тестовыми параметрами
endpoints = [
    ('user_login', {}),
    ('user_logout', {}),
    ('home', {}),
    ('create_order', {'room_type_id': 1, 'tariff_id': 1}),
    ('register', {}),
    ('rooms', {}),
    ('profile', {}),
    ('analytics', {}),
    ('edit_profile', {}),
    ('confirm_email', {'token': 'testtoken'}),
    ('download_receipt', {'order_id': 1}),
    ('order_edit', {'order_id': 1}),
    ('thank_you', {'order_id': 1}),
    ('order_delete', {'order_id': 1}),
]

def assert_endpoint(name, kwargs):
    """Проверяет доступность эндпоинта по имени и параметрам"""
    try:
        path = reverse(name, kwargs=kwargs)
        response = client.get(path)
        if response.status_code < 400:
            print(f"PASSED {path} — статус {response.status_code}")
        else:
            print(f"FAILED {path} — статус {response.status_code}")
    except NoReverseMatch:
        print(f"FAILED {name} — невозможно построить URL (проверь параметры)")
    except Exception as e:
        print(f"FAILED {name} — ошибка {e}")

print("Тестирование всех эндпоинтов account...\n")
for name, kwargs in endpoints:
    assert_endpoint(name, kwargs)

print("\nAPI тестирование завершено.")
