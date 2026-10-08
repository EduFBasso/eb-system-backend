from django.urls import path
from rest_framework_simplejwt.views import TokenRefreshView

from apps.authentication.services.authentication import EmailTokenObtainPairView


urlpatterns = [
    path('', EmailTokenObtainPairView.as_view(), name='token_obtain_pair'),
    path('refresh/', TokenRefreshView.as_view(), name='token_refresh'),
]