from django.urls import path

from apps.authentication.views.views_bakery_auth import (
    BakeryAdminLoginView,
    BakeryCustomerLoginView,
)


urlpatterns = [
    path('admin/', BakeryAdminLoginView.as_view(), name='bakery_admin_login'),
    path('customer/', BakeryCustomerLoginView.as_view(), name='bakery_customer_login'),
]
