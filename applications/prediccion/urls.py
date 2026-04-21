
from .views import *

prediccion_urls = (
    {
        "nombre": "Entrenamientos",
        "url": 'entrenamientos/',
        "vista": EntrenamientosAppView.as_view(),
        "namespace": 'admin_entrenamientos',
    },
    # {
    #     "nombre": "Predicción",
    #     "url": 'predecir/',
    #     "vista": PrediccionAppView.as_view(),
    #     "namespace": 'admin_prediccion',
    # },
    {
        "nombre": "Predicción manual",
        "url": 'predecir-manual/',
        "vista": PrediccionManualAppView.as_view(),
        "namespace": 'admin_prediccion_manual',
    },
    {
        "nombre": "Optimizar receta",
        "url": 'optimizar-receta/',
        "vista": OptimizarRecetaView.as_view(),
        "namespace": 'admin_optimizar_receta',
    }
)
