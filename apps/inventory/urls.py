from django.urls import path
from apps.inventory import views

urlpatterns = [
    path("products", views.products_view, name="products_view"),
    path("products/new", views.products_new, name="products_new"),
    path("products/<str:product_id>/edit", views.products_edit, name="products_edit"),
    path("products/<str:product_id>/delete", views.products_delete, name="products_delete"),
    path("categories/new", views.categories_new, name="categories_new"),
    path("categories/<str:cat_id>/delete", views.categories_delete, name="categories_delete"),
    path("inventory", views.inventory_view, name="inventory_view"),
    path("inventory/<str:product_id>/adjust", views.inventory_adjust, name="inventory_adjust"),
    path("api/products/by-barcode/<str:barcode>", views.product_by_barcode, name="product_by_barcode"),
]

