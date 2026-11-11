from django.urls import path
from apps.customers import views

urlpatterns = [
    path("customers", views.customers_view, name="customers_view"),
    path("customers/new", views.customers_new, name="customers_new"),
    path("customers/<str:customer_id>/edit", views.customers_edit, name="customers_edit"),
    path("customers/<str:customer_id>/delete", views.customers_delete, name="customers_delete"),
]

