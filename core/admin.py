from django.contrib import admin

# Register your models here.
# core/admin.py
from django.contrib import admin
from .models import UserProfile

@admin.register(UserProfile)
class UserProfileAdmin(admin.ModelAdmin):
    list_display = ['user', 'role', 'status', 'phone', 'employee_number']
    list_filter = ['role', 'status', 'department']
    search_fields = ['user__username', 'user__email', 'employee_number']
    readonly_fields = ['created_at', 'updated_at']