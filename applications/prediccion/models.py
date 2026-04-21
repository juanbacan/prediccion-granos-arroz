from django.db import models
from core.models import ModeloBase

# prediccion/models/base.py (opcional; ya usas ModeloBase del core)
from django.db import models
from core.models import ModeloBase



class ConjuntoDatos(ModeloBase):
    """
    Archivo de entrenamiento (el Excel que ya tienes).
    Puedes fijar la hoja por defecto a: Modelo Black Scholes "cacao"
    """
    nombre = models.CharField("Nombre", max_length=150)
    archivo = models.FileField("Archivo (Excel/CSV)", upload_to="datasets/")

    class Meta:
        verbose_name = "Conjunto de datos"
        verbose_name_plural = "Conjuntos de datos"

    def __str__(self):
        return self.nombre


class Entrenamiento(ModeloBase):
    """
    Una corrida que entrena y evalúa Y1 (Call) y Y2 (Put) en conjunto
    usando el ConjuntoDatos. Guarda métricas y artefactos de ambos.
    """
    ESTADOS = (('PENDING','PENDIENTE'), ('RUNNING','EN PROCESO'),
               ('DONE','COMPLETO'), ('FAILED','FALLÓ'))

    nombre = models.CharField("Nombre", max_length=160, blank=True, default="")
    dataset = models.ForeignKey(
        ConjuntoDatos,
        on_delete=models.CASCADE,
        related_name='entrenamientos',
        verbose_name="Conjunto de datos"
    )
    estado = models.CharField("Estado", max_length=10, choices=ESTADOS, default='PENDING')
    resumen = models.TextField("Resumen / Log", blank=True, default="")

    # Métricas TEST para Y1 (Call)
    y1_mse  = models.FloatField("MSE (Y1)", null=True, blank=True)
    y1_rmse = models.FloatField("RMSE (Y1)", null=True, blank=True)
    y1_r2   = models.FloatField("R² (Y1)", null=True, blank=True)

    # Métricas TEST para Y2 (Put)
    y2_mse  = models.FloatField("MSE (Y2)", null=True, blank=True)
    y2_rmse = models.FloatField("RMSE (Y2)", null=True, blank=True)
    y2_r2   = models.FloatField("R² (Y2)", null=True, blank=True)

    # Artefactos (si usas RNA)
    modelo_y1_file = models.FileField("Modelo Y1 (.h5/.pkl)", upload_to="modelos/", null=True, blank=True)
    scaler_y1_file = models.FileField("Scaler Y1 (.pkl)", upload_to="modelos/", null=True, blank=True)
    modelo_y2_file = models.FileField("Modelo Y2 (.h5/.pkl)", upload_to="modelos/", null=True, blank=True)
    scaler_y2_file = models.FileField("Scaler Y2 (.pkl)", upload_to="modelos/", null=True, blank=True)

    # (Opcional) gráficos comparativos
    grafico_y1 = models.FileField("Gráfico Y1 (png)", upload_to="modelos/", null=True, blank=True)
    grafico_y2 = models.FileField("Gráfico Y2 (png)", upload_to="modelos/", null=True, blank=True)

    iniciado_en  = models.DateTimeField("Iniciado en", null=True, blank=True)
    finalizado_en = models.DateTimeField("Finalizado en", null=True, blank=True)

    class Meta:
        verbose_name = "Entrenamiento"
        verbose_name_plural = "Entrenamientos"
        indexes = [models.Index(fields=["estado"])]

    def __str__(self):
        base = self.nombre.strip() or f"Entrenamiento #{self.pk}"
        return f"{base} · {self.get_estado_display()}"

    def save(self, *args, **kwargs):
        if not self.nombre:
            from django.utils import timezone
            ts = timezone.localtime(timezone.now()).strftime("%Y-%m-%d %H:%M")
            self.nombre = f"Entrenamiento · {self.dataset.nombre} · {ts}"
        super().save(*args, **kwargs)


class TipoGrano(ModeloBase):
    nombre = models.CharField("Nombre", max_length=120)
    clave_normalizada = models.CharField("Clave normalizada", max_length=120, unique=True)
    codigo = models.PositiveIntegerField("Código", unique=True)
    activo = models.BooleanField("Activo", default=True)

    class Meta:
        verbose_name = "Tipo de grano"
        verbose_name_plural = "Tipos de grano"
        ordering = ["nombre"]
        indexes = [models.Index(fields=["clave_normalizada"])]

    def __str__(self):
        return self.nombre


class Prediccion(ModeloBase):
    ESTADOS = (('PENDING','PENDIENTE'), ('RUNNING','EN PROCESO'),
               ('DONE','COMPLETO'), ('FAILED','FALLÓ'))

    nombre = models.CharField("Nombre", max_length=160, blank=True, default="")
    entrenamiento = models.ForeignKey(
        Entrenamiento, on_delete=models.PROTECT,
        related_name="predicciones", verbose_name="Modelo (Entrenamiento)"
    )

    input_file  = models.FileField("Archivo de entrada", upload_to="pred_inputs/")
    output_file = models.FileField("Archivo con predicciones", upload_to="pred_outputs/",
                                   null=True, blank=True)

    filas_in  = models.IntegerField("Filas de entrada", default=0)
    filas_out = models.IntegerField("Filas de salida",  default=0)
    es_manual = models.BooleanField("Es manual", default=False)

    estado  = models.CharField("Estado", max_length=10, choices=ESTADOS, default='PENDING')
    resumen = models.TextField("Resumen / Log", blank=True, default="")

    iniciado_en   = models.DateTimeField("Iniciado en", null=True, blank=True)
    finalizado_en = models.DateTimeField("Finalizado en", null=True, blank=True)

    class Meta:
        verbose_name = "Predicción"
        verbose_name_plural = "Predicciones"
        indexes = [models.Index(fields=["estado"])]

    def __str__(self):
        base = self.nombre.strip() or f"Predicción #{self.pk}"
        return f"{base} · {self.get_estado_display()}"
