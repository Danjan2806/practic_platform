# Используем официальный Python
FROM python:3.12-slim

# Рабочая директория внутри контейнера
WORKDIR /app

# Сначала копируем requirements
COPY requirements.txt .

RUN pip install --no-cache-dir -r requirements.txt

# Копируем всё Django-приложение
COPY . .

# Указываем рабочую директорию на папку mysite
WORKDIR /app/mysite

# Экспонируем порт Django
EXPOSE 8000

# Команда запуска Django
CMD ["python", "mysite/manage.py", "runserver", "0.0.0.0:8000"]
