from django.urls import path, include
from django.contrib.auth import views as auth_views
from . import views

urlpatterns = [
    path('login/', views.user_login, name='user_login'),
    path('logout/', views.user_logout, name='user_logout'),
    path('', views.home_view, name='home'),
    path('', include('django.contrib.auth.urls')),
    path('order/create/<int:room_type_id>/<int:tariff_id>/', views.create_order_view, name='create_order'),
    path('register/', views.register_view, name='register'),
    path('rooms/', views.rooms_view, name='rooms'),
    path('profile/', views.profile_view, name='profile'),
    path('analytics/', views.analytics_view, name='analytics'),
    path('profile/edit/', views.edit_profile_view, name='edit_profile'),
    path('confirm-email/<str:token>/', views.confirm_email_view, name='confirm_email'),
    path('orders/<int:order_id>/download_receipt/', views.download_receipt, name='download_receipt'),
    path('order/edit/<int:order_id>/', views.order_edit_view, name='order_edit'),
    path('order/thank-you/<int:order_id>/', views.thank_you_view, name='thank_you'),
]