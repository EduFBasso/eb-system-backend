from rest_framework.routers import DefaultRouter
from .inventory import (
    SupplierViewSet,
    ProductViewSet,
    StockMoveViewSet,
    ServiceViewSet,
    ServiceMaterialViewSet,
)

router = DefaultRouter()
router.register(r'suppliers', SupplierViewSet, basename='supplier')
router.register(r'products', ProductViewSet, basename='product')
router.register(r'stock-moves', StockMoveViewSet, basename='stock-move')
router.register(r'services', ServiceViewSet, basename='service')
router.register(r'service-materials', ServiceMaterialViewSet, basename='service-material')

urlpatterns = router.urls
