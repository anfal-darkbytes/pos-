from django.urls import path
from apps.analytics import views

urlpatterns = [
    path("", views.dashboard, name="dashboard"),
    path("reports", views.reports_view, name="reports_view"),
]

