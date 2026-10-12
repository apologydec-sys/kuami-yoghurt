from django.contrib.auth import views as auth_views
from django.contrib.auth.decorators import login_required
from django.urls import path

from . import views

app_name = "accounts"

urlpatterns = [
    path("register/", views.RegistrationView.as_view(), name="register"),
    path("login/", views.AccountLoginView.as_view(), name="login"),
    path("logout/", auth_views.LogoutView.as_view(next_page="/"), name="logout"),
    path(
        "profile/",
        login_required(views.ProfileView.as_view(), login_url="/accounts/login/"),
        name="profile",
    ),
    path(
        "chats/",
        login_required(views.MyChatsView.as_view(), login_url="/accounts/login/"),
        name="my_chats",
    ),
]
