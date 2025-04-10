# accounts/admin.py
from django.contrib import admin
from .models import User, Activity

@admin.register(User)
class UserAdmin(admin.ModelAdmin):
    list_display = ('username', 'email', 'first_name', 'last_name', 'user_type', 'is_student', 'admin_type', 'is_active_admin')
    search_fields = ('username', 'email', 'first_name', 'last_name', 'phone')
    list_filter = ('user_type', 'is_student', 'admin_type', 'is_active_admin', 'created_at')
    fieldsets = (
        ('User Information', {
            'fields': ('username', 'email', 'password', 'first_name', 'last_name', 'phone', 'bio', 'profile_image')
        }),
        ('User Type', {
            'fields': ('user_type', 'is_student', 'admin_type', 'is_active_admin')
        }),
        ('Permissions', {
            'fields': ('is_active', 'is_staff', 'is_superuser', 'groups', 'user_permissions')
        }),
        ('Important dates', {
            'fields': ('last_login', 'date_joined', 'last_admin_login')
        }),
    )

@admin.register(Activity)
class ActivityAdmin(admin.ModelAdmin):
    list_display = ('user', 'activity_type', 'description', 'timestamp')
    list_filter = ('activity_type', 'timestamp')
    search_fields = ('user__username', 'user__email', 'description')