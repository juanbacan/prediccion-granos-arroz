import re
import unicodedata

from .models import TipoGrano


def normalizar_tipo_grano(valor: str) -> str:
    texto = str(valor or "").strip().lower()
    texto = unicodedata.normalize("NFKD", texto).encode("ascii", "ignore").decode("ascii")
    texto = re.sub(r"\s+", " ", texto)
    return texto


def mostrar_tipo_grano(clave: str) -> str:
    return str(clave or "").strip().title()


def asegurar_tipos_desde_serie(serie):
    if serie is None:
        return

    existentes = {t.clave_normalizada for t in TipoGrano.objects.all()}
    max_codigo = TipoGrano.objects.order_by("-codigo").values_list("codigo", flat=True).first() or 0

    nuevas_claves = []
    for val in serie.dropna().astype(str):
        clave = normalizar_tipo_grano(val)
        if not clave or clave in existentes:
            continue
        existentes.add(clave)
        nuevas_claves.append(clave)

    for idx, clave in enumerate(sorted(nuevas_claves), start=1):
        TipoGrano.objects.create(
            nombre=mostrar_tipo_grano(clave),
            clave_normalizada=clave,
            codigo=max_codigo + idx,
            activo=True,
        )


def mapa_codigos_tipo_grano() -> dict:
    return {
        item["clave_normalizada"]: item["codigo"]
        for item in TipoGrano.objects.filter(activo=True).values("clave_normalizada", "codigo")
    }
