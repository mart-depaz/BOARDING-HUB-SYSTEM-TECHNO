# students app urls.py

from django.urls import path
from properties import views as property_api_views

from . import views

app_name = "students"

urlpatterns = [
    path("dashboard/", views.student_dashboard, name="student_dashboard"),
    path(
        "dashboard/<str:section>/",
        views.student_dashboard,
        name="student_dashboard_section",
    ),
    path("trash/", views.trash_page, name="trash_page"),
    path("profile-setup/", views.profile_setup, name="profile_setup"),
    # Property API Endpoint (student-facing)
    path(
        "api/properties/",
        views.api_get_student_properties,
        name="api_get_student_properties",
    ),
    # Room API Endpoints
    path("api/rooms/<int:property_id>/", views.api_get_rooms, name="api_get_rooms"),
    path(
        "api/rooms/<int:property_id>/create/",
        views.api_create_room,
        name="api_create_room",
    ),
    path(
        "api/rooms/<int:room_id>/update/", views.api_update_room, name="api_update_room"
    ),
    path(
        "api/rooms/<int:room_id>/delete/", views.api_delete_room, name="api_delete_room"
    ),
    path(
        "api/rooms/<int:room_id>/restore/",
        views.api_restore_room,
        name="api_restore_room",
    ),
    path(
        "api/rooms/<int:property_id>/trashed/",
        views.api_get_trashed_rooms,
        name="api_get_trashed_rooms",
    ),
    # Messaging API Endpoints
    path("api/conversations/", views.api_conversations, name="api_conversations"),
    path(
        "api/conversations/<int:conversation_id>/messages/",
        views.api_conversation_messages,
        name="api_conversation_messages",
    ),
    path(
        "api/send-message/<int:participant_id>/",
        views.api_send_message,
        name="api_send_message",
    ),
    path(
        "api/messages/<int:message_id>/delete/",
        views.api_delete_message,
        name="api_delete_message",
    ),
    # User Profile API Endpoint
    path("api/user/<int:user_id>/", views.api_user_profile, name="api_user_profile"),
    # Full page messenger
    path("messenger/", views.messenger_page, name="messenger_page"),
    # Post API
    path("api/create-post/", views.api_create_post, name="api_create_post"),
    # Boarding Key API
    path("api/boarding-key/", views.api_boarding_key, name="api_boarding_key"),
    # Community Feed API
    path("api/community-feed/", views.api_community_feed, name="api_community_feed"),
    path(
        "api/post/<str:source>/<int:post_id>/toggle-like/",
        property_api_views.api_toggle_like,
        name="api_toggle_like",
    ),
    path(
        "api/post/<str:source>/<int:post_id>/comments/",
        property_api_views.api_post_comments,
        name="api_post_comments",
    ),
    path(
        "api/post/<str:source>/<int:post_id>/edit/",
        property_api_views.api_edit_post,
        name="api_edit_post",
    ),
    path(
        "api/post/<str:source>/<int:post_id>/delete/",
        property_api_views.api_delete_post,
        name="api_delete_post",
    ),
]
