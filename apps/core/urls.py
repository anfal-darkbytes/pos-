from django.urls import path
from apps.core import views

urlpatterns = [
    path("api/general-settings/", views.api_general_settings, name="api_general_settings_slash"),
    path("api/general-settings", views.api_general_settings, name="api_general_settings"),
    path("api/payment-accounts", views.api_payment_accounts, name="api_payment_accounts"),
    path("settings", views.settings_view, name="settings_view"),
    path("settings/payment-accounts/create", views.payment_account_create, name="payment_account_create"),
    path("settings/payment-accounts/<uuid:account_id>/edit", views.payment_account_edit, name="payment_account_edit"),
    path("settings/payment-accounts/<uuid:account_id>/toggle", views.payment_account_toggle, name="payment_account_toggle"),
    path("settings/payment-accounts/<uuid:account_id>/delete", views.payment_account_delete, name="payment_account_delete"),
]

