from django.urls import include, path

urlpatterns = [
    path('api/v1/auth/bakery/login/', include('apps.authentication.urls_bakery_auth')),
    path('token/', include('apps.authentication.urls_tokens')),
    path('register/auth/', include('apps.authentication.urls_professional_registration')),
]
