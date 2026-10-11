from django.urls import path

from . import views

app_name = "chat"

urlpatterns = [
    path("chat/", views.ChatStartView.as_view(), name="start"),
    path("chat/<int:pk>/", views.ChatWindowView.as_view(), name="window"),
    path("chat/<int:pk>/send/", views.SendMessageView.as_view(), name="send"),
    path("chat/<int:pk>/poll/", views.PollMessagesView.as_view(), name="poll"),
]
