from django.urls import path

from apps.authentication.views.views_sessions import (
    sessions_active,
    sessions_revoke,
    sessions_summary,
)


urlpatterns = [
    path('summary', sessions_summary),
    path('active', sessions_active),
    path('revoke', sessions_revoke),
]