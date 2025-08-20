"""
URLs for inventory app views.
Part of Prompt 8: Dashboard i widoki użytkownika.
"""

from django.urls import path

from . import views

app_name = "inventory"

urlpatterns = [
    # Dashboard
    path("", views.dashboard, name="dashboard"),
    path("monitoring/", views.monitoring_dashboard, name="monitoring_dashboard"),
    # Inventory items
    path("inventory/", views.InventoryListView.as_view(), name="inventory_list"),
    path("inventory/expiring/", views.expiring_items, name="expiring_items"),
    path("inventory/low-stock/", views.low_stock_items, name="low_stock_items"),
    path(
        "inventory/location/<str:location>/",
        views.inventory_by_location,
        name="inventory_by_location",
    ),
    # Products
    path("products/", views.ProductListView.as_view(), name="product_list"),
    path(
        "products/<int:pk>/", views.ProductDetailView.as_view(), name="product_detail"
    ),
    # Receipts
    path("receipts/", views.ReceiptListView.as_view(), name="receipt_list"),
    path(
        "receipts/<int:pk>/", views.ReceiptDetailView.as_view(), name="receipt_detail"
    ),
    path("receipts/recent/", views.recent_receipts, name="recent_receipts"),
    path("receipts/upload/", views.upload_receipt, name="upload_receipt"),
    path(
        "receipts/<int:receipt_id>/status/",
        views.receipt_processing_status,
        name="receipt_processing_status",
    ),
    path(
        "receipts/<int:receipt_id>/review/",
        views.receipt_review,
        name="receipt_review",
    ),
    path(
        "api/receipts/<int:receipt_id>/correct/",
        views.correct_receipt_data,
        name="correct_receipt_data",
    ),
    path(
        "api/monitoring_data/",
        views.get_monitoring_data,
        name="get_monitoring_data",
    ),
    # Categories
    path("categories/", views.CategoryListView.as_view(), name="category_list"),
]
