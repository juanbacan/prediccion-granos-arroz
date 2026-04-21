import numpy as np

from .prediccion_service import _load_model_auto, _predict_auto
from ..tipo_grano_utils import mapa_codigos_tipo_grano, normalizar_tipo_grano


def _expected_features(model):
    if hasattr(model, "n_features_in_"):
        try:
            return int(model.n_features_in_)
        except Exception:
            pass

    input_shape = getattr(model, "input_shape", None)
    if isinstance(input_shape, tuple) and len(input_shape) >= 2 and input_shape[1]:
        try:
            return int(input_shape[1])
        except Exception:
            return None
    return None


def optimizar_receta(entrenamiento, params: dict) -> dict:
    if entrenamiento.estado != "DONE":
        raise ValueError("El entrenamiento seleccionado no está completado (DONE)")

    if not entrenamiento.modelo_y1_file or not entrenamiento.modelo_y2_file:
        raise ValueError("El entrenamiento no tiene modelos guardados")

    modelo_y1 = _load_model_auto(entrenamiento.modelo_y1_file.path)
    modelo_y2 = _load_model_auto(entrenamiento.modelo_y2_file.path)

    scaler_y1 = None
    scaler_y2 = None
    if entrenamiento.scaler_y1_file:
        import joblib
        scaler_y1 = joblib.load(entrenamiento.scaler_y1_file.path)
    if entrenamiento.scaler_y2_file:
        import joblib
        scaler_y2 = joblib.load(entrenamiento.scaler_y2_file.path)

    expected = _expected_features(modelo_y1) or _expected_features(modelo_y2) or 6

    humedad_mp = float(params["humedad_mp"])
    blancura_mp = float(params["blancura_mp"])
    objetivo_h = float(params["objetivo_humedad_pt"])
    objetivo_b = float(params["objetivo_blancura_pt"])

    tipo_grano = params.get("tipo_grano")
    tipo_cod = None
    if tipo_grano:
        catalogo = mapa_codigos_tipo_grano()
        tipo_cod = catalogo.get(normalizar_tipo_grano(tipo_grano.nombre))

    if expected >= 7 and tipo_cod is None:
        raise ValueError("El modelo requiere tipo de grano. Selecciona un tipo válido.")

    ranges = {
        "t_desh": (float(params["t_desh_min"]), float(params["t_desh_max"])),
        "temp_desh": (float(params["temp_desh_min"]), float(params["temp_desh_max"])),
        "t_col": (float(params["t_col_min"]), float(params["t_col_max"])),
        "temp_col": (float(params["temp_col_min"]), float(params["temp_col_max"])),
    }

    iters = int(params.get("iteraciones", 2500))
    decimales = int(params.get("decimales", 2))
    forzar_no_neg = bool(params.get("forzar_no_negativo", True))

    rng = np.random.default_rng(42)
    best = None

    for _ in range(iters):
        t_desh = rng.uniform(*ranges["t_desh"])
        temp_desh = rng.uniform(*ranges["temp_desh"])
        t_col = rng.uniform(*ranges["t_col"])
        temp_col = rng.uniform(*ranges["temp_col"])

        feat = [humedad_mp, blancura_mp, t_desh, temp_desh, t_col, temp_col]
        if expected >= 7:
            feat.append(float(tipo_cod))

        X1 = np.asarray([feat], dtype="float32")
        X2 = np.asarray([feat], dtype="float32")

        if scaler_y1:
            X1 = scaler_y1.transform(X1)
        if scaler_y2:
            X2 = scaler_y2.transform(X2)

        pred_h = float(_predict_auto(modelo_y1, X1)[0])
        pred_b = float(_predict_auto(modelo_y2, X2)[0])

        if forzar_no_neg:
            pred_h = max(0.0, pred_h)
            pred_b = max(0.0, pred_b)

        err_h = pred_h - objetivo_h
        err_b = pred_b - objetivo_b
        loss = (err_h ** 2) + (err_b ** 2)

        if best is None or loss < best["loss"]:
            best = {
                "loss": loss,
                "t_desh": t_desh,
                "temp_desh": temp_desh,
                "t_col": t_col,
                "temp_col": temp_col,
                "pred_h": pred_h,
                "pred_b": pred_b,
                "err_h": err_h,
                "err_b": err_b,
            }

    if not best:
        raise ValueError("No fue posible optimizar la receta")

    return {
        "iteraciones": iters,
        "tipo_grano": tipo_grano.nombre if tipo_grano else "",
        "objetivo_humedad_pt": round(objetivo_h, decimales),
        "objetivo_blancura_pt": round(objetivo_b, decimales),
        "pred_humedad_pt": round(best["pred_h"], decimales),
        "pred_blancura_pt": round(best["pred_b"], decimales),
        "desviacion_humedad": round(best["err_h"], decimales),
        "desviacion_blancura": round(best["err_b"], decimales),
        "tiempo_deshidratacion": round(best["t_desh"], decimales),
        "temp_deshidratacion": round(best["temp_desh"], decimales),
        "tiempo_coloracion": round(best["t_col"], decimales),
        "temp_coloracion": round(best["temp_col"], decimales),
    }
