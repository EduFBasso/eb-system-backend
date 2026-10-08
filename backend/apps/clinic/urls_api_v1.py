"""Rotas canônicas do ecossistema Clinic sob o prefixo /api/v1/clinic/.

Espelha o padrão do Bakery (/api/v1/bakery/), isolando as rotas de dados do
Clinic num namespace próprio. As rotas legadas na raiz (/register/, /agenda/,
/inventory/, /clinic/treatment/) continuam montadas em core/urls.py para
compatibilidade com o frontend-clinic durante a migração.
"""
from django.urls import include, path


app_name = "clinic-v1"

urlpatterns = [
    path("register/", include("apps.clinic.urls_registration")),
    path("agenda/", include("apps.clinic.views.agenda_urls")),
    path("inventory/", include("apps.clinic.views.inventory_urls")),
    path("treatment/", include("apps.clinic.views.odonto_urls")),
]
