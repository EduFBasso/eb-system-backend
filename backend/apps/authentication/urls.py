from django.urls import include, path

urlpatterns = [
    path('sessions/', include('apps.authentication.urls_sessions')),
    path('token/', include('apps.authentication.urls_tokens')),
]
