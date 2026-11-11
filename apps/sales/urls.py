from django.urls import path
from apps.sales import views

urlpatterns = [
    path("pos", views.pos_terminal, name="pos"),
    path("api/checkout", views.checkout_api, name="checkout_api"),
    path("orders", views.orders_view, name="orders_view"),
    path("orders/<str:order_id>", views.order_detail, name="order_detail"),
    path("invoices", views.invoices_view, name="invoices_view"),
]

