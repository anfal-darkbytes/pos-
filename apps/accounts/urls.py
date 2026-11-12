from django.urls import path
from apps.accounts import views

urlpatterns = [
    path("profile", views.profile_view, name="profile_view"),
    path("login", views.login_view, name="login"),
    path("logout", views.logout_view, name="logout"),
    path("register", views.register_view, name="register"),
    path("forgot", views.forgot_view, name="forgot"),
    path("reset-password", views.reset_password_view, name="reset_password"),
    path("users", views.users_view, name="users_view"),
    path("users/new", views.users_new, name="users_new"),
    path("users/<str:user_id>/edit", views.users_edit, name="users_edit"),
    path("users/<str:user_id>/delete", views.users_delete, name="users_delete"),
    path("users/<str:user_id>/toggle", views.users_toggle, name="users_toggle"),
]

