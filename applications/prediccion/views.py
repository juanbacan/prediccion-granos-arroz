from django.shortcuts import render
from django.http import JsonResponse
from django.core.files.base import ContentFile
from django.urls import reverse
from django.db.models import Q
from django.db.models.deletion import ProtectedError
from core.views import ViewAdministracionBase, ModelCRUDView
from .models import Entrenamiento, ConjuntoDatos, Prediccion
from .forms import SubirYEntrenarForm, PrediccionNuevaForm, PrediccionManualForm, OptimizarRecetaForm
from core.utils import success_json, error_json, get_redirect_url
from django.utils import timezone
from django.utils.html import format_html
import io
import pandas as pd

from .services.entrenamiento_service import ejecutar_entrenamiento
from .services.prediccion_service import ejecutar_prediccion
from .services.optimizacion_service import optimizar_receta


class EntrenamientosAppView(ModelCRUDView):
    model = Entrenamiento
    form_class = SubirYEntrenarForm
    template_form = "prediccion/form_admin_custom.html"
    list_display = ["id", "nombre", "tipo", "dataset", "estado_badge", "iniciado_fmt", "finalizado_fmt"]

    # Personalizar acciones por fila: eliminar editar, añadir ver detalle
    row_actions = [
        {
            "name": "ver_detalle",
            "label": "Ver detalle",
            "icon": "fa-eye",
            "url": lambda o: f"?action=ver_detalle&id={o.id}",
            'attrs': {
                'data-bs-toggle': 'tooltip',
                'title': 'Ver resultados del entrenamiento',
            },
        },
        {
            "name": "delete",
            "label": "Eliminar",
            "icon": "fa-trash",
            "url": lambda o: f"?action=delete&id={o.id}",
            "modal": True,
            'attrs': {
                'data-bs-toggle': 'tooltip',
                'title': 'Eliminar',
            },
        },
    ]

    def estado_badge(self, obj):
        estado = (obj.estado or "").upper()
        cfg = {
            "DONE": ("success", "Completado"),
            "RUNNING": ("info", "En proceso"),
            "FAILED": ("danger", "Falló"),
            "PENDING": ("warning", "Pendiente"),
        }
        color, text = cfg.get(estado, ("secondary", estado or "N/A"))
        return format_html('<span class="badge badge-{} bg-{}">{}</span>', color, color, text)

    estado_badge.short_description = "Estado"

    def iniciado_fmt(self, obj):
        if not obj.iniciado_en:
            return "-"
        return timezone.localtime(obj.iniciado_en).strftime("%d/%m/%Y %H:%M")

    iniciado_fmt.short_description = "Iniciado"

    def finalizado_fmt(self, obj):
        if not obj.finalizado_en:
            return "-"
        return timezone.localtime(obj.finalizado_en).strftime("%d/%m/%Y %H:%M")

    finalizado_fmt.short_description = "Finalizado"

    def get(self, request, *args, **kwargs):
        """Intercepta acción 'ver_detalle' antes de ejecutar el GET por defecto."""
        action = request.GET.get('action', '')
        if action == 'ver_detalle':
            return self.get_detalle(request, *args, **kwargs)
        return super().get(request, *args, **kwargs)

    def get_detalle(self, request, *args, **kwargs):
        """Renderiza el template de detalle con el objeto Entrenamiento."""
        entrenamiento_id = request.GET.get('id')
        if not entrenamiento_id:
            return JsonResponse({'error': 'ID no proporcionado'}, status=400)
        
        try:
            entrenamiento = Entrenamiento.objects.get(id=entrenamiento_id)
        except Entrenamiento.DoesNotExist:
            return JsonResponse({'error': 'Entrenamiento no encontrado'}, status=404)
        
        context = self.get_context_data(**kwargs)
        context['entrenamiento'] = entrenamiento
        return render(request, 'prediccion/entrenamiento_detalle.html', context)

    def post_add(self, request, context, *args, **kwargs):
        form = self.form_class(request.POST, request.FILES or None)
        if form.is_valid():
            ds = ConjuntoDatos.objects.create(
                nombre=form.cleaned_data["nombre"],
                archivo=form.cleaned_data["archivo"]
            )

            run = Entrenamiento.objects.create(
                nombre=f'Entrenamiento · {ds.nombre}',
                dataset=ds,
                estado="RUNNING",
                iniciado_en=timezone.now()
            )

            params = {
                "excel_path": ds.archivo.path,  # se usará la PRIMERA hoja
                "usar_escalado": form.cleaned_data["usar_escalado"],
                "semilla": form.cleaned_data["semilla"],
                "n_estimadores": form.cleaned_data["n_estimadores"],
                "max_profundidad": form.cleaned_data["max_profundidad"],
                "decimales": form.cleaned_data["decimales"],
                "forzar_no_negativo": form.cleaned_data["forzar_no_negativo"],
            }

            ejecutar_entrenamiento(run_id=run.id, params=params)

            return success_json(url=get_redirect_url(request))
        return error_json(mensaje="Error al guardar el objeto", forms=[form])

    def post_delete(self, request, context, *args, **kwargs):
        entrenamiento_id = request.POST.get('id')
        obj = self.model.objects.get(id=entrenamiento_id)
        try:
            obj.delete()
        except ProtectedError:
            total_predicciones = obj.predicciones.count()
            sufijo = "" if total_predicciones == 1 else "es"
            relacionadas = "relacionada" if total_predicciones == 1 else "relacionadas"
            return error_json(
                mensaje=(
                    f"No se puede eliminar este entrenamiento porque tiene "
                    f"{total_predicciones} prediccion{sufijo} {relacionadas}. "
                    "Elimina primero las predicciones relacionadas."
                )
            )
        return success_json(url=get_redirect_url(request))
    


class PrediccionAppView(ModelCRUDView):
    form_class = PrediccionNuevaForm
    model = Prediccion
    template_form = "prediccion/form_admin_custom.html"
    list_display = ["id", "nombre", "entrenamiento", "estado_badge", "filas_in", "filas_out", "iniciado_fmt", "finalizado_fmt"]

    # Personalizar acciones por fila
    row_actions = [
        {
            "name": "ver_detalle",
            "label": "Ver detalle",
            "icon": "fa-eye",
            "url": lambda o: f"?action=ver_detalle&id={o.id}",
            'attrs': {
                'data-bs-toggle': 'tooltip',
                'title': 'Ver detalles de la predicción',
            },
        },
        {
            "name": "descargar",
            "label": "Descargar",
            "icon": "fa-download",
            "url": lambda o: o.output_file.url if o.output_file else "#",
            "visible_if": lambda o: o.estado == "DONE" and o.output_file,
            'attrs': {
                'data-bs-toggle': 'tooltip',
                'title': 'Descargar archivo de predicciones',
                'download': '',
            },
        },
        {
            "name": "delete",
            "label": "Eliminar",
            "icon": "fa-trash",
            "url": lambda o: f"?action=delete&id={o.id}",
            "modal": True,
            'attrs': {
                'data-bs-toggle': 'tooltip',
                'title': 'Eliminar',
            },
        },
    ]

    def get_queryset(self):
        qs = super().get_queryset()
        # Oculta corridas manuales del listado principal de predicciones por archivo.
        return qs.exclude(Q(es_manual=True) | Q(nombre__startswith="Prediccion_Manual_"))

    def get(self, request, *args, **kwargs):
        """Intercepta acción 'ver_detalle' antes de ejecutar el GET por defecto."""
        action = request.GET.get('action', '')
        if action == 'ver_detalle':
            return self.get_detalle(request, *args, **kwargs)
        return super().get(request, *args, **kwargs)

    def get_detalle(self, request, *args, **kwargs):
        """Renderiza el template de detalle con el objeto Prediccion."""
        pred_id = request.GET.get('id')
        if not pred_id:
            return JsonResponse({'error': 'ID no proporcionado'}, status=400)
        
        try:
            prediccion = Prediccion.objects.select_related('entrenamiento').get(id=pred_id)
        except Prediccion.DoesNotExist:
            return JsonResponse({'error': 'Predicción no encontrada'}, status=404)
        
        context = self.get_context_data(**kwargs)
        context['prediccion'] = prediccion
        return render(request, 'prediccion/prediccion_detalle.html', context)

    def post_add(self, request, context, *args, **kwargs):
        form = self.form_class(request.POST, request.FILES or None)
        if form.is_valid():
            entrenamiento = form.cleaned_data.get("entrenamiento")
            if entrenamiento is None:
                entrenamiento = Entrenamiento.objects.filter(estado="DONE").order_by("-finalizado_en", "-id").first()
            if entrenamiento is None:
                return error_json(mensaje="No hay entrenamientos completados (DONE) disponibles", forms=[form])

            # Crear objeto Prediccion
            pred = Prediccion.objects.create(
                nombre=form.cleaned_data["nombre"],
                entrenamiento=entrenamiento,
                input_file=form.cleaned_data["archivo"],
                es_manual=False,
                estado="RUNNING",
                iniciado_en=timezone.now()
            )

            params = {
                "decimales": form.cleaned_data["decimales"],
                "forzar_no_negativo": form.cleaned_data["forzar_no_negativo"],
            }

            ejecutar_prediccion(pred_id=pred.id, params=params)

            return success_json(url=get_redirect_url(request))
        return error_json(mensaje="Error al guardar la predicción", forms=[form])

    def estado_badge(self, obj):
        estado = (obj.estado or "").upper()
        cfg = {
            "DONE": ("success", "Completado"),
            "RUNNING": ("info", "En proceso"),
            "FAILED": ("danger", "Falló"),
            "PENDING": ("warning", "Pendiente"),
        }
        color, text = cfg.get(estado, ("secondary", estado or "N/A"))
        return format_html('<span class="badge badge-{} bg-{}">{}</span>', color, color, text)

    estado_badge.short_description = "Estado"

    def iniciado_fmt(self, obj):
        if not obj.iniciado_en:
            return "-"
        return timezone.localtime(obj.iniciado_en).strftime("%d/%m/%Y %H:%M")

    iniciado_fmt.short_description = "Iniciado"

    def finalizado_fmt(self, obj):
        if not obj.finalizado_en:
            return "-"
        return timezone.localtime(obj.finalizado_en).strftime("%d/%m/%Y %H:%M")

    finalizado_fmt.short_description = "Finalizado"


class PrediccionManualAppView(ViewAdministracionBase):
    form_class = PrediccionManualForm
    template_form = "prediccion/form_admin_custom.html"

    def get(self, request, *args, **kwargs):
        context = self.get_context_data(**kwargs)
        context["form"] = self.form_class()
        context["action"] = "add"
        return render(request, self.template_form, context)

    def post(self, request, *args, **kwargs):
        form = self.form_class(request.POST, request.FILES or None)
        if form.is_valid():
            entrenamiento = form.cleaned_data.get("entrenamiento")
            if entrenamiento is None:
                entrenamiento = Entrenamiento.objects.filter(estado="DONE").order_by("-finalizado_en", "-id").first()
            if entrenamiento is None:
                return error_json(mensaje="No hay entrenamientos completados (DONE) disponibles", forms=[form])

            manual_row = {
                "TIPO DE GRANO": (
                    form.cleaned_data["manual_tipo_grano"].nombre
                    if form.cleaned_data.get("manual_tipo_grano")
                    else ""
                ),
                "HUMEDAD MP": form.cleaned_data["manual_humedad_mp"],
                "BLANCURA MP": form.cleaned_data["manual_blancura_mp"],
                "TIEMPO DESHIDRATACION": form.cleaned_data["manual_t_desh"],
                "TEMP. DESHIDRATACION": form.cleaned_data["manual_temp_desh"],
                "TIEMPO COLORACION": form.cleaned_data["manual_t_col"],
                "TEMP. COLORACION": form.cleaned_data["manual_temp_col"],
            }
            df_manual = pd.DataFrame([manual_row])
            output = io.BytesIO()
            with pd.ExcelWriter(output, engine="openpyxl") as writer:
                df_manual.to_excel(writer, sheet_name="PrediccionManual", index=False)
            output.seek(0)
            ts = timezone.localtime().strftime("%Y%m%d_%H%M%S")
            input_file = ContentFile(output.read(), name=f"manual_pred_input_{ts}.xlsx")
            nombre_auto = f"Prediccion_Manual_{ts}"

            pred = Prediccion.objects.create(
                nombre=nombre_auto,
                entrenamiento=entrenamiento,
                input_file=input_file,
                es_manual=True,
                estado="RUNNING",
                iniciado_en=timezone.now()
            )

            params = {
                "decimales": form.cleaned_data["decimales"],
                "forzar_no_negativo": form.cleaned_data["forzar_no_negativo"],
                "manual_mode": True,
            }

            ejecutar_prediccion(pred_id=pred.id, params=params)

            pred.refresh_from_db()
            if pred.estado != "DONE":
                return error_json(mensaje="La prediccion manual no pudo completarse", forms=[form])

            if not pred.output_file:
                return error_json(mensaje="No se encontro archivo de salida para la prediccion manual", forms=[form])

            df_out = pd.read_excel(pred.output_file.path, sheet_name=0)
            if "HUMEDAD PT PRED" not in df_out.columns or "BLANCURA PT PRED" not in df_out.columns:
                return error_json(mensaje="No se encontraron columnas de salida esperadas", forms=[form])

            df_valid_pred = df_out[["HUMEDAD PT PRED", "BLANCURA PT PRED"]].dropna(how="all")
            if df_valid_pred.empty:
                return error_json(mensaje="No se obtuvieron valores predichos para mostrar", forms=[form])

            first_row = df_valid_pred.iloc[0]
            humedad_pred = float(first_row["HUMEDAD PT PRED"])
            blancura_pred = float(first_row["BLANCURA PT PRED"])

            return success_json(
                mensaje="Prediccion manual completada",
                resp={
                    "prediccion_id": pred.id,
                    "nombre": pred.nombre,
                    "humedad_pt_pred": humedad_pred,
                    "blancura_pt_pred": blancura_pred,
                    "decimales": int(form.cleaned_data["decimales"]),
                },
            )
        return error_json(mensaje="Error al guardar la predicción manual", forms=[form])


class OptimizarRecetaView(ViewAdministracionBase):
    form_class = OptimizarRecetaForm
    template_form = "prediccion/optimizar_receta_form.html"

    def get(self, request, *args, **kwargs):
        context = self.get_context_data(**kwargs)
        context["form"] = self.form_class()
        context["action"] = "add"
        return render(request, self.template_form, context)

    def post(self, request, *args, **kwargs):
        form = self.form_class(request.POST)
        if not form.is_valid():
            return error_json(mensaje="Revisa los campos de optimización", forms=[form])

        entrenamiento = form.cleaned_data.get("entrenamiento")
        if entrenamiento is None:
            entrenamiento = Entrenamiento.objects.filter(estado="DONE").order_by("-finalizado_en", "-id").first()
        if entrenamiento is None:
            return error_json(mensaje="No hay entrenamientos completados (DONE) disponibles", forms=[form])

        try:
            resultado = optimizar_receta(
                entrenamiento=entrenamiento,
                params={
                    "tipo_grano": form.cleaned_data.get("tipo_grano"),
                    "humedad_mp": form.cleaned_data["humedad_mp"],
                    "blancura_mp": form.cleaned_data["blancura_mp"],
                    "objetivo_humedad_pt": form.cleaned_data["objetivo_humedad_pt"],
                    "objetivo_blancura_pt": form.cleaned_data["objetivo_blancura_pt"],
                    "t_desh_min": form.cleaned_data["t_desh_min"],
                    "t_desh_max": form.cleaned_data["t_desh_max"],
                    "temp_desh_min": form.cleaned_data["temp_desh_min"],
                    "temp_desh_max": form.cleaned_data["temp_desh_max"],
                    "t_col_min": form.cleaned_data["t_col_min"],
                    "t_col_max": form.cleaned_data["t_col_max"],
                    "temp_col_min": form.cleaned_data["temp_col_min"],
                    "temp_col_max": form.cleaned_data["temp_col_max"],
                    "iteraciones": form.cleaned_data["iteraciones"],
                    "decimales": form.cleaned_data["decimales"],
                    "forzar_no_negativo": form.cleaned_data["forzar_no_negativo"],
                },
            )
        except Exception as exc:
            return error_json(mensaje=f"No fue posible optimizar la receta: {exc}", forms=[form])

        return success_json(mensaje="Receta optimizada", resp=resultado)

    