from django.contrib import admin
from django.contrib.auth.admin import UserAdmin
from .models import Empleado

@admin.register(Empleado)
class EmpleadoAdmin(UserAdmin):
    list_display = ('username', 'codigo_empleado', 'first_name', 'last_name', 'is_active', 'is_staff')
    search_fields = ('username', 'codigo_empleado', 'first_name', 'last_name')
    readonly_fields = ('id', 'version', 'version_credenciales', 'actualizado_en')
    fieldsets = UserAdmin.fieldsets + (
        ('Identidad Vita Suite', {'fields': ('id', 'codigo_empleado', 'version', 'version_credenciales', 'actualizado_en')}),
    )
    add_fieldsets = UserAdmin.add_fieldsets + (
        ('Identidad Vita Suite', {'fields': ('codigo_empleado',)}),
    )
