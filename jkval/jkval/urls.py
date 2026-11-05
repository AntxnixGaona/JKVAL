"""
URL configuration for jkval project.

The `urlpatterns` list routes URLs to views. For more information please see:
    https://docs.djangoproject.com/en/6.1/topics/http/urls/
Examples:
Function views
    1. Add an import:  from my_app import views
    2. Add a URL to urlpatterns:  path('', views.home, name='home')
Class-based views
    1. Add an import:  from other_app.views import Home
    2. Add a URL to urlpatterns:  path('', Home.as_view(), name='home')
Including another URLconf
    1. Import the include() function: from django.urls import include, path
    2. Add a URL to urlpatterns:  path('blog/', include('blog.urls'))
"""
from django.contrib import admin
from django.urls import path
from core import views

urlpatterns = [
    path('admin/', admin.site.urls),
    path('', views.home, name='home'),
    path('fuentes/', views.sources, name='sources'),
    path('privacidad/', views.privacy, name='privacy'),
    path('terminos/', views.terms, name='terms'),
    path('aviso-legal/', views.legal_notice, name='legal_notice'),
    path('guias/', views.guides, name='guides'),
    path('estadisticas/', views.stats, name='stats'),
    path('perfiles/', views.profiles, name='profiles'),
    path('aim-trainer/', views.aim_trainer, name='aim_trainer'),
    path('salud/', views.health, name='health'),
]
