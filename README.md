# Practic Platform

Practic Platform — это веб-приложение для бронирования номеров в отеле с возможностью управления пользователями, аналитики заказов и интеграцией с современными инструментами разработки. Проект разработан на **Python** с использованием **Django**, **Flask**, а также различных вспомогательных библиотек для работы с API, тестирования и визуализации данных.

---

## Технологии

- Python 3.12
- Django 4.2
- PostgreSQL
- Docker
- Git / GitHub
- GitLab (для автоматизации сборки)
- VS Code
- Pytest (для модульного тестирования)
- Chart.js (для аналитики)
- PIP для управления зависимостями

---

## Установка и запуск проекта

1. **Клонируем репозиторий**
```
git clone https://github.com/Danjan2806/practic_platform.git
cd practic_platform
```

2. **Создаём виртуальное окружение**
```
python -m venv venv
```

3. **Активируем виртуальное окружение**
Windows:
```
cd practic_platform
venv\Scripts\activate.bat    
```
Linux/macOS:
```
cd practic_platform
source venv/bin/activate   
```

4. **Устанавливаем зависимости**
```
pip install -r requirements.txt
```

5. **Применяем миграции базы данных**
```
python manage.py migrate
```

6. **Запускаем сервер разработки**
```
cd mysite
python manage.py runserver
```
