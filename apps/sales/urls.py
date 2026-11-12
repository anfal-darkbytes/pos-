from django.urls import path
from apps.sales import views

urlpatterns = [
    path("pos", views.pos_terminal, name="pos"),
    path("api/checkout", views.checkout_api, name="checkout_api"),
    path("api/sync/bootstrap", views.sync_bootstrap_api, name="sync_bootstrap_api"),
    path("api/sync/orders", views.sync_orders_api, name="sync_orders_api"),
    path("orders", views.orders_view, name="orders_view"),
    path("orders/<str:order_id>", views.order_detail, name="order_detail"),
    path("invoices", views.invoices_view, name="invoices_view"),
]

