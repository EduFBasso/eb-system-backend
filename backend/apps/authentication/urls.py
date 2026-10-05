from django.urls import include, path

urlpatterns = [
    path('sessions/', include('apps.authentication.urls_sessions')),
    path('token/', include('apps.authentication.urls_tokens')),
    path('register/auth/', include('apps.authentication.urls_professional_registration')),
]
