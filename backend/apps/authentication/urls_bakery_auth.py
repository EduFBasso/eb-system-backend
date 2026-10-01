from django.urls import path

from apps.authentication.views.views_bakery_auth import BakeryTokenObtainPairView


urlpatterns = [
    path('', BakeryTokenObtainPairView.as_view(), name='bakery_token_obtain_pair'),
]