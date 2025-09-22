from django.contrib import admin
from .models import Role, Profile, Conveniences, RoomType, Room, RoomTypeImage, Tariff, Order

class RoomInline(admin.TabularInline):
    model = Room
    extra = 1

class TariffInline(admin.TabularInline):  # или admin.StackedInline
    model = Tariff
    extra = 1

class RoomTypeImageInline(admin.TabularInline):
    model = RoomTypeImage
    extra = 1  # сколько пустых форм будет показано для добавления фото

class RoomTypeAdmin(admin.ModelAdmin):
    inlines = [RoomTypeImageInline]
    list_display = ('name', 'capacity')
    search_fields = ('name',)

@admin.register(Conveniences)
class ConveniencesAdmin(admin.ModelAdmin):
    list_display = ('name', 'icon', 'price')
    search_fields = ('name',)
    
@admin.register(Room)
class RoomAdmin(admin.ModelAdmin):
    list_display = ('number', 'room_type')
    list_filter = ('room_type',)
    search_fields = ('number',)

@admin.register(Tariff)
class TariffAdmin(admin.ModelAdmin):
    list_display = ('title', 'room_type', 'price_per_night', 'includes_breakfast', 'bed_type')
    list_filter = ('room_type', 'includes_breakfast', 'bed_type')
    search_fields = ('title', 'room_type__name')

@admin.register(Role)
class RoleAdmin(admin.ModelAdmin):
    list_display = ('id', 'name', 'created_at')
    search_fields = ('name',)

@admin.register(Profile)
class ProfileAdmin(admin.ModelAdmin):
    list_display = ('user', 'first_name', 'second_name', 'email', 'phone_number', 'role', 'is_guest')
    list_filter = ('role', 'is_guest')
    search_fields = ('first_name', 'second_name', 'email', 'phone_number')
    ordering = ('user',)
    fieldsets = (
        (None, {
            'fields': (
                'user',
                'first_name',
                'second_name',
                'email',
                'phone_number',
                'date_of_birth',
                'role',
                'is_guest'
            )
        }),
    )

@admin.register(Order)
class OrderAdmin(admin.ModelAdmin):
    list_display = ('id', 'order_number', 'creator', 'room', 'tariff', 'check_in', 'check_out', 'total_price', 'arrival_time')
    list_filter = ('check_in', 'check_out')
    search_fields = ('order_number', 'creator__user__username')
    autocomplete_fields = ['creator', 'room', 'tariff', 'conveniences']



admin.site.register(RoomType, RoomTypeAdmin)
# Register your models here.
