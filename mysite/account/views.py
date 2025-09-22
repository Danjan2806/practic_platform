import datetime
import os
import json

from django.shortcuts import render, redirect, get_object_or_404
from datetime import date, timedelta
from .models import Profile, Conveniences, Room, RoomTypeImage, RoomType, Tariff, Order, room_type_image_upload_to
from .forms import LoginForm, RegistrationForm, EditProfileForm, OrderEditForm
from django.shortcuts import render
from django.db.models import Q, Count
from datetime import datetime, timedelta
from django.contrib.auth.decorators import login_required
from django.contrib.auth import login, logout, authenticate
from django.template.loader import render_to_string
from django.http import HttpResponse, HttpResponseBadRequest, FileResponse, Http404
from django.contrib.auth.models import User
from django.core.signing import BadSignature, SignatureExpired, TimestampSigner
from django.core.mail import send_mail
from django.conf import settings
from django.contrib import messages
from django.urls import reverse
from django.db.models.functions import TruncWeek, TruncMonth, TruncYear
from django.db import connection
from collections import defaultdict
from django.utils.dateformat import format as df

signer = TimestampSigner()

def user_login(request):
    if request.method == 'POST':
        email = request.POST.get('email')
        password = request.POST.get('password')
        user = authenticate(request, username=email, password=password)

        if user is not None and user.is_active:
            if hasattr(user, 'profile') and not user.profile.email_confirmed:
                messages.error(request, "Подтвердите email перед входом.")
                return redirect('home')
            login(request, user)
            return redirect('home')
        else:
            messages.error(request, "Неверный логин или пароль.")
            return redirect('home')
    else:
        return redirect('home')


def user_logout(request):
    logout(request)
    return redirect('home')  # или redirect('/')

def confirm_email_view(request, token):
    try:
        user_id = signer.unsign(token, max_age=60*60*24)  # токен действителен 24 часа
        user = get_object_or_404(User, pk=user_id)
        
        profile = user.profile
        profile.email_confirmed = True
        profile.save()

        # Установить user.backend перед login
        user.backend = 'account.authentication.EmailAuthBackend'  # замените yourapp на имя своего приложения
        user.is_active = True
        user.save()

        login(request, user)

        return redirect('home')

    except SignatureExpired:
        return HttpResponse('Ссылка для подтверждения истекла.', status=400)
    except BadSignature:
        return HttpResponse('Недействительная ссылка.', status=400)

def home_view(request):
    guests_str = request.GET.get("guests")
    guests = int(guests_str) if guests_str and guests_str.isdigit() else None

    # Преобразуем check_in и check_out в date-объекты
    try:
        check_in_str = request.GET.get('check_in')
        check_out_str = request.GET.get('check_out')
        check_in = datetime.strptime(check_in_str, "%Y-%m-%d").date() if check_in_str else None
        check_out = datetime.strptime(check_out_str, "%Y-%m-%d").date() if check_out_str else None
    except ValueError:
        check_in, check_out = None, None

    available_room_types = []
    added_ids = set()

    # Фильтруем RoomType по вместимости гостей (если указано)
    room_types_qs = RoomType.objects.all()
    if guests:
        room_types_qs = room_types_qs.filter(capacity__gte=guests)

    # Если даты не заданы — ищем ближайшую доступную ночь
    if not check_in or not check_out:
        today = datetime.today().date()
        found_dates = False
        for offset in range(0, 365):
            candidate_in = today + timedelta(days=offset)
            candidate_out = candidate_in + timedelta(days=1)

            for room_type in room_types_qs:
                rooms = room_type.rooms.all()
                for room in rooms:
                    overlapping = Order.objects.filter(
                        room=room,
                        check_in__lt=candidate_out,
                        check_out__gt=candidate_in,
                    )
                    if not overlapping.exists():
                        check_in = candidate_in
                        check_out = candidate_out
                        found_dates = True
                        break
                if found_dates:
                    break
            if found_dates:
                break

    # Ищем доступные типы номеров с учётом дат и вместимости
    if check_in and check_out:
        for room_type in room_types_qs:
            rooms = room_type.rooms.all()
            for room in rooms:
                overlapping = Order.objects.filter(
                    room=room,
                    check_in__lt=check_out,
                    check_out__gt=check_in,
                )
                if not overlapping.exists():
                    if room_type.id not in added_ids:
                        available_room_types.append(room_type)
                        added_ids.add(room_type.id)
                    break
    else:
        # Если даты не заданы, просто показываем все, отфильтрованные по вместимости
        available_room_types = list(room_types_qs)

    # Если доступных меньше 5 — дополняем без фильтрации по вместимости
    if len(available_room_types) < 5:
        exclude_ids = [rt.id for rt in available_room_types]

        additional_room_types = RoomType.objects.exclude(id__in=exclude_ids)
        if guests:
            additional_room_types = additional_room_types.filter(capacity__gte=guests)

        needed = 5 - len(available_room_types)
        available_room_types.extend(additional_room_types[:needed])

    return render(request, 'home.html', {
        'available_room_types': available_room_types,
        'check_in': check_in,
        'check_out': check_out,
        'guests': guests,
        'check_in_time': "с 14:00",
        'check_out_time': "до 12:00",
        'hotel_name': "DSTU Hotel",
        'today': datetime.today().date().isoformat(),
    })

def create_order_view(request, room_type_id, tariff_id):
    room_type = get_object_or_404(RoomType, id=room_type_id)
    tariff = get_object_or_404(Tariff, id=tariff_id)
    check_in_str = request.GET.get('check_in')
    check_out_str = request.GET.get('check_out')

    check_in = None
    check_out = None

    try:
        if check_in_str:
            check_in = datetime.strptime(check_in_str, "%Y-%m-%d").date()
        if check_out_str:
            check_out = datetime.strptime(check_out_str, "%Y-%m-%d").date()
    except ValueError:
        # Обработка ошибки формата даты, например:
        return render(request, 'create_order.html', {
            'error': 'Некорректный формат даты. Используйте YYYY-MM-DD.',
        })

    if not check_in or not check_out:
        return render(request, 'create_order.html', {
            'error': 'Не указаны даты заезда и выезда.',
        })

    nights = (check_out - check_in).days
    if nights <= 0:
        return HttpResponseBadRequest("Дата выезда должна быть позже даты заезда.")

    login_form = LoginForm()

    # Найти свободный номер заданного типа
    booked_rooms = Order.objects.filter(
        Q(check_in__lt=check_out) & Q(check_out__gt=check_in)
    ).values_list('room_id', flat=True)

    free_room = Room.objects.filter(room_type=room_type).exclude(id__in=booked_rooms).first()

    if not free_room:
        return render(request, 'create_order.html', {
            'error': 'К сожалению, свободных номеров данного типа на выбранные даты нет.',
            'room_type': room_type,
            'tariff': tariff,
            'check_in': check_in,
            'check_out': check_out,
            'login_form': login_form,
        })

    # вход по логину
    if request.method == 'POST' and 'login' in request.POST:
        login_form = LoginForm(request.POST)
        if login_form.is_valid():
            cd = login_form.cleaned_data
            user = authenticate(request, username=cd['username'], password=cd['password'])
            if user and user.is_active:
                login(request, user)
                return redirect(request.path + '?' + request.META['QUERY_STRING'])

    # если отправлена форма заказа
    elif request.method == 'POST':
        guest_email = request.POST.get('email')
        guest_first_name = request.POST.get('first_name')
        guest_last_name = request.POST.get('last_name')
        guest_phone = request.POST.get('phone_number')
        guest_wishes = request.POST.get('wishes')
        guest_checkin_time = request.POST.get('arrival_time')

        if request.user.is_authenticated:
            profile, _ = Profile.objects.get_or_create(user=request.user, defaults={
                'first_name': guest_first_name,
                'second_name': guest_last_name,
                'phone_number': guest_phone,
                'email': guest_email,
                'role_id': 38
            })
        else:
            profile = Profile.objects.create(
                first_name=guest_first_name,
                second_name=guest_last_name,
                phone_number=guest_phone,
                email=guest_email,
                role_id=37,
                is_guest=True
            )

        total_price = tariff.price_per_night * nights
        order = Order(
            order_number=f'F{datetime.now().strftime("%Y%m%d")}{str(Order.objects.count() + 1).zfill(5)}',
            creator=profile,
            room=free_room,
            tariff=tariff,
            check_in=check_in,
            check_out=check_out,
            total_price=total_price,
            wishes=guest_wishes,
            arrival_time=guest_checkin_time or None,
        )
        order.save()
        return redirect('thank_you', order_id=order.id)


    # рассчёт времени въезда
    last_order = free_room.order_set.filter(check_out__lte=check_in).order_by('-check_out').first()
    available_from = datetime.combine(check_in, datetime.min.time()).replace(hour=14)
    total_price = tariff.price_per_night * nights
    if last_order:
        available_from = datetime.combine(last_order.check_out, datetime.min.time()) + timedelta(hours=3)

    return render(request, 'create_order.html', {
        'room_type': room_type,
        'tariff': tariff,
        'check_in': check_in,
        'check_out': check_out,
        'nights': nights,
        'available_from': available_from.strftime("%H:%M"),
        'login_form': login_form,
        'total_price': total_price,
    })

def thank_you_view(request, order_id):
    from .models import Order
    from django.http import Http404

    order = Order.objects.filter(id=order_id).first()
    if not order:
        raise Http404("Заказ не найден")

    return render(request, 'thank_you.html', {
        'order': order,
    })

def register_view(request):
    if request.method == 'POST':
        form = RegistrationForm(request.POST)
        if form.is_valid():
            # Создаём пользователя, но пока не активируем
            user = User.objects.create_user(
                username=form.cleaned_data['email'],
                email=form.cleaned_data['email'],
                password=form.cleaned_data['password'],
                first_name=form.cleaned_data['first_name'],
                last_name=form.cleaned_data['last_name'],
            )
            user.is_active = False  # Аккаунт неактивен до подтверждения
            user.save()

            user_role_id = 39
            Profile.objects.create(
                user=user,
                first_name=form.cleaned_data['first_name'],
                second_name=form.cleaned_data['last_name'],
                email=form.cleaned_data['email'],
                phone_number=form.cleaned_data['phone_number'],
                role_id=user_role_id,
            )

            # Генерируем ссылку подтверждения
            token = signer.sign(user.pk)
            confirm_url = settings.SITE_URL + reverse('confirm_email', args=[token])

            # Отправляем письмо
            send_mail(
                'Подтверждение регистрации',
                f'Здравствуйте! Подтвердите почту по ссылке:\n{confirm_url}',
                settings.DEFAULT_FROM_EMAIL,
                [user.email],
                fail_silently=False,
            )

            return render(request, 'email_sent.html', {'email': user.email})
    else:
        form = RegistrationForm()

    return render(request, 'register.html', {'form': form})

def rooms_view(request):
    room_types = RoomType.objects.prefetch_related('conveniences', 'images')
    return render(request, 'rooms.html', {'room_types': room_types})


@login_required
def profile_view(request):
    profile = request.user.profile
    sort_by = request.GET.get('sort', '-check_in')  # по умолчанию - новые по дате заезда

    allowed_sorts = {
        'tariff': 'tariff__title',
        '-tariff': '-tariff__title',
        'check_in': 'check_in',
        '-check_in': '-check_in',
        'total_price': 'total_price',
        '-total_price': '-total_price',
        'arrival_time': 'arrival_time',
        '-arrival_time': '-arrival_time',
    }
    sort_field = allowed_sorts.get(sort_by, '-check_in')

    orders = Order.objects.filter(creator=profile).order_by(sort_field)

    return render(request, 'profile.html', {
        'profile': profile,
        'orders': orders,
        'current_sort': sort_by,
    })

@login_required
def edit_profile_view(request):
    profile = request.user.profile
    if request.method == 'POST':
        form = EditProfileForm(request.POST, instance=profile)
        if form.is_valid():
            form.save()
            return redirect('home')
    else:
        form = EditProfileForm(instance=profile)
    return render(request, 'edit_profile.html', {'form': form})


def download_receipt(request, order_id):
    try:
        order = Order.objects.get(id=order_id)
    except Order.DoesNotExist:
        raise Http404("Чек не найден")

    if not order.receipt_file:
        raise Http404("Файл чека отсутствует")

    file_path = order.receipt_file.path
    filename = f"Чек_заказа_{order.order_number}.txt"

    if os.path.exists(file_path):
        return FileResponse(open(file_path, 'rb'), as_attachment=True, filename=filename)
    else:
        raise Http404("Файл не найден")

@login_required
def order_edit_view(request, order_id):
    order = get_object_or_404(Order, id=order_id, creator=request.user.profile)
    
    if request.method == 'POST':
        form = OrderEditForm(request.POST, instance=order)
        if form.is_valid():
            form.save()
            # Можно добавить сообщение об успешном сохранении
            return redirect('profile')  # или куда нужно после сохранения
    else:
        form = OrderEditForm(instance=order)
    
    return render(request, 'order_edit.html', {'form': form, 'order': order})

def get_empty_weeks(start_date, end_date):
    with connection.cursor() as cursor:
        cursor.execute("""
            WITH weeks AS (
              SELECT date_trunc('week', gs.day) AS week_start
              FROM generate_series(%s::date, %s::date, '1 week') gs(day)
            ),
            orders_per_week AS (
              SELECT date_trunc('week', check_in) AS week_start, COUNT(*) AS count
              FROM account_order
              WHERE check_in BETWEEN %s AND %s
              GROUP BY week_start
            )
            SELECT w.week_start
            FROM weeks w
            LEFT JOIN orders_per_week o ON w.week_start = o.week_start
            WHERE o.count IS NULL OR o.count = 0
            ORDER BY w.week_start;
        """, [start_date, end_date, start_date, end_date])
        rows = cursor.fetchall()
    # Вернём список дат типа datetime.date
    return [row[0] for row in rows]

@login_required
def analytics_view(request):
    start_date = request.GET.get('start_date')
    end_date = request.GET.get('end_date')
    interval = request.GET.get('interval', 'week')  # week, month, year
    chart_type = request.GET.get('chart_type', 'count')  # count, empty, peak

    today = date.today()
    if not start_date or not end_date:
        start_date = date(today.year, today.month, 1)
        end_date = today
    else:
        start_date = date.fromisoformat(start_date)
        end_date = date.fromisoformat(end_date)

    trunc_map = {
        'week': (TruncWeek, timedelta(weeks=1)),
        'month': (TruncMonth, None),  # месяцы считаем отдельно
        'year': (TruncYear, None),
    }
    trunc_fn, step = trunc_map.get(interval, (TruncWeek, timedelta(weeks=1)))

    # Получаем агрегированные данные из БД
    qs = (
        Order.objects.filter(check_in__range=(start_date, end_date))
        .annotate(period=trunc_fn('check_in'))
        .values('period')
        .annotate(count=Count('id'))
        .order_by('period')
    )

    data_dict = {entry['period'].date() if hasattr(entry['period'], 'date') else entry['period']: entry['count'] for entry in qs}

    # Формируем полный список периодов с шагом
    periods = []
    counts = []

    # Функция для перехода к следующему месяцу
    def next_month(d):
        year = d.year + (d.month // 12)
        month = d.month % 12 + 1
        return date(year, month, 1)

    if interval == 'week':
        current = start_date - timedelta(days=start_date.weekday())  # понедельник недели
        while current <= end_date:
            periods.append(current)
            counts.append(data_dict.get(current, 0))
            current += step

    elif interval == 'month':
        current = date(start_date.year, start_date.month, 1)
        while current <= end_date:
            periods.append(current)
            counts.append(data_dict.get(current, 0))
            current = next_month(current)

    elif interval == 'year':
        current = date(start_date.year, 1, 1)
        while current <= end_date:
            periods.append(current)
            counts.append(data_dict.get(current, 0))
            current = date(current.year + 1, 1, 1)

    labels = []
    if interval == 'week':
        labels = [p.strftime('%d.%m.%Y') for p in periods]
    elif interval == 'month':
        labels = [p.strftime('%B %Y') for p in periods]
    elif interval == 'year':
        labels = [str(p.year) for p in periods]

    chart_label = ''
    background_colors = []

    if chart_type == 'count':
        chart_label = "Количество заказов за период"
        background_colors = ['rgba(54, 162, 235, 0.7)'] * len(counts)

    elif chart_type == 'empty':
        # Периоды без заказов отмечаем 1, остальные 0
        counts = [1 if c == 0 else 0 for c in counts]
        chart_label = "Периоды без заказов"
        background_colors = ['rgba(255, 99, 132, 0.7)' if v == 1 else 'rgba(200,200,200,0.3)' for v in counts]

    elif chart_type == 'peak':
        chart_label = "Пиковые значения по количеству заказов"
        max_count = max(counts) if counts else 0
        background_colors = ['rgba(54, 162, 235, 0.7)' if c < max_count else 'rgba(255, 206, 86, 0.9)' for c in counts]

    context = {
        'labels_json': json.dumps(labels, ensure_ascii=False),
        'values_json': json.dumps(counts),
        'background_colors_json': json.dumps(background_colors),
        'start_date': start_date.isoformat(),
        'end_date': end_date.isoformat(),
        'interval': interval,
        'chart_type': chart_type,
        'chart_label': chart_label,
        'peak_value': max(counts) if chart_type == 'peak' and counts else None,
        'peak_period': labels[counts.index(max(counts))] if chart_type == 'peak' and counts else None,
    }

    return render(request, 'analytics.html', context)

# Create your views here.
