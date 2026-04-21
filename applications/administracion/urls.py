from django.urls import path

from core.utils import gestionar_modulos
from applications.administracion.views import PanelView, api

from applications.prediccion.urls import prediccion_urls

urls_sistema = (
    {
        "nombre": "Predicción",
        "url": 'prediccion/',
        "sub_urls": prediccion_urls
    },
)

urlpatterns = [
    path('', PanelView.as_view(), name='administracion'),
    path('api/', api, name='api_administracion'),
]

# Construcción de urlpatterns
urlpatterns += [
        path(url['url'] + sub_url['url'], sub_url['vista'], name=sub_url['namespace'])
        for url in urls_sistema
        for sub_url in url['sub_urls'] if sub_url['vista']
]


gestionar_modulos(urls_sistema)