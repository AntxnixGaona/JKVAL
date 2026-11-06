from django.urls import path
from django.views.generic import RedirectView

from . import views

app_name = "core"

urlpatterns = [
    path(
        "favicon.ico",
        RedirectView.as_view(url="/static/img/favicon.svg", permanent=True),
        name="favicon",
    ),
    path("", views.home, name="home"),
    path("fuentes/", views.fuentes, name="fuentes"),
    path("privacidad/", views.privacidad, name="privacidad"),
    path("terminos/", views.terminos, name="terminos"),
    path("aviso-legal/", views.aviso_legal, name="aviso_legal"),
    path("guias/", views.guias, name="guias"),
    path("guias/agentes/<slug:slug>/", views.guia_agente, name="guia_agente"),
    path("guias/mapas/<slug:slug>/", views.guia_mapa, name="guia_mapa"),

    # RUTA DE COMBINACIONES
    path("combinaciones/", views.composiciones, name="composiciones"),

    path("rangos/", views.rangos, name="rangos"),
    path("estadisticas/", views.estadisticas, name="estadisticas"),

    # RUTA DEL BUSCADOR
    path("player/buscar/", views.search_player, name="search_player"),

    # RUTA DEL TRACKER
    path("player/<str:name>/<str:tag>/", views.player_stats_view, name="player_stats"),

    path("aim-trainer/", views.aim_trainer, name="aim_trainer"),
    path("salud/", views.salud, name="salud"),
]
