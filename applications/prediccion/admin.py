from django.contrib import admin

# Register your models here.
from .models import ConjuntoDatos, Entrenamiento

@admin.register(ConjuntoDatos)
class ConjuntoDatosAdmin(admin.ModelAdmin):
    list_display = ('id', 'nombre', 'archivo', 'created_at')
    search_fields = ('nombre',)
    readonly_fields = ('created_at',)


@admin.register(Entrenamiento)
class EntrenamientoAdmin(admin.ModelAdmin):
    list_display = ('id', 'nombre', 'dataset', 'estado', 'iniciado_en', 'finalizado_en')
    list_filter = ('estado', 'iniciado_en', 'finalizado_en')
    search_fields = ('nombre', 'dataset__nombre')
    readonly_fields = (
        'estado', 'resumen',
        'y1_mse', 'y1_rmse', 'y1_r2',
        'y2_mse', 'y2_rmse', 'y2_r2',
        'modelo_y1_file', 'scaler_y1_file',
        'modelo_y2_file', 'scaler_y2_file',
        'grafico_y1', 'grafico_y2',
        'iniciado_en', 'finalizado_en'
    )