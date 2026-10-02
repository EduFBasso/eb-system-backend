from django.urls import path

from apps.authentication.services.authentication import EmailTokenObtainPairView
from apps.authentication.services.token_refresh import DeviceBoundTokenRefreshView


urlpatterns = [
    path('', EmailTokenObtainPairView.as_view(), name='token_obtain_pair'),
    path('refresh/', DeviceBoundTokenRefreshView.as_view(), name='token_refresh'),
]