# prediccion/services/prediccion_service.py
# -*- coding: utf-8 -*-
"""
Servicio de predicción: carga modelos/scalers de un Entrenamiento DONE,
lee archivo de entrada (Excel/CSV), genera predicciones Y1/Y2 y guarda Excel.

Requisitos:
    pandas, numpy, tensorflow (keras), joblib, openpyxl
"""
import os
import io
import traceback
import re
import unicodedata
import numpy as np
import pandas as pd

from django.core.files import File
from django.conf import settings
from django.utils import timezone
from django.db import transaction

from keras.models import load_model
import joblib

from ..models import Prediccion
from ..tipo_grano_utils import mapa_codigos_tipo_grano, normalizar_tipo_grano


# Nombres de columnas esperados para predicción de hornos
COLS = {
    "humedad_mp": "HUMEDAD MP",
    "blancura_mp": "BLANCURA MP",
    "tipo": "TIPO DE GRANO",
    "t_desh": "TIEMPO DESHIDRATACION",
    "temp_desh": "TEMP. DESHIDRATACION",
    "t_col": "TIEMPO COLORACION",
    "temp_col": "TEMP. COLORACION",
}

COL_ALIASES = {
    "humedad_mp": ["Humedad MP (%)", "HUMEDAD MP", "Humedad MP"],
    "blancura_mp": ["Blancura MP", "BLANCURA MP"],
    "tipo": ["TIPO", "TIPO DE GRANO", "Tipo de Grano"],
    "t_desh": ["Tiempo deshidratación", "TIEMPO DESHIDRATACION", "Tiempo deshidratacion"],
    "temp_desh": ["Temperatura deshidratación", "TEMP. DESHIDRATACION", "TEMP DESHIDRATACION"],
    "t_col": ["Tiempo coloración", "TIEMPO COLORACION", "Tiempo coloracion"],
    "temp_col": ["Temperatura coloración", "TEMP. COLORACION", "TEMP COLORACION"],
}


def _normalize_header_name(text: str) -> str:
    t = str(text or "").strip().lower()
    t = unicodedata.normalize("NFKD", t).encode("ascii", "ignore").decode("ascii")
    t = re.sub(r"[^a-z0-9]+", "", t)
    return t


def _resolve_columns_pred(df: pd.DataFrame) -> dict:
    normalized_to_real = {}
    for col in df.columns:
        normalized_to_real[_normalize_header_name(col)] = col

    resolved = {}
    required_keys = ["humedad_mp", "blancura_mp", "t_desh", "temp_desh", "t_col", "temp_col"]
    for key in required_keys:
        candidates = [COLS[key]] + COL_ALIASES.get(key, [])
        found = None
        for c in candidates:
            norm = _normalize_header_name(c)
            if norm in normalized_to_real:
                found = normalized_to_real[norm]
                break
        if not found:
            raise ValueError(f"Falta columna requerida '{key}'. Esperado uno de: {candidates}")
        resolved[key] = found

    tipo_found = None
    for c in [COLS["tipo"]] + COL_ALIASES.get("tipo", []):
        norm = _normalize_header_name(c)
        if norm in normalized_to_real:
            tipo_found = normalized_to_real[norm]
            break
    resolved["tipo"] = tipo_found

    return resolved


def _encode_tipo_grano_pred(df: pd.DataFrame, col_name: str) -> pd.DataFrame:
    if not col_name or col_name not in df.columns:
        return df
    out = df.copy()
    serie = out[col_name].astype(str).map(normalizar_tipo_grano)
    mapping = mapa_codigos_tipo_grano()
    mapped = serie.map(mapping)
    if mapped.isna().any():
        extra_vals = sorted(set(serie[mapped.isna()]))
        start_code = max(mapping.values(), default=0) + 1
        dyn = {v: start_code + i for i, v in enumerate(extra_vals)}
        mapped = mapped.fillna(serie.map(dyn))
    out["tipo_grano_cod"] = pd.to_numeric(mapped, errors="coerce")
    return out


def _normalize_columns_pred(df: pd.DataFrame, columnas_necesarias: list) -> pd.DataFrame:
    """Normaliza encabezados y convierte columnas a numérico (igual que en entrenamiento_service)."""
    df = df.copy()
    df.columns = df.columns.astype(str).str.strip()

    for c in columnas_necesarias:
        if c not in df.columns:
            continue
        ser = df[c]
        if pd.api.types.is_numeric_dtype(ser):
            df[c] = pd.to_numeric(ser, errors="coerce")
            continue

        s = ser.astype(str).str.strip()

        if s.str.contains(r"\d+\.\d+,[0-9]+", regex=True).any() or (s.str.contains(r"\.").any() and s.str.contains(r",").any()):
            s = s.str.replace(r"\.", '', regex=True).str.replace(',', '.', regex=False)
        elif s.str.contains(',').any() and not s.str.contains(r"\.").any():
            s = s.str.replace(',', '.', regex=False)

        s = s.str.replace(r"[^0-9\-\.]", '', regex=True)
        df[c] = pd.to_numeric(s, errors="coerce")

    return df


def _load_model_auto(model_path: str):
    """Carga modelo .h5 (keras) o .pkl (sklearn/joblib)."""
    low = str(model_path).lower()
    if low.endswith(".h5") or low.endswith(".keras"):
        return load_model(model_path, compile=False)
    return joblib.load(model_path)


def _predict_auto(model, X: np.ndarray) -> np.ndarray:
    """Predicción robusta para modelos keras y sklearn."""
    try:
        pred = model.predict(X, verbose=0)
    except TypeError:
        pred = model.predict(X)
    return np.asarray(pred).reshape(-1)


