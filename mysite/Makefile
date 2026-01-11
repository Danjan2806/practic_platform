# Makefile для проекта Django на Windows

# Путь к виртуальному окружению
VENV=my_env\Scripts\activate.bat

# Запуск виртуального окружения и выполнение команды
define run_in_venv
	@call $(VENV) && $(1)
endef

# Установка зависимостей
install:
	$(call run_in_venv,pip install -r requirements.txt)

# Применение миграций
migrate:
	$(call run_in_venv,python manage.py migrate)

# Создание суперпользователя
createsuperuser:
	$(call run_in_venv,python manage.py createsuperuser)

# Запуск сервера разработки
run:
	cd mysite && $(call run_in_venv,python manage.py runserver)

# Очистка pyc файлов
clean:
	@del /S /Q *.pyc 2>nul || true
	@del /S /Q __pycache__ 2>nul || true

