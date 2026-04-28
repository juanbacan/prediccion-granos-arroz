# prediccion/services/entrenamiento_service.py
# -*- coding: utf-8 -*-
"""
Servicio de entrenamiento para Y1 (Humedad PT) y Y2 (Blancura PT) con un único Excel.
- Lee SIEMPRE la primera hoja del archivo subido en ConjuntoDatos.
- Entrena dos modelos separados (uno por objetivo), calcula métricas y guarda artefactos.
- Rellena campos del modelo Entrenamiento (métricas, archivos, estado, timestamps).
"""
import os
import json
import io
import math
import re
import tempfile
import joblib
import random
import traceback
import unicodedata
import warnings
import numpy as np
import pandas as pd
import matplotlib
matplotlib.use("Agg")  # backend no interactivo para guardar PNG
import matplotlib.pyplot as plt

from django.core.files import File
from django.conf import settings
from django.utils import timezone
from django.db import transaction

from keras import Sequential
from keras.layers import Dense, Input
from keras.optimizers import Adam, SGD
from keras.callbacks import EarlyStopping

from sklearn.model_selection import LeaveOneOut, cross_val_predict
from sklearn.preprocessing import StandardScaler
from sklearn.metrics import mean_squared_error, r2_score
from sklearn.ensemble import RandomForestRegressor
from sklearn.linear_model import Ridge, ElasticNet
from sklearn.pipeline import Pipeline

from ..models import Entrenamiento
from ..tipo_grano_utils import asegurar_tipos_desde_serie, mapa_codigos_tipo_grano, normalizar_tipo_grano


# Nombres de columnas esperados según el Excel de hornos
# Nota: _normalize_columns ya hace strip() en encabezados.
COLS = {
    # Entradas
    "humedad_mp": "HUMEDAD MP",
    "blancura_mp": "BLANCURA MP",
    "tipo": "TIPO DE GRANO",
    "t_desh": "TIEMPO DESHIDRATACION",
    "temp_desh": "TEMP. DESHIDRATACION",
    "t_col": "TIEMPO COLORACION",
    "temp_col": "TEMP. COLORACION",
    # Salidas
    "y1": "HUMEDAD PT",
    "y2": "Blancura PT",
}

# Variantes aceptadas de encabezados (por si cambian mayúsculas, acentos o sufijos).
COL_ALIASES = {
    "humedad_mp": ["Humedad MP (%)", "HUMEDAD MP", "Humedad MP"],
    "blancura_mp": ["Blancura MP", "BLANCURA MP"],
    "tipo": ["TIPO", "TIPO DE GRANO", "Tipo de Grano"],
    "t_desh": ["Tiempo deshidratación", "TIEMPO DESHIDRATACION", "Tiempo deshidratacion"],
    "temp_desh": ["Temperatura deshidratación", "TEMP. DESHIDRATACION", "TEMP DESHIDRATACION"],
    "t_col": ["Tiempo coloración", "TIEMPO COLORACION", "Tiempo coloracion"],
    "temp_col": ["Temperatura coloración", "TEMP. COLORACION", "TEMP COLORACION"],
    "y1": ["Humedad PT (%)", "HUMEDAD PT", "Humedad PT"],
    "y2": ["Blancura PT", "BLANCURA PT"],
}


def _normalize_header_name(text: str) -> str:
    """Normaliza encabezados para comparación flexible (acentos, espacios, signos)."""
    t = str(text or "").strip().lower()
    t = unicodedata.normalize("NFKD", t).encode("ascii", "ignore").decode("ascii")
    t = re.sub(r"[^a-z0-9]+", "", t)
    return t


def _resolve_columns(df: pd.DataFrame) -> dict:
    """Resuelve nombres reales de columnas del Excel usando aliases robustos."""
    # mapa normalizado -> nombre real en dataframe
    normalized_to_real = {}
    for col in df.columns:
        normalized_to_real[_normalize_header_name(col)] = col

    resolved = {}
    required_keys = ["humedad_mp", "blancura_mp", "t_desh", "temp_desh", "t_col", "temp_col", "y1", "y2"]

    for key in required_keys:
        candidates = [COLS[key]] + COL_ALIASES.get(key, [])
        found = None
        for c in candidates:
            norm = _normalize_header_name(c)
            if norm in normalized_to_real:
                found = normalized_to_real[norm]
                break
        if not found:
            disponibles = ", ".join([str(c) for c in df.columns])
            raise ValueError(
                f"No se encontró la columna requerida '{key}'. "
                f"Esperado uno de: {candidates}. Columnas disponibles: {disponibles}"
            )
        resolved[key] = found

    # 'tipo' es opcional
    tipo_found = None
    for c in [COLS["tipo"]] + COL_ALIASES.get("tipo", []):
        norm = _normalize_header_name(c)
        if norm in normalized_to_real:
            tipo_found = normalized_to_real[norm]
            break
    resolved["tipo"] = tipo_found

    return resolved


def _normalize_columns(df: pd.DataFrame, columnas_necesarias: list) -> pd.DataFrame:
    """Normaliza encabezados y convierte columnas esperadas a numérico.
    Soporta formatos como "2.299,39" (punto de miles, coma decimal) y
    otros casos donde los valores lleguen como texto.
    """
    df = df.copy()
    # Normalizar nombres de columnas
    df.columns = df.columns.astype(str).str.strip()

    for c in columnas_necesarias:
        if c not in df.columns:
            continue
        ser = df[c]
        # Si ya es numérico, forzar a numeric para uniformidad
        if pd.api.types.is_numeric_dtype(ser):
            df[c] = pd.to_numeric(ser, errors="coerce")
            continue

        s = ser.astype(str).str.strip()

        # Detectar y convertir formatos con punto de miles y coma decimal
        # Ej: '2.299,39' -> '2299.39'
        if s.str.contains(r"\d+\.\d+,[0-9]+", regex=True).any() or (s.str.contains(r"\.").any() and s.str.contains(r",").any()):
            s = s.str.replace('.', '', regex=True).str.replace(',', '.', regex=False)
        elif s.str.contains(',').any() and not s.str.contains(r"\.").any():
            # '2299,39' -> '2299.39'
            s = s.str.replace(',', '.', regex=False)

        # Eliminar caracteres no numéricos residuales (excepto - y .)
        s = s.str.replace(r"[^0-9\-\.]", '', regex=True)

        df[c] = pd.to_numeric(s, errors="coerce")

    return df


def _asegurar_dir(path_dir: str):
    os.makedirs(path_dir, exist_ok=True)


def _encode_tipo_grano(df: pd.DataFrame, col_name: str) -> pd.DataFrame:
    """Codifica tipo de grano a numérico para usarlo como feature opcional."""
    if col_name not in df.columns:
        return df

    out = df.copy()
    serie = out[col_name].astype(str).map(normalizar_tipo_grano)
    asegurar_tipos_desde_serie(serie)

    mapping = mapa_codigos_tipo_grano()
    mapped = serie.map(mapping)

    # Fallback temporal por lote para no perder filas con valores nuevos atípicos.
    if mapped.isna().any():
        extra_vals = sorted(set(serie[mapped.isna()]))
        start_code = max(mapping.values(), default=0) + 1
        dynamic_map = {v: start_code + i for i, v in enumerate(extra_vals)}
        mapped = mapped.fillna(serie.map(dynamic_map))

    out["tipo_grano_cod"] = pd.to_numeric(mapped, errors="coerce")
    return out


def _set_seed(semilla: int = 42):
    random.seed(semilla)
    np.random.seed(semilla)
    try:
        import tensorflow as tf
        tf.random.set_seed(semilla)
    except Exception:
        pass


def _construir_modelo(input_dim: int, capas: tuple, activacion: str, optimizador: str, lr: float) -> Sequential:
    model = Sequential()
    model.add(Input(shape=(input_dim,)))
    if not capas:
        capas = (128, 64)
    for units in capas:
        model.add(Dense(int(units), activation=activacion))
    model.add(Dense(1, activation="linear"))

    if optimizador == "adam":
        opt = Adam(learning_rate=lr)
    elif optimizador == "sgd":
        opt = SGD(learning_rate=lr, momentum=0.0, nesterov=False)
    else:
        # por si llega algo raro
        opt = Adam(learning_rate=lr)

    model.compile(optimizer=opt, loss="mse")
    return model


def _plot_real_vs_pred(y_true: np.ndarray, y_pred: np.ndarray, titulo: str) -> bytes:
    """Devuelve un PNG en bytes con el scatter real vs pred."""
    fig, ax = plt.subplots(figsize=(6, 6), dpi=120)
    ax.scatter(y_true, y_pred, alpha=0.6)
    # línea y=x
    min_v = min(np.min(y_true), np.min(y_pred))
    max_v = max(np.max(y_true), np.max(y_pred))
    ax.plot([min_v, max_v], [min_v, max_v])
    ax.set_xlabel("Real")
    ax.set_ylabel("Estimado")
    ax.set_title(titulo)
    fig.tight_layout()
    buf = io.BytesIO()
    fig.savefig(buf, format="png")
    plt.close(fig)
    buf.seek(0)
    return buf.read()


def _entrenar_objetivo(
    df: pd.DataFrame,
    feature_cols: list,
    y_col: str,
    params: dict,
    etiqueta: str,
):
    """
    Entrena y evalúa un objetivo (Y1 o Y2) usando LOOCV para pocos datos.
    Devuelve: metrics(dict), modelo_bytes, scaler_bytes, grafico_png_bytes, modelo_ext
    """
    # 1. LIMPIEZA BÁSICA
    df = df.loc[:, ~df.columns.astype(str).str.startswith("Unnamed")]
    columnas_necesarias = feature_cols + [y_col]
    faltantes = [c for c in columnas_necesarias if c not in df.columns]
    if faltantes:
        raise ValueError(f"Faltan columnas requeridas para {etiqueta}: {faltantes}")

    df = _normalize_columns(df, columnas_necesarias)
    data = df[columnas_necesarias].dropna(axis=0, how="any").copy()
    
    if data.empty:
        raise ValueError(f"Después de limpiar NaN, no hay filas para {etiqueta}")

    X = data[feature_cols].values.astype("float32")
    y = data[y_col].values.astype("float32")

    random_state = int(params.get("semilla", 42))

    # 2. ESCALADO (sin fuga de datos: se aplica dentro del pipeline CV)
    usar_escalado = bool(params.get("usar_escalado", True))
    scaler = None

    # 3. SELECCIÓN DE MODELO (RF, Ridge, ElasticNet)
    model_ext = ".pkl"

    base_n = int(params.get("n_estimadores", 30))
    base_depth = int(params.get("max_profundidad", 3))

    n_grid = sorted(set([max(20, base_n // 2), base_n, min(500, base_n * 2), 100, 200]))
    depth_grid = sorted(set([base_depth, max(2, base_depth + 2), max(2, base_depth * 2)]))
    min_leaf_grid = [1, 2]
    ridge_alphas = [0.01, 0.1, 1.0, 10.0, 100.0]
    enet_alphas = [0.001, 0.01, 0.1, 1.0]
    enet_l1_ratios = [0.1, 0.5, 0.9]

    # 4. VALIDACIÓN CRUZADA (LOOCV) y selección por menor MSE
    loo = LeaveOneOut()
    best = None

    candidate_models = []

    for n_est in n_grid:
        for depth in depth_grid:
            for min_leaf in min_leaf_grid:
                candidate_models.append((
                    "random_forest",
                    RandomForestRegressor(
                        n_estimators=n_est,
                        max_depth=depth,
                        min_samples_leaf=min_leaf,
                        random_state=random_state,
                        n_jobs=-1,
                    ),
                    {
                        "modelo": "random_forest",
                        "n_estimadores": n_est,
                        "max_profundidad": depth,
                        "min_samples_leaf": min_leaf,
                        "usar_escalado": usar_escalado,
                    }
                ))

    for alpha in ridge_alphas:
        candidate_models.append((
            "ridge",
            Ridge(alpha=alpha),
            {
                "modelo": "ridge",
                "alpha": alpha,
                "usar_escalado": usar_escalado,
            }
        ))

    for alpha in enet_alphas:
        for l1_ratio in enet_l1_ratios:
            candidate_models.append((
                "elasticnet",
                ElasticNet(alpha=alpha, l1_ratio=l1_ratio, random_state=random_state, max_iter=10000),
                {
                    "modelo": "elasticnet",
                    "alpha": alpha,
                    "l1_ratio": l1_ratio,
                    "usar_escalado": usar_escalado,
                }
            ))

    for _, base_model, model_params in candidate_models:
        estimator = Pipeline([
            ("scaler", StandardScaler()),
            ("model", base_model),
        ]) if usar_escalado else base_model

        with warnings.catch_warnings():
            warnings.simplefilter("ignore")
            y_pred_cv_candidate = cross_val_predict(estimator, X, y, cv=loo)

        if bool(params.get("forzar_no_negativo", True)):
            y_pred_cv_candidate = np.clip(y_pred_cv_candidate, 0, None)

        mse_candidate = float(mean_squared_error(y, y_pred_cv_candidate))
        if best is None or mse_candidate < best["mse"]:
            best = {
                "mse": mse_candidate,
                "estimator": estimator,
                "y_pred_cv": y_pred_cv_candidate,
                "params": model_params,
            }

    if best is None:
        raise ValueError(f"No se pudo seleccionar un modelo para {etiqueta}")

    # 5. ENTRENAMIENTO FINAL (Para guardar el modelo en producción)
    best_estimator = best["estimator"]
    best_estimator.fit(X, y)

    if usar_escalado:
        scaler = best_estimator.named_steps["scaler"]
        model = best_estimator.named_steps["model"]
    else:
        model = best_estimator

    # 6. MÉTRICAS (Usando resultados LOOCV sin redondear)
    y_pred_cv = best["y_pred_cv"]
    if bool(params.get("forzar_no_negativo", True)):
        y_pred_cv = np.clip(y_pred_cv, 0, None)

    mse = float(mean_squared_error(y, y_pred_cv))
    rmse = float(math.sqrt(mse))
    r2 = float(r2_score(y, y_pred_cv))

    metrics = {
        "MSE": mse,
        "RMSE": rmse,
        "R2": r2,
        "best_params": best["params"],
    }

    # 7. SERIALIZACIÓN (GUARDAR MODELO Y SCALER)
    modelo_bytes = io.BytesIO()
    tmp_model_path = None
    try:
        with tempfile.NamedTemporaryFile(suffix=".pkl", delete=False) as tmp_model:
            tmp_model_path = tmp_model.name
        joblib.dump(model, tmp_model_path)
        with open(tmp_model_path, "rb") as fh:
            modelo_bytes.write(fh.read())
    finally:
        if tmp_model_path and os.path.exists(tmp_model_path):
            os.remove(tmp_model_path)
    modelo_bytes.seek(0)

    scaler_bytes = None
    if scaler is not None:
        scaler_bytes = io.BytesIO()
        tmp_scaler_path = None
        try:
            with tempfile.NamedTemporaryFile(suffix=".pkl", delete=False) as tmp_scaler:
                tmp_scaler_path = tmp_scaler.name
            joblib.dump(scaler, tmp_scaler_path)
            with open(tmp_scaler_path, "rb") as fh:
                scaler_bytes.write(fh.read())
        finally:
            if tmp_scaler_path and os.path.exists(tmp_scaler_path):
                os.remove(tmp_scaler_path)
        scaler_bytes.seek(0)

    # 8. GRÁFICO (Comparamos y_real vs y_predichas por LOOCV)
    graf_png = _plot_real_vs_pred(y, y_pred_cv, titulo=f"Real vs Estimado (LOOCV) · {etiqueta}")

    return metrics, modelo_bytes, scaler_bytes, graf_png, model_ext


@transaction.atomic
def ejecutar_entrenamiento(run_id: int, params: dict):
    """
    Orquesta el entrenamiento para Y1 (Humedad PT) y Y2 (Blancura PT)
    leyendo SIEMPRE la primera hoja del Excel.
    Actualiza el objeto Entrenamiento con métricas, archivos y estado.
    """
    run = Entrenamiento.objects.select_for_update().get(id=run_id)
    run.estado = "RUNNING"
    run.iniciado_en = timezone.now()
    run.save(update_fields=["estado", "iniciado_en"])

    resumen_lines = []
    try:
        _set_seed(int(params.get("semilla", 42)))

        # Cargar Excel (primera hoja)
        excel_path = run.dataset.archivo.path
        df = pd.read_excel(excel_path, sheet_name=0)
        # Blindaje extra contra espacios traicioneros en encabezados del Excel.
        df.columns = [str(c).strip() for c in df.columns]

        # Resolver encabezados reales del archivo contra aliases del proyecto.
        cols = _resolve_columns(df)

        # Limpieza: conservar solo lotes con resultados finales disponibles.
        df = _normalize_columns(df, [cols["y1"], cols["y2"]])
        df = df.dropna(subset=[cols["y1"], cols["y2"]])

        # Feature opcional: tipo de grano codificado.
        df = _encode_tipo_grano(df, cols["tipo"])

        # Features comunes para ambos objetivos de hornos.
        feats_horno = [
            cols["humedad_mp"],
            cols["blancura_mp"],
            cols["t_desh"],
            cols["temp_desh"],
            cols["t_col"],
            cols["temp_col"],
        ]
        if "tipo_grano_cod" in df.columns:
            feats_horno.append("tipo_grano_cod")

        # === Y1 (HUMEDAD PT) ===
        m1, modelo1, scaler1, graf1, model_ext_1 = _entrenar_objetivo(
            df=df,
            feature_cols=feats_horno,
            y_col=cols["y1"],
            params=params,
            etiqueta="Humedad Final (PT)",
        )
        run.y1_mse, run.y1_rmse, run.y1_r2 = m1["MSE"], m1["RMSE"], m1["R2"]
        resumen_lines.append(f"Humedad PT -> MSE={m1['MSE']:.6f}, RMSE={m1['RMSE']:.6f}, R²={m1['R2']:.6f}")
        if m1.get("best_params"):
            resumen_lines.append(f"Humedad PT -> mejores hiperparámetros: {m1['best_params']}")

        # Guardar artefactos Y1
        media_root = getattr(settings, "MEDIA_ROOT", "")
        modelos_dir = os.path.join(media_root, "modelos")
        _asegurar_dir(modelos_dir)

        ts_str = timezone.localtime().strftime("%Y%m%d_%H%M%S")
        fname_m1 = f"modelo_y1_{run.id}_{ts_str}{model_ext_1}"
        fname_s1 = f"scaler_y1_{run.id}_{ts_str}.pkl"
        fname_g1 = f"grafico_y1_{run.id}_{ts_str}.png"

        run.modelo_y1_file.save(fname_m1, File(modelo1), save=False)
        if scaler1 is not None:
            run.scaler_y1_file.save(fname_s1, File(scaler1), save=False)
        run.grafico_y1.save(fname_g1, File(io.BytesIO(graf1)), save=False)

        # === Y2 (BLANCURA PT) ===
        m2, modelo2, scaler2, graf2, model_ext_2 = _entrenar_objetivo(
            df=df,
            feature_cols=feats_horno,
            y_col=cols["y2"],
            params=params,
            etiqueta="Blancura Final (PT)",
        )
        run.y2_mse, run.y2_rmse, run.y2_r2 = m2["MSE"], m2["RMSE"], m2["R2"]
        resumen_lines.append(f"Blancura PT -> MSE={m2['MSE']:.6f}, RMSE={m2['RMSE']:.6f}, R²={m2['R2']:.6f}")
        if m2.get("best_params"):
            resumen_lines.append(f"Blancura PT -> mejores hiperparámetros: {m2['best_params']}")

        # Guardar artefactos Y2
        fname_m2 = f"modelo_y2_{run.id}_{ts_str}{model_ext_2}"
        fname_s2 = f"scaler_y2_{run.id}_{ts_str}.pkl"
        fname_g2 = f"grafico_y2_{run.id}_{ts_str}.png"

        run.modelo_y2_file.save(fname_m2, File(modelo2), save=False)
        if scaler2 is not None:
            run.scaler_y2_file.save(fname_s2, File(scaler2), save=False)
        run.grafico_y2.save(fname_g2, File(io.BytesIO(graf2)), save=False)

        # Finalizar
        run.estado = "DONE"
        run.finalizado_en = timezone.now()
        if run.resumen:
            run.resumen += "\n"
        run.resumen += "\n".join(resumen_lines)
        run.save()

    except Exception as e:
        run.estado = "FAILED"
        run.finalizado_en = timezone.now()
        err_text = f"[{timezone.localtime().strftime('%Y-%m-%d %H:%M:%S')}] {type(e).__name__}: {e}"
        tb = traceback.format_exc(limit=3)
        if run.resumen:
            run.resumen += "\n"
        run.resumen += err_text + "\n" + tb
        run.save(update_fields=["estado", "finalizado_en", "resumen"])
