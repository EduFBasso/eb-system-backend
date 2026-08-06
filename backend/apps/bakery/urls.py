from rest_framework.routers import DefaultRouter

from apps.bakery.views import (
    BakeryCustomerViewSet,
    CreditLedgerEntryViewSet,
    OrderViewSet,
    ProductViewSet,
)

app_name = "bakery"

router = DefaultRouter()
router.register("customers", BakeryCustomerViewSet, basename="customer")
router.register("products", ProductViewSet, basename="product")
router.register("orders", OrderViewSet, basename="order")
router.register("ledger-entries", CreditLedgerEntryViewSet, basename="ledger-entry")

urlpatterns = router.urls