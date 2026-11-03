from django.contrib import admin
from .models import Sucursal

@admin.register(Sucursal)
class SucursalAdmin(admin.ModelAdmin):
    list_display = ('codigo', 'nombre', 'activa')
    search_fields = ('codigo', 'nombre')
    readonly_fields = ('uuid',)