@transaction.atomic
def ejecutar_prediccion(pred_id: int, params: dict):
    """
    Carga modelos del entrenamiento, lee Excel de entrada, predice Humedad/Blancura y guarda Excel de salida.
    
    params:
        - decimales (int)
        - forzar_no_negativo (bool)
    """
    pred = Prediccion.objects.select_for_update().get(id=pred_id)
    pred.estado = "RUNNING"
    pred.iniciado_en = timezone.now()
    pred.save(update_fields=["estado", "iniciado_en"])

    resumen_lines = []
    try:
        entrenamiento = pred.entrenamiento
        if entrenamiento.estado != "DONE":
            raise ValueError(f"El entrenamiento #{entrenamiento.id} no está completo (estado={entrenamiento.estado})")

        # Cargar modelos y scalers
        if not entrenamiento.modelo_y1_file or not entrenamiento.modelo_y2_file:
            raise ValueError("El entrenamiento no tiene modelos guardados")

        modelo_y1_path = entrenamiento.modelo_y1_file.path
        modelo_y2_path = entrenamiento.modelo_y2_file.path

        modelo_y1 = _load_model_auto(modelo_y1_path)
        modelo_y2 = _load_model_auto(modelo_y2_path)

        scaler_y1 = None
        scaler_y2 = None
        if entrenamiento.scaler_y1_file:
            scaler_y1 = joblib.load(entrenamiento.scaler_y1_file.path)
        if entrenamiento.scaler_y2_file:
            scaler_y2 = joblib.load(entrenamiento.scaler_y2_file.path)

        # Leer archivo de entrada
        input_path = pred.input_file.path
        if input_path.endswith(".csv"):
            df = pd.read_csv(input_path)
        else:
            df = pd.read_excel(input_path, sheet_name=0)

        # Resolver y normalizar columnas de hornos
        cols = _resolve_columns_pred(df)
        feats_horno = [
            cols["humedad_mp"],
            cols["blancura_mp"],
            cols["t_desh"],
            cols["temp_desh"],
            cols["t_col"],
            cols["temp_col"],
        ]

        df = _normalize_columns_pred(df, feats_horno)
        df = _encode_tipo_grano_pred(df, cols.get("tipo"))
        if "tipo_grano_cod" in df.columns:
            feats_horno.append("tipo_grano_cod")

        df_valid = df[feats_horno].dropna(axis=0, how="any")
        if df_valid.empty:
            raise ValueError("No hay filas válidas para predecir tras limpiar NaN en variables de horno")

        # Predicción Humedad (Y1)
        X_y1 = df_valid[feats_horno].values.astype("float32")
        if scaler_y1:
            X_y1 = scaler_y1.transform(X_y1)
        pred_y1_raw = _predict_auto(modelo_y1, X_y1)

        # Predicción Blancura (Y2)
        X_y2 = df_valid[feats_horno].values.astype("float32")
        if scaler_y2:
            X_y2 = scaler_y2.transform(X_y2)
        pred_y2_raw = _predict_auto(modelo_y2, X_y2)

        # Post-proceso
        decimales = int(params.get("decimales", 2))
        forzar_no_neg = bool(params.get("forzar_no_negativo", True))

        if forzar_no_neg:
            pred_y1_raw = np.clip(pred_y1_raw, 0, None)
            pred_y2_raw = np.clip(pred_y2_raw, 0, None)

        pred_y1 = np.round(pred_y1_raw, decimals=decimales)
        pred_y2 = np.round(pred_y2_raw, decimals=decimales)

        # Crear DataFrame de salida
        df_out = df.copy()
        df_out["HUMEDAD PT PRED"] = np.nan
        df_out["BLANCURA PT PRED"] = np.nan

        # Asignar predicciones (alineadas por índices que no tenían NaN)
        df_out.loc[df_valid.index, "HUMEDAD PT PRED"] = pred_y1
        df_out.loc[df_valid.index, "BLANCURA PT PRED"] = pred_y2

        # Guardar Excel de salida
        output_buffer = io.BytesIO()
        with pd.ExcelWriter(output_buffer, engine="openpyxl") as writer:
            df_out.to_excel(writer, sheet_name="Predicciones", index=False)
        output_buffer.seek(0)

        ts_str = timezone.localtime().strftime("%Y%m%d_%H%M%S")
        output_filename = f"prediccion_{pred.id}_{ts_str}.xlsx"
        pred.output_file.save(output_filename, File(output_buffer), save=False)

        # Actualizar contadores
        pred.filas_in = len(df)
        pred.filas_out = len(df_out)

        resumen_lines.append(f"Predicción completada: {pred.filas_out} filas procesadas.")
        resumen_lines.append(f"Humedad PT: {len(df_valid)} predicciones generadas.")
        resumen_lines.append(f"Blancura PT: {len(df_valid)} predicciones generadas.")

        if bool(params.get("manual_mode")) and len(df_valid.index) == 1:
            resumen_lines.append(f"Resultado manual -> Humedad PT: {float(pred_y1[0]):.2f} | Blancura PT: {float(pred_y2[0]):.2f}")

        pred.estado = "DONE"
        pred.finalizado_en = timezone.now()
        if pred.resumen:
            pred.resumen += "\n"
        pred.resumen += "\n".join(resumen_lines)
        pred.save()

    except Exception as e:
        pred.estado = "FAILED"
        pred.finalizado_en = timezone.now()
        err_text = f"[{timezone.localtime().strftime('%Y-%m-%d %H:%M:%S')}] {type(e).__name__}: {e}"
        tb = traceback.format_exc(limit=3)
        if pred.resumen:
            pred.resumen += "\n"
        pred.resumen += err_text + "\n" + tb
        pred.save(update_fields=["estado", "finalizado_en", "resumen"])
