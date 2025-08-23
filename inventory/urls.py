"""
URLs for inventory app API views.
Frontend layer has been removed - these URLs only provide API functionality.
"""

from django.urls import path

from . import views

app_name = "inventory"

urlpatterns = [
    # API endpoints for dashboard and monitoring
    path("api/dashboard/", views.dashboard_api, name="dashboard_api"),
    path("api/monitoring/", views.monitoring_api, name="monitoring_api"),
    
    # API endpoints for inventory items
    path("api/inventory/", views.InventoryItemsAPI.as_view(), name="inventory_api"),
    path("api/inventory/expiring/", views.expiring_items_api, name="expiring_items_api"),
    path("api/inventory/low-stock/", views.low_stock_items_api, name="low_stock_items_api"),
    path(
        "api/inventory/location/<str:location>/",
        views.inventory_by_location_api,
        name="inventory_by_location_api",
    ),
    
    # API endpoints for products
    path("api/products/", views.ProductsAPI.as_view(), name="products_api"),
    path(
        "api/products/<int:pk>/", views.ProductDetailAPI.as_view(), name="product_detail_api"
    ),
    
    # API endpoints for receipts
    path("api/receipts/", views.ReceiptsAPI.as_view(), name="receipts_api"),
    path(
        "api/receipts/<int:pk>/", views.ReceiptDetailAPI.as_view(), name="receipt_detail_api"
    ),
    path("api/receipts/recent/", views.recent_receipts_api, name="recent_receipts_api"),
    path("api/receipts/upload/", views.upload_receipt_api, name="upload_receipt_api"),
    path(
        "api/receipts/<int:receipt_id>/status/",
        views.receipt_processing_status,
        name="receipt_processing_status",
    ),
    path(
        "api/receipts/<int:receipt_id>/correct/",
        views.correct_receipt_data,
        name="correct_receipt_data",
    ),
    
    # API endpoint for monitoring data
    path(
        "api/monitoring/data/",
        views.get_monitoring_data,
        name="get_monitoring_data",
    ),
    
    # API endpoint for categories
    path("api/categories/", views.CategoriesAPI.as_view(), name="categories_api"),
]
