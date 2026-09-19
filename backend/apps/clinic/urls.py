from django.urls import include, path

urlpatterns = [
    # Rota canônica única para o núcleo de planos/itens de tratamento (Odonto, Podologia, ...).
    path('treatment/', include('apps.clinic.views.odonto_urls')),
]
