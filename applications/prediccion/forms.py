from django import forms
from .models import Entrenamiento, TipoGrano
from core.forms import BaseForm
from core.layout import FormHelper, Layout, Fieldset, Row, Column, Field, Separator


class SubirYEntrenarForm(BaseForm):
    # 1) Dataset
    nombre = forms.CharField(label="Nombre del entrenamiento", max_length=150)
    archivo = forms.FileField(
        label="Archivo de lotes (Excel o CSV)",
        help_text="Cargue la tabla de variables con los lotes procesados.",
    )

    # 2) Configuración general
    semilla = forms.IntegerField(label="Semilla aleatoria", initial=42)
    usar_escalado = forms.BooleanField(label="Normalizar datos (Scaling)", required=False, initial=True)

    # 3) Hiperparámetros del modelo
    n_estimadores = forms.IntegerField(
        label="Número de árboles (n_estimators)",
        initial=30,
        min_value=10,
        max_value=1000,
        help_text="Valor recomendado para pocos datos: 30.",
    )
    max_profundidad = forms.IntegerField(
        label="Profundidad máxima (max_depth)",
        initial=3,
        min_value=1,
        max_value=100,
        help_text="Valor recomendado para pocos datos: 3 (reduce sobreajuste).",
    )

    # 4) Formato de salida
    decimales = forms.IntegerField(label="Decimales en resultados", initial=2, min_value=0, max_value=4)
    forzar_no_negativo = forms.BooleanField(
        label="Evitar valores negativos",
        help_text="Asegura que la humedad y blancura sean siempre mayores a cero.",
        required=False,
        initial=True,
    )

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        self.fields["nombre"].help_text = "Nombre interno para identificar esta corrida de entrenamiento."
        self.fields["semilla"].help_text = "Permite reproducir resultados entre ejecuciones."
        self.fields["usar_escalado"].help_text = "Normaliza variables de entrada para mejorar estabilidad del modelo."
        self.fields["decimales"].help_text = "Cantidad de decimales en los resultados exportados."

        self.fields["nombre"].widget.attrs.update({"placeholder": "Ej.: Lotes_Semana4_Hornos"})
        self.fields["n_estimadores"].widget.attrs.update({"step": "10"})

    # Validación mínima
    def clean(self):
        cleaned = super().clean()
        f = cleaned.get("archivo")
        if f:
            name = f.name.lower()
            if not (name.endswith(".xlsx") or name.endswith(".xls") or name.endswith(".csv")):
                self.add_error("archivo", "Formato no permitido. Usa .xlsx, .xls o .csv")
        return cleaned

class PrediccionNuevaForm(BaseForm):
    nombre = forms.CharField(label="Nombre de la predicción", max_length=160)

    entrenamiento = forms.ModelChoiceField(
        label="Modelo (Entrenamiento)",
        queryset=Entrenamiento.objects.filter(estado="DONE").order_by("-finalizado_en", "-id"),
        required=False,
        empty_label="Usar el último entrenamiento completado"
    )

    archivo = forms.FileField(
        label="Archivo de entrada (Excel .xlsx/.xls o CSV)",
        help_text="Se usará la primera hoja si es Excel.",
        required=True,
    )

    # Opciones de salida
    decimales = forms.IntegerField(label="Decimales", initial=2, min_value=0, max_value=6)
    forzar_no_negativo = forms.BooleanField(label="Forzar no negativo", required=False, initial=True)

    # Validación mínima
    def clean(self):
        cleaned = super().clean()
        f = cleaned.get("archivo")
        if not f:
            self.add_error("archivo", "Este campo es obligatorio")
            return cleaned

        if f:
            name = f.name.lower()
            if not (name.endswith(".xlsx") or name.endswith(".xls") or name.endswith(".csv")):
                self.add_error("archivo", "Formato no permitido. Usa .xlsx, .xls o .csv")
        return cleaned

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        self.fields["nombre"].help_text = "Nombre para identificar esta corrida de predicción."
        self.fields["entrenamiento"].help_text = "Opcional: si no selecciona uno, se usa el último entrenamiento finalizado (DONE)."
        self.fields["decimales"].help_text = "Cantidad de decimales en los resultados generados."
        self.fields["forzar_no_negativo"].help_text = "Si se activa, los valores negativos se ajustan a 0."

        self.fields["nombre"].widget.attrs.update({"placeholder": "Ej.: Predicción_Abril_2026"})

        self.helper = FormHelper(self)
        self.helper.layout = Layout(
            Fieldset(
                "Nueva predicción",
                Row(
                    Column(Field("nombre"), css_class="col-md-6"),
                    Column(Field("entrenamiento"), css_class="col-md-6"),
                ),
                Field("archivo"),
            ),
            Separator("Opciones de salida", css_class="mb-3"),
            Row(
                Column(Field("decimales"), css_class="col-md-4"),
                Column(Field("forzar_no_negativo", label_position="right"), css_class="col-md-8"),
            ),
        )


class PrediccionManualForm(BaseForm):
    entrenamiento = forms.ModelChoiceField(
        label="Modelo (Entrenamiento)",
        queryset=Entrenamiento.objects.filter(estado="DONE").order_by("-finalizado_en", "-id"),
        required=False,
        empty_label="Usar el último entrenamiento completado"
    )

    manual_tipo_grano = forms.ModelChoiceField(
        label="Tipo de grano",
        required=False,
        queryset=TipoGrano.objects.filter(activo=True).order_by("nombre"),
        empty_label="Seleccionar",
    )
    manual_humedad_mp = forms.FloatField(label="Humedad MP", required=True)
    manual_blancura_mp = forms.FloatField(label="Blancura MP", required=True)
    manual_t_desh = forms.FloatField(label="Tiempo deshidratación", required=True)
    manual_temp_desh = forms.FloatField(label="Temp. deshidratación", required=True)
    manual_t_col = forms.FloatField(label="Tiempo coloración", required=True)
    manual_temp_col = forms.FloatField(label="Temp. coloración", required=True)

    decimales = forms.IntegerField(label="Decimales", initial=2, min_value=0, max_value=6)
    forzar_no_negativo = forms.BooleanField(label="Forzar no negativo", required=False, initial=True)

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        self.fields["entrenamiento"].help_text = "Opcional: si no selecciona uno, se usa el último entrenamiento finalizado (DONE)."
        self.fields["decimales"].help_text = "Cantidad de decimales en los resultados generados."
        self.fields["forzar_no_negativo"].help_text = "Si se activa, los valores negativos se ajustan a 0."

        self.fields["manual_humedad_mp"].widget.attrs.update({"placeholder": "Ej.: 12.0"})
        self.fields["manual_blancura_mp"].widget.attrs.update({"placeholder": "Ej.: 45.0"})
        self.fields["manual_t_desh"].widget.attrs.update({"placeholder": "Ej.: 300"})
        self.fields["manual_temp_desh"].widget.attrs.update({"placeholder": "Ej.: 80"})
        self.fields["manual_t_col"].widget.attrs.update({"placeholder": "Ej.: 900"})
        self.fields["manual_temp_col"].widget.attrs.update({"placeholder": "Ej.: 90"})


class OptimizarRecetaForm(BaseForm):
    entrenamiento = forms.ModelChoiceField(
        label="Modelo (Entrenamiento)",
        queryset=Entrenamiento.objects.filter(estado="DONE").order_by("-finalizado_en", "-id"),
        required=False,
        empty_label="Usar el último entrenamiento completado",
    )

    tipo_grano = forms.ModelChoiceField(
        label="Tipo de grano",
        required=False,
        queryset=TipoGrano.objects.filter(activo=True).order_by("nombre"),
        empty_label="Seleccionar",
    )

    humedad_mp = forms.FloatField(label="Humedad MP", required=True)
    blancura_mp = forms.FloatField(label="Blancura MP", required=True)

    objetivo_humedad_pt = forms.FloatField(label="Objetivo Humedad PT", required=True)
    objetivo_blancura_pt = forms.FloatField(label="Objetivo Blancura PT", required=True)

    t_desh_min = forms.FloatField(label="Tiempo deshidratación mínimo", initial=120)
    t_desh_max = forms.FloatField(label="Tiempo deshidratación máximo", initial=600)
    temp_desh_min = forms.FloatField(label="Temp. deshidratación mínima", initial=60)
    temp_desh_max = forms.FloatField(label="Temp. deshidratación máxima", initial=120)
    t_col_min = forms.FloatField(label="Tiempo coloración mínimo", initial=300)
    t_col_max = forms.FloatField(label="Tiempo coloración máximo", initial=1200)
    temp_col_min = forms.FloatField(label="Temp. coloración mínima", initial=70)
    temp_col_max = forms.FloatField(label="Temp. coloración máxima", initial=130)

    iteraciones = forms.IntegerField(label="Iteraciones", initial=2500, min_value=200, max_value=30000)
    decimales = forms.IntegerField(label="Decimales", initial=2, min_value=0, max_value=6)
    forzar_no_negativo = forms.BooleanField(label="Forzar no negativo", required=False, initial=True)

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        self.fields["entrenamiento"].help_text = "Opcional: si no selecciona uno, se usa el último entrenamiento finalizado (DONE)."
        self.fields["tipo_grano"].help_text = "Opcional, pero recomendado para una receta más precisa por tipo de lote."
        self.fields["iteraciones"].help_text = "Más iteraciones mejoran la búsqueda, pero tardan más."

        self.fields["humedad_mp"].widget.attrs.update({"placeholder": "Ej.: 12.0"})
        self.fields["blancura_mp"].widget.attrs.update({"placeholder": "Ej.: 45.0"})
        self.fields["objetivo_humedad_pt"].widget.attrs.update({"placeholder": "Ej.: 10.5"})
        self.fields["objetivo_blancura_pt"].widget.attrs.update({"placeholder": "Ej.: 43.0"})

    def clean(self):
        cleaned = super().clean()
        rangos = [
            ("t_desh_min", "t_desh_max"),
            ("temp_desh_min", "temp_desh_max"),
            ("t_col_min", "t_col_max"),
            ("temp_col_min", "temp_col_max"),
        ]
        for min_key, max_key in rangos:
            min_val = cleaned.get(min_key)
            max_val = cleaned.get(max_key)
            if min_val is None or max_val is None:
                continue
            if float(min_val) >= float(max_val):
                self.add_error(max_key, "Debe ser mayor que el valor mínimo")
        return cleaned
    

