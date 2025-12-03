# properties app views.py

import ast
import base64
import json
import random
import uuid

from core.models import (
    BoardingAssignment,
    MaintenanceRequest,
    Property,
    Room,
    RoomImage,
    UserProfile,
)
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.contrib.auth.models import User
from django.core.files.base import ContentFile
from django.db import models
from django.http import Http404, JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.template.loader import render_to_string
from django.utils import timezone
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_http_methods
from students.models import Comment as StudentsComment
from students.models import Post as StudentsPost
from students.models import PostReaction as StudentsPostReaction

# Post models (created below in properties.models)
from .models import Comment, Post, PostImage, PostReaction

ALLOWED_SECTIONS = {"home", "my-home", "survey", "notifications", "trash", "profile"}

SOURCE_MODEL_MAP = {
    "property": (Post, Comment, PostReaction),
    "student": (StudentsPost, StudentsComment, StudentsPostReaction),
}


def _normalize_source(source):
    key = (source or "").lower()
    if key not in SOURCE_MODEL_MAP:
        raise Http404("Invalid post source")
    return key, SOURCE_MODEL_MAP[key]


def _format_location_value(value):
    if not value:
        return ""
    if isinstance(value, dict):
        parts = [
            value.get("province") or value.get("state") or "",
            value.get("city") or "",
            value.get("barangay") or "",
            value.get("address") or value.get("display_name") or "",
        ]
        return ", ".join([str(p).strip() for p in parts if p and str(p).strip()])
    if isinstance(value, str):
        stripped = value.strip()
        try:
            loaded = json.loads(stripped)
            if isinstance(loaded, dict):
                return _format_location_value(loaded)
        except Exception:
            try:
                loaded = ast.literal_eval(stripped)
                if isinstance(loaded, dict):
                    return _format_location_value(loaded)
            except Exception:
                pass
        return stripped
    return str(value)


def _serialize_comment(comment, request_user=None):
    author_profile_picture = ""
    if (
        comment.author
        and hasattr(comment.author, "profile")
        and comment.author.profile.profile_picture
    ):
        author_profile_picture = comment.author.profile.profile_picture.url

    is_author = False
    if request_user and comment.author:
        is_author = comment.author.id == request_user.id

    return {
        "id": comment.id,
        "author": comment.author.get_full_name()
        if comment.author
        else (comment.author_name or "Anonymous"),
        "author_profile_picture": author_profile_picture,
        "text": comment.text,
        "timestamp": timezone.localtime(comment.created_at).strftime("%b %d, %Y %H:%M"),
        "created_at": comment.created_at.isoformat(),
        "likes": getattr(comment, "likes", 0),
        "liked": False,  # TODO: Check if request_user liked this comment
        "is_author": is_author,
    }


def _serialize_post(post_obj, source_key):
    author_profile_picture = ""
    if (
        post_obj.author
        and hasattr(post_obj.author, "profile")
        and post_obj.author.profile.profile_picture
    ):
        author_profile_picture = post_obj.author.profile.profile_picture.url

    return {
        "id": post_obj.id,
        "author_name": post_obj.author.get_full_name()
        if post_obj.author
        else (post_obj.author_name or "Anonymous"),
        "author_profile_picture": author_profile_picture,
        "message": post_obj.message,
        "location": _format_location_value(post_obj.location),
        "timestamp": timezone.localtime(post_obj.created_at).strftime(
            "%b %d, %Y %H:%M"
        ),
        "created_at": post_obj.created_at.isoformat(),
        "images": [img.image.url for img in post_obj.images.all()],
        "likes": post_obj.likes,
        "source": source_key,
    }


@login_required
def owner_dashboard(request, section="home"):
    """Property Owner Dashboard with neon console sections."""
    try:
        profile = request.user.profile
        if profile.role != "property_owner":
            messages.error(request, "Access denied. Property owners only.")
            return redirect("accounts:login")
    except UserProfile.DoesNotExist:
        messages.error(request, "User profile not found.")
        return redirect("accounts:login")

    section = (section or "home").lower()
    if section not in ALLOWED_SECTIONS:
        section = "home"

    properties = Property.objects.filter(owner=request.user)
    total_properties = properties.count()

    active_tenants = BoardingAssignment.objects.filter(
        property__owner=request.user, status="active"
    ).select_related("student__user", "property")

    maintenance_requests = MaintenanceRequest.objects.filter(
        property__owner=request.user
    ).order_by("-created_at")[:10]

    rent_collected = 0  # Placeholder until financial tracking is implemented

    boarders_list = []
    for assignment in active_tenants:
        student_user = assignment.student.user
        boarders_list.append(
            {
                "name": student_user.get_full_name() or student_user.username,
                "property": assignment.property.address,
                "room": assignment.property.property_id,
                "status": assignment.status.title(),
                "contact": getattr(student_user.profile, "phone", "")
                if hasattr(student_user, "profile")
                else "",
            }
        )

    # Build a public posts feed (includes others' posts and your own) - ordered by newest first (news feed algorithm)
    try:
        posts_qs = (
            Post.objects.filter(is_public=True)
            .select_related("author")
            .prefetch_related("images", "comments")
            .order_by("-created_at")[:50]
        )

        owner_posts = []
        for p in posts_qs:
            liked = False
            if request.user.is_authenticated:
                liked = PostReaction.objects.filter(post=p, user=request.user).exists()
            owner_posts.append(
                {
                    "id": p.id,
                    "likes": p.likes,
                    "author": p.author,  # Pass author object for profile picture access
                    "author_id": p.author.id if p.author else None,
                    "author_full_name": p.author.get_full_name()
                    if p.author
                    else (p.author_name or "User"),
                    "author_name": p.author.username
                    if p.author
                    else (p.author_name or "User"),
                    "timestamp": p.created_at,
                    "message": p.message,
                    "location": p.location,
                    "images": [img.image.url for img in p.images.all()],
                    "comments": [],  # Remove inline comments - only show in modal
                    "source": "property",
                    "liked": liked,
                }
            )
    except Exception:
        owner_posts = []

    payments = [
        {
            "reference": "PMT-2101",
            "boarder": "Ava Lim",
            "property": "Neon Suite 2F",
            "due_date": "Dec 05, 2025",
            "amount": 7500,
            "status": "Paid",
            "method": "GCash",
        },
        {
            "reference": "PMT-2102",
            "boarder": "Marcus Dela Cruz",
            "property": "Skyline Pod C12",
            "due_date": "Dec 05, 2025",
            "amount": 8200,
            "status": "Pending",
            "method": "Bank Transfer",
        },
        {
            "reference": "PMT-2103",
            "boarder": "Faith Santos",
            "property": "Neon Suite 3C",
            "due_date": "Nov 28, 2025",
            "amount": 7000,
            "status": "Overdue",
            "method": "Cash",
        },
    ]

    payment_stats = {
        "collected": sum(p["amount"] for p in payments if p["status"] == "Paid"),
        "pending": sum(p["amount"] for p in payments if p["status"] == "Pending"),
        "overdue": sum(p["amount"] for p in payments if p["status"] == "Overdue"),
        "upcoming_due": payments[0]["due_date"] if payments else "N/A",
    }

    payment_calendar = [
        {"date": "Dec 05", "label": "Cycle Billing", "status": "upcoming"},
        {"date": "Dec 15", "label": "Utility Sync", "status": "upcoming"},
        {"date": "Dec 28", "label": "Rent Settlement", "status": "reminder"},
    ]

    notifications_feed = [
        {
            "title": req.title,
            "priority": req.get_priority_display(),
            "created_at": req.created_at,
            "description": req.description,
        }
        for req in maintenance_requests
    ]

    owner_location_data = [
        {
            "id": prop.property_id,
            "name": prop.name or prop.property_id,
            "address": prop.address,
            "city": prop.city or "",
            "province": prop.state or "",
            "zip_code": prop.zip_code or "",
            "latitude": float(prop.latitude) if prop.latitude is not None else None,
            "longitude": float(prop.longitude) if prop.longitude is not None else None,
            "status": prop.get_status_display(),
        }
        for prop in properties
    ]

    context = {
        "section": section,
        "total_properties": total_properties,
        "active_tenants": active_tenants,
        "maintenance_requests": maintenance_requests,
        "rent_collected": rent_collected,
        "properties": properties,
        "owner_location_data": owner_location_data,
        "boarders_list": boarders_list,
        "owner_posts": owner_posts,
        "payments": payments,
        "payment_stats": payment_stats,
        "payment_calendar": payment_calendar,
        "notifications_feed": notifications_feed,
    }

    return render(request, "properties/owner_dashboard.html", context)


@login_required
def trash_page(request):
    """Trash page for deleted posts with categorization."""
    try:
        profile = request.user.profile
        if profile.role != "property_owner":
            messages.error(request, "Access denied. Property owners only.")
            return redirect("accounts:login")
    except UserProfile.DoesNotExist:
        messages.error(request, "User profile not found.")
        return redirect("accounts:login")

    context = {
        "section": "trash",
        "user": request.user,
    }

    return render(request, "properties/trash.html", context)


# ==================== ROOM API ENDPOINTS ====================
import ast
import json

from core.models import Property, Room, RoomImage
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_http_methods


@login_required
@require_http_methods(["GET"])
def api_get_owner_properties(request):
    """Get all properties owned by the current user (used by frontend to fetch property_id on page load)"""
    try:
        properties = Property.objects.filter(owner=request.user).values(
            "id", "property_id", "name", "address"
        )
        props_list = list(properties)
        return JsonResponse({"success": True, "properties": props_list})
    except Exception as e:
        return JsonResponse({"success": False, "error": str(e)}, status=500)


@login_required
@require_http_methods(["GET"])
def api_get_rooms(request, property_id):
    """Get all rooms for a property"""
    try:
        prop = Property.objects.get(id=property_id, owner=request.user)
    except Property.DoesNotExist:
        return JsonResponse({"error": "Property not found"}, status=404)

    from core.models import BoardingAssignment

    rooms = Room.objects.filter(prop=prop, is_trashed=False).prefetch_related(
        "images", "student_assignments"
    )
    room_data = []

    for room in rooms:
        images = [img.image.url for img in room.images.all()]
        image_objects = [
            {"id": img.id, "url": img.image.url} for img in room.images.all()
        ]

        # Get active students assigned to this room
        active_students = []
        for assignment in room.student_assignments.filter(status="active"):
            student = assignment.student
            active_students.append(
                {
                    "id": student.id,
                    "name": student.user.get_full_name() or student.user.username,
                    "student_id": student.student_id,
                    "email": student.user.email,
                    "phone": student.user.profile.phone
                    if hasattr(student.user, "profile")
                    else "",
                    "department": student.department.name
                    if student.department
                    else "N/A",
                    "year_level": student.year_level or "N/A",
                }
            )

        room_data.append(
            {
                "id": room.id,
                "name": room.name,
                "type": room.room_type,
                "capacity": room.capacity,
                "rate": float(room.monthly_rate) if room.monthly_rate else None,
                "images": images,
                "image_objects": image_objects,
                "image_count": room.get_image_count(),
                "students": active_students,
                "occupancy": len(active_students),
            }
        )

    return JsonResponse({"rooms": room_data}, safe=False)


@login_required
@require_http_methods(["POST"])
def api_create_post(request):
    """Create a Post from AJAX (supports images). Returns HTML snippet for immediate insertion."""
    try:
        content = request.POST.get("content", "").strip()
        raw_location = (
            request.POST.get("location", "").strip()
            if "location" in request.POST
            else ""
        )

        # Use location from user profile if no location provided
        location = raw_location
        if not location and request.user.profile:
            profile = request.user.profile
            location_parts = []
            if profile.boarding_region:
                location_parts.append(profile.boarding_region)
            if profile.boarding_province:
                location_parts.append(profile.boarding_province)
            if profile.boarding_city:
                location_parts.append(profile.boarding_city)
            if profile.boarding_barangay:
                location_parts.append(f"Brgy. {profile.boarding_barangay}")
            if profile.boarding_address:
                location_parts.append(profile.boarding_address)
            location = ", ".join(location_parts) if location_parts else ""

        # Normalize location: if client sent a JSON/object string, convert to a readable single string
        def normalize_location(loc_raw):
            if not loc_raw:
                return ""
            if isinstance(loc_raw, str):
                s = loc_raw.strip()
                try:
                    parsed = json.loads(s)
                except json.JSONDecodeError:
                    try:
                        parsed = ast.literal_eval(s)
                    except Exception:
                        parsed = None
                if isinstance(parsed, dict):
                    parts = [
                        parsed.get("province") or parsed.get("state") or "",
                        parsed.get("city") or "",
                        parsed.get("barangay") or "",
                        parsed.get("address") or parsed.get("display_name") or "",
                    ]
                    parts = [p for p in parts if p and str(p).strip()]
                    return ", ".join(parts)
                return s
            if isinstance(loc_raw, dict):
                parts = [
                    loc_raw.get("province") or loc_raw.get("state") or "",
                    loc_raw.get("city") or "",
                    loc_raw.get("barangay") or "",
                    loc_raw.get("address") or loc_raw.get("display_name") or "",
                ]
                parts = [p for p in parts if p and str(p).strip()]
                return ", ".join(parts)
            return str(loc_raw)

        location = normalize_location(location)

        post = Post.objects.create(
            author=request.user,
            author_name=request.user.get_full_name(),
            message=content,
            location=location,
            is_public=True,
        )

        # Handle uploaded files
        files = request.FILES.getlist("images")
        for f in files:
            PostImage.objects.create(post=post, image=f)

        # Render the post HTML using the partial
        post_dict = {
            "id": post.id,
            "likes": post.likes,
            "author_id": post.author.id if post.author else None,
            "author_full_name": post.author.get_full_name()
            if post.author
            else post.author_name,
            "author_name": post.author.username if post.author else post.author_name,
            "timestamp": post.created_at,
            "message": post.message,
            "location": post.location,
            "images": [img.image.url for img in post.images.all()],
            "comments": [],
        }

        html = render_to_string(
            "properties/partials/post_card.html",
            {
                "post": post_dict,
                "request": request,
                "post_source": "property",
                "is_server": True,
                "show_actions": True,
            },
        )
        # Debug logging to verify server received the create-post request
        try:
            print(
                f"DEBUG: Created property post id={post.id} author={request.user.username if request.user else post.author_name} is_public={post.is_public}"
            )
        except Exception:
            pass
        return JsonResponse({"success": True, "post_html": html})
    except Exception as e:
        return JsonResponse({"success": False, "error": str(e)}, status=500)


@login_required
@require_http_methods(["POST"])
def api_create_room(request, property_id):
    """Create a new room"""
    try:
        prop = Property.objects.get(id=property_id, owner=request.user)
    except Property.DoesNotExist:
        return JsonResponse({"error": "Property not found"}, status=404)

    try:
        data = json.loads(request.POST.get("data", "{}"))
    except:
        return JsonResponse({"error": "Invalid JSON data"}, status=400)

    try:
        room = Room.objects.create(
            prop=prop,
            name=data.get("name", "Unnamed Room"),
            room_type=data.get("type", "single"),
            capacity=int(data.get("capacity", 1)),
            monthly_rate=float(data.get("rate", 0)) if data.get("rate") else None,
        )

        # Handle image uploads
        for file_key in request.FILES:
            if file_key.startswith("image_"):
                image_file = request.FILES[file_key]
                RoomImage.objects.create(room=room, image=image_file)

        images = [img.image.url for img in room.images.all()]
        return JsonResponse(
            {
                "success": True,
                "room": {
                    "id": room.id,
                    "name": room.name,
                    "type": room.room_type,
                    "capacity": room.capacity,
                    "rate": float(room.monthly_rate) if room.monthly_rate else None,
                    "images": images,
                    "image_count": room.get_image_count(),
                },
            }
        )
    except Exception as e:
        return JsonResponse({"error": str(e)}, status=400)


@login_required
@require_http_methods(["POST"])
def api_update_room(request, room_id):
    """Update a room"""
    try:
        room = Room.objects.get(id=room_id, prop__owner=request.user)
    except Room.DoesNotExist:
        return JsonResponse({"error": "Room not found"}, status=404)

    try:
        data = json.loads(request.POST.get("data", "{}"))
    except:
        return JsonResponse({"error": "Invalid JSON data"}, status=400)

    try:
        room.name = data.get("name", room.name)
        room.room_type = data.get("type", room.room_type)
        room.capacity = int(data.get("capacity", room.capacity))
        room.monthly_rate = (
            float(data.get("rate", room.monthly_rate))
            if data.get("rate")
            else room.monthly_rate
        )
        room.save()

        # Handle new image uploads
        new_image_count = 0
        for file_key in request.FILES:
            if file_key.startswith("image_"):
                image_file = request.FILES[file_key]
                RoomImage.objects.create(room=room, image=image_file)
                new_image_count += 1

        print(
            f"DEBUG: Updated room {room.id}, added {new_image_count} new images, total files in request: {len(request.FILES)}"
        )

        # Handle image deletions
        deleted_images = data.get("deleted_images", [])
        if deleted_images:
            RoomImage.objects.filter(id__in=deleted_images, room=room).delete()

        images = [img.image.url for img in room.images.all()]
        print(f"DEBUG: Room {room.id} now has {len(images)} images: {images}")
        return JsonResponse(
            {
                "success": True,
                "room": {
                    "id": room.id,
                    "name": room.name,
                    "type": room.room_type,
                    "capacity": room.capacity,
                    "rate": float(room.monthly_rate) if room.monthly_rate else None,
                    "images": images,
                    "image_count": room.get_image_count(),
                },
            }
        )
    except Exception as e:
        print(f"DEBUG: Error updating room: {str(e)}")
        return JsonResponse({"error": str(e)}, status=400)


@login_required
@require_http_methods(["POST"])
def api_delete_room(request, room_id):
    """Soft delete (trash) a room"""
    try:
        room = Room.objects.get(id=room_id, prop__owner=request.user)
    except Room.DoesNotExist:
        return JsonResponse({"error": "Room not found"}, status=404)

    room.is_trashed = True
    room.save()

    return JsonResponse({"success": True, "message": "Room moved to trash"})


@login_required
@require_http_methods(["POST"])
def api_restore_room(request, room_id):
    """Restore a trashed room"""
    try:
        room = Room.objects.get(id=room_id, prop__owner=request.user, is_trashed=True)
    except Room.DoesNotExist:
        return JsonResponse({"error": "Trashed room not found"}, status=404)

    room.is_trashed = False
    room.save()

    return JsonResponse({"success": True, "message": "Room restored"})


@login_required
@require_http_methods(["GET"])
def api_get_trashed_rooms(request, property_id):
    """Get all trashed rooms for a property"""
    try:
        prop = Property.objects.get(id=property_id, owner=request.user)
    except Property.DoesNotExist:
        return JsonResponse({"error": "Property not found"}, status=404)

    rooms = Room.objects.filter(prop=prop, is_trashed=True).prefetch_related("images")
    room_data = []

    for room in rooms:
        images = [img.image.url for img in room.images.all()]
        room_data.append(
            {
                "id": room.id,
                "name": room.name,
                "type": room.room_type,
                "capacity": room.capacity,
                "rate": float(room.monthly_rate) if room.monthly_rate else None,
                "images": images,
                "image_count": room.get_image_count(),
            }
        )

    return JsonResponse({"rooms": room_data}, safe=False)


# Messaging APIs
@login_required
@require_http_methods(["GET"])
def api_conversations(request):
    """Get all conversations for the current user"""
    from core.models import Conversation

    conversations = (
        Conversation.objects.filter(
            models.Q(participant1=request.user) | models.Q(participant2=request.user)
        )
        .prefetch_related("messages")
        .order_by("-updated_at")
    )

    conv_data = []
    for conv in conversations:
        other_user = conv.get_other_user(request.user)
        last_message = conv.get_last_message()
        unread_count = conv.get_unread_count(request.user)

        conv_data.append(
            {
                "id": conv.id,
                "participant": {
                    "id": other_user.id,
                    "name": other_user.get_full_name() or other_user.username,
                    "username": other_user.username,
                    "avatar": other_user.profile.get_profile_photo()
                    if hasattr(other_user, "profile")
                    else None,
                },
                "last_message": {
                    "content": last_message.content[:100] if last_message else "",
                    "sender_id": last_message.sender.id if last_message else None,
                    "created_at": last_message.created_at.isoformat()
                    if last_message
                    else None,
                    "is_read": last_message.is_read if last_message else True,
                }
                if last_message
                else None,
                "unread_count": unread_count,
                "updated_at": conv.updated_at.isoformat(),
            }
        )

    return JsonResponse({"conversations": conv_data})


@login_required
@require_http_methods(["GET"])
def api_conversation_messages(request, conversation_id):
    """Get all messages in a conversation"""
    from core.models import Conversation, Message

    # Find conversation where user is either participant1 or participant2
    try:
        conv = Conversation.objects.filter(
            models.Q(id=conversation_id, participant1=request.user)
            | models.Q(id=conversation_id, participant2=request.user)
        ).first()
        if not conv:
            return JsonResponse({"error": "Conversation not found"}, status=404)
    except:
        return JsonResponse({"error": "Conversation not found"}, status=404)

    messages_qs = Message.objects.filter(conversation=conv).select_related("sender")

    # Mark messages as read
    Message.objects.filter(conversation=conv).exclude(sender=request.user).update(
        is_read=True
    )

    messages_data = []
    for msg in messages_qs:
        messages_data.append(
            {
                "id": msg.id,
                "sender_id": msg.sender.id,
                "sender_name": msg.sender.get_full_name() or msg.sender.username,
                "sender_avatar": msg.sender.profile.get_profile_photo()
                if hasattr(msg.sender, "profile")
                else None,
                "content": msg.content,
                "is_read": msg.is_read,
                "created_at": msg.created_at.isoformat(),
            }
        )

    return JsonResponse({"messages": messages_data})


@login_required
@require_http_methods(["POST"])
def api_send_message(request, participant_id):
    """Send a message to a user"""
    import json

    from core.models import Conversation, Message
    from django.db.models import Q

    try:
        recipient = User.objects.get(id=participant_id)
    except User.DoesNotExist:
        return JsonResponse({"error": "User not found"}, status=404)

    if recipient == request.user:
        return JsonResponse({"error": "Cannot message yourself"}, status=400)

    try:
        data = json.loads(request.POST.get("data", "{}"))
        content = data.get("content", "").strip()
    except:
        content = ""

    if not content:
        return JsonResponse({"error": "Message cannot be empty"}, status=400)

    # Get or create conversation (order-independent)
    conv, created = Conversation.objects.get_or_create(
        participant1=min(request.user, recipient, key=lambda u: u.id),
        participant2=max(request.user, recipient, key=lambda u: u.id),
    )

    # Create message
    message = Message.objects.create(
        conversation=conv, sender=request.user, content=content
    )

    return JsonResponse(
        {
            "success": True,
            "message": {
                "id": message.id,
                "sender_id": message.sender.id,
                "content": message.content,
                "created_at": message.created_at.isoformat(),
            },
            "conversation_id": conv.id,
        }
    )


@login_required
@require_http_methods(["DELETE"])
def api_delete_message(request, message_id):
    """Delete a message (soft delete)"""
    from core.models import Message

    try:
        message = Message.objects.get(id=message_id, sender=request.user)
        message.delete()
        return JsonResponse({"success": True})
    except Message.DoesNotExist:
        return JsonResponse(
            {"error": "Message not found or not authorized"}, status=404
        )


@login_required
@require_http_methods(["GET"])
def api_user_profile(request, user_id):
    """Get user profile information"""
    try:
        user = User.objects.get(id=user_id)
        profile = UserProfile.objects.get(user=user)

        return JsonResponse(
            {
                "success": True,
                "user": {
                    "id": user.id,
                    "full_name": user.get_full_name() or user.username,
                    "email": user.email,
                    "department": profile.department or "",
                    "year_level": profile.year_level or "",
                    "phone": getattr(profile, "phone", "") or "",
                },
            }
        )
    except User.DoesNotExist:
        return JsonResponse({"error": "User not found"}, status=404)
    except UserProfile.DoesNotExist:
        # Return basic user info if profile doesn't exist
        return JsonResponse(
            {
                "success": True,
                "user": {
                    "id": user.id,
                    "full_name": user.get_full_name() or user.username,
                    "email": user.email,
                    "department": "",
                    "year_level": "",
                    "phone": "",
                },
            }
        )


@login_required
def messenger_page(request):
    """Render a full-page messenger UI. Optional ?user_id= will open that conversation."""
    user_id = request.GET.get("user_id")
    context = {
        "initial_user_id": user_id,
    }
    return render(request, "properties/messenger.html", context)


@login_required
def profile_setup(request):
    """Profile setup page for property owners to configure their boarding house locations and profile picture"""
    try:
        profile = request.user.profile
        if profile.role != "property_owner":
            messages.error(request, "Access denied. Property owners only.")
            return redirect("accounts:login")
    except UserProfile.DoesNotExist:
        messages.error(request, "User profile not found.")
        return redirect("accounts:login")

    if request.method == "POST":
        try:
            # Handle profile picture upload
            if "profile_picture" in request.FILES:
                profile.profile_picture = request.FILES["profile_picture"]

            # Handle boarding house location (where their property is located)
            profile.boarding_region = request.POST.get("boarding_region", "").strip()
            profile.boarding_province = request.POST.get(
                "boarding_province", ""
            ).strip()
            profile.boarding_city = request.POST.get("boarding_city", "").strip()
            profile.boarding_barangay = request.POST.get(
                "boarding_barangay", ""
            ).strip()
            profile.boarding_address = request.POST.get("boarding_address", "").strip()

            # Update phone number if provided
            if "phone" in request.POST:
                profile.phone = request.POST.get("phone", "").strip()

            profile.save()

            messages.success(request, "Profile updated successfully!")
            return redirect("properties:profile_setup")

        except Exception as e:
            messages.error(request, f"Error updating profile: {str(e)}")

    context = {
        "section": "profile",
        "user": request.user,
        "profile": profile,
        "profile_picture_url": profile.get_profile_photo(),
    }

    return render(request, "properties/profile_setup.html", context)


@login_required
@require_http_methods(["GET"])
def api_community_feed(request):
    """API endpoint to get community news feed - all public posts from all users (students + properties)"""
    try:
        import json
        from datetime import timedelta

        from core.models import UserProfile
        from django.db.models import CharField, Count, Value
        from django.db.models.functions import Concat
        from django.utils import timezone
        from students.models import Post as StudentsPost

        # Get page for pagination
        page = int(request.GET.get("page", 1))
        limit = int(request.GET.get("limit", 10))
        offset = (page - 1) * limit

        # Get location filters - Only allow Caraga region
        filter_region = request.GET.get("region", "").strip()
        filter_province = request.GET.get("province", "").strip()
        filter_city = request.GET.get("city", "").strip()
        filter_barangay = request.GET.get("barangay", "").strip()

        # Restrict region to Caraga only
        if filter_region and "caraga" not in filter_region.lower():
            filter_region = ""

        # Get all public posts from both students and properties
        student_posts = (
            StudentsPost.objects.filter(is_public=True)
            .select_related("author")
            .prefetch_related("images", "comments")
            .annotate(
                engagement_score=Count("comments"),
                user_type=Value("student", output_field=CharField()),
            )
            .values(
                "id",
                "author_id",
                "author_name",
                "message",
                "location",
                "likes",
                "created_at",
                "engagement_score",
                "user_type",
            )
        )

        property_posts = (
            Post.objects.filter(is_public=True)
            .select_related("author")
            .prefetch_related("images", "comments")
            .annotate(
                engagement_score=Count("comments"),
                user_type=Value("property_owner", output_field=CharField()),
            )
            .values(
                "id",
                "author_id",
                "author_name",
                "message",
                "location",
                "likes",
                "created_at",
                "engagement_score",
                "user_type",
            )
        )

        # Combine both querysets and mix by recency and randomness
        all_posts = list(student_posts) + list(property_posts)

        # Apply location filters if provided (Caraga region focus)
        if filter_region or filter_province or filter_city or filter_barangay:
            filtered_posts = []
            for post_data in all_posts:
                location_str = str(post_data.get("location", "") or "").lower()

                # Try to parse as JSON first, then as string
                location_obj = None
                try:
                    if location_str.startswith("{"):
                        location_obj = json.loads(location_str)
                except:
                    pass

                matches = True

                # Check region (must be Caraga if specified)
                if filter_region:
                    region_match = False
                    if location_obj:
                        region_val = str(location_obj.get("region", "") or "").lower()
                        if "caraga" in region_val:
                            region_match = True
                    elif "caraga" in location_str:
                        region_match = True

                    if not region_match:
                        matches = False

                # Check province (within Caraga)
                if matches and filter_province:
                    province_match = False
                    if location_obj:
                        province_val = str(
                            location_obj.get("province", "") or ""
                        ).lower()
                        if filter_province.lower() in province_val:
                            province_match = True
                    elif filter_province.lower() in location_str:
                        province_match = True

                    if not province_match:
                        matches = False

                # Check city/municipality
                if matches and filter_city:
                    city_match = False
                    if location_obj:
                        city_val = str(location_obj.get("city", "") or "").lower()
                        if filter_city.lower() in city_val:
                            city_match = True
                    elif filter_city.lower() in location_str:
                        city_match = True

                    if not city_match:
                        matches = False

                # Check barangay
                if matches and filter_barangay:
                    barangay_match = False
                    if location_obj:
                        barangay_val = str(
                            location_obj.get("barangay", "") or ""
                        ).lower()
                        if filter_barangay.lower() in barangay_val:
                            barangay_match = True
                    elif filter_barangay.lower() in location_str:
                        barangay_match = True

                    if not barangay_match:
                        matches = False

                if matches:
                    filtered_posts.append(post_data)

            all_posts = filtered_posts

        # Sort by created_at, handling both datetime objects and strings
        def get_sort_key(post):
            created = post.get("created_at")
            if isinstance(created, str):
                from django.utils.dateparse import parse_datetime

                parsed = parse_datetime(created)
                return parsed if parsed else timezone.now()
            return created if created else timezone.now()

        all_posts.sort(key=get_sort_key, reverse=True)
        latest_slice = all_posts[:5]
        remaining_slice = all_posts[5:]
        random.shuffle(remaining_slice)
        mixed_posts = latest_slice + remaining_slice

        # Apply pagination
        paginated_posts = mixed_posts[offset : offset + limit]

        posts_data = []
        for post_data in paginated_posts:
            # Determine which model to get full post from
            source_key = (
                "student" if post_data["user_type"] == "student" else "property"
            )
            if source_key == "student":
                post_obj = (
                    StudentsPost.objects.select_related("author")
                    .prefetch_related("images", "comments")
                    .get(id=post_data["id"])
                )
                reaction_model = StudentsPostReaction
            else:
                post_obj = (
                    Post.objects.select_related("author")
                    .prefetch_related("images", "comments")
                    .get(id=post_data["id"])
                )
                reaction_model = PostReaction

            # Get images
            images = [img.image.url for img in post_obj.images.all()]

            # Get recent comments (limit to 3)
            comments = post_obj.comments.all().order_by("-created_at")[:3]
            comments_data = [
                {
                    "id": c.id,
                    "author": c.author_name
                    or (c.author.get_full_name() if c.author else "Anonymous"),
                    "text": c.text,
                    "timestamp": c.created_at.strftime("%Y-%m-%d %H:%M:%S"),
                }
                for c in comments
            ]

            # Calculate post age for display
            now = timezone.now()
            created_at = post_data["created_at"]
            if isinstance(created_at, str):
                from django.utils.dateparse import parse_datetime

                created_at = parse_datetime(created_at) or timezone.now()
            post_age = now - created_at

            if post_age.days > 0:
                time_display = f"{post_age.days}d ago"
            elif post_age.seconds > 3600:
                time_display = f"{post_age.seconds // 3600}h ago"
            elif post_age.seconds > 60:
                time_display = f"{post_age.seconds // 60}m ago"
            else:
                time_display = "just now"

            # Get author role
            author_role = "Student"
            if post_data["user_type"] == "property_owner":
                author_role = "Property Owner"

            # Try to get user role from UserProfile
            if post_data["author_id"]:
                try:
                    user_profile = UserProfile.objects.get(
                        user_id=post_data["author_id"]
                    )
                    if user_profile.role == "student":
                        author_role = "Student"
                    elif user_profile.role == "property_owner":
                        author_role = "Property Owner"
                except:
                    pass

            liked = False
            if request.user.is_authenticated:
                liked = reaction_model.objects.filter(
                    post=post_obj, user=request.user
                ).exists()

            # Get author profile picture
            author_profile_picture = ""
            if post_obj.author:
                try:
                    profile = UserProfile.objects.get(user=post_obj.author)
                    if profile.profile_picture:
                        author_profile_picture = profile.profile_picture.url
                except UserProfile.DoesNotExist:
                    pass

            posts_data.append(
                {
                    "id": post_data["id"],
                    "author_id": post_data["author_id"],
                    "author_name": post_data["author_name"] or "Anonymous",
                    "author_profile_picture": author_profile_picture,
                    "author_role": author_role,
                    "message": post_data["message"],
                    "location": _format_location_value(post_data["location"]) or "",
                    "likes": post_obj.likes,
                    "images": images,
                    "comments": comments_data,
                    "comments_count": post_obj.comments.count(),
                    "timestamp": time_display,
                    "created_at": created_at.isoformat()
                    if hasattr(created_at, "isoformat")
                    else str(created_at),
                    "created_display": timezone.localtime(created_at).strftime(
                        "%b %d, %Y %H:%M"
                    )
                    if hasattr(created_at, "strftime")
                    else str(created_at),
                    "user_type": post_data["user_type"],
                    "source": source_key,
                    "liked": liked,
                }
            )

        total_count = len(mixed_posts)

        return JsonResponse(
            {
                "success": True,
                "posts": posts_data,
                "page": page,
                "limit": limit,
                "total_count": total_count,
                "has_more": offset + limit < total_count,
            }
        )

    except Exception as e:
        import traceback

        traceback.print_exc()
        return JsonResponse({"success": False, "error": str(e)}, status=500)


@login_required
@require_http_methods(["POST"])
def api_toggle_like(request, source, post_id):
    source_key, (PostModel, CommentModel, ReactionModel) = _normalize_source(source)
    post = get_object_or_404(PostModel, id=post_id)

    reaction, created = ReactionModel.objects.get_or_create(
        post=post, user=request.user
    )
    if not created:
        reaction.delete()
        liked = False
    else:
        liked = True

    post.likes = ReactionModel.objects.filter(post=post).count()
    post.save(update_fields=["likes"])

    return JsonResponse({"success": True, "liked": liked, "likes": post.likes})


@login_required
@require_http_methods(["GET", "POST"])
def api_post_comments(request, source, post_id):
    source_key, (PostModel, CommentModel, ReactionModel) = _normalize_source(source)
    post = get_object_or_404(
        PostModel.objects.select_related("author").prefetch_related("images"),
        id=post_id,
    )

    if request.method == "GET":
        comments_qs = (
            CommentModel.objects.filter(post=post)
            .select_related("author", "author__profile")
            .order_by("created_at")
        )
        serialized = [
            _serialize_comment(comment, request.user) for comment in comments_qs
        ]
        return JsonResponse(
            {
                "success": True,
                "post": _serialize_post(post, source_key),
                "comments": serialized,
                "comment_count": len(serialized),
            }
        )

    try:
        payload = json.loads(request.body or "{}")
    except json.JSONDecodeError:
        payload = {}
    text = payload.get("text", "").strip()
    if not text:
        return JsonResponse(
            {"success": False, "error": "Comment text is required."}, status=400
        )

    comment = CommentModel.objects.create(
        post=post,
        author=request.user,
        author_name=request.user.get_full_name() or request.user.username,
        text=text,
    )

    total_comments = CommentModel.objects.filter(post=post).count()
    return JsonResponse(
        {
            "success": True,
            "comment": _serialize_comment(comment, request.user),
            "comment_count": total_comments,
        }
    )


@login_required
@require_http_methods(["PUT", "PATCH"])
def api_edit_post(request, source, post_id):
    """Edit a post (only by author)"""
    source_key, (PostModel, CommentModel, ReactionModel) = _normalize_source(source)
    post = get_object_or_404(PostModel, id=post_id)

    if post.author != request.user:
        return JsonResponse({"success": False, "error": "Not authorized"}, status=403)

    try:
        payload = json.loads(request.body or "{}")
    except json.JSONDecodeError:
        return JsonResponse({"success": False, "error": "Invalid JSON"}, status=400)

    if "message" in payload:
        post.message = payload["message"].strip()

    if "location" in payload:
        raw_location = payload["location"]
        if isinstance(raw_location, dict):
            parts = [
                raw_location.get("province") or raw_location.get("state") or "",
                raw_location.get("city") or "",
                raw_location.get("barangay") or "",
                raw_location.get("address") or raw_location.get("display_name") or "",
            ]
            parts = [p for p in parts if p and str(p).strip()]
            post.location = ", ".join(parts)
        else:
            post.location = str(raw_location).strip()

    post.save()

    post_dict = {
        "id": post.id,
        "likes": post.likes,
        "author": post.author,
        "author_id": post.author.id if post.author else None,
        "author_full_name": post.author.get_full_name()
        if post.author
        else post.author_name,
        "author_name": post.author.username if post.author else post.author_name,
        "timestamp": post.created_at,
        "message": post.message,
        "location": post.location,
        "images": [img.image.url for img in post.images.all()],
        "comments": [],
        "source": source_key,
    }

    template_name = (
        "students/partials/post_card_students.html"
        if source_key == "student"
        else "properties/partials/post_card.html"
    )
    html = render_to_string(
        template_name,
        {
            "post": post_dict,
            "request": request,
            "post_source": source_key,
            "is_server": True,
            "show_actions": True,
        },
    )

    return JsonResponse({"success": True, "post_html": html})


@login_required
@require_http_methods(["DELETE"])
def api_delete_post(request, source, post_id):
    """Permanently delete a post (only by author)"""
    source_key, (PostModel, CommentModel, ReactionModel) = _normalize_source(source)
    post = get_object_or_404(PostModel, id=post_id)

    if post.author != request.user:
        return JsonResponse({"success": False, "error": "Not authorized"}, status=403)

    # Permanently delete the post
    post.delete()

    return JsonResponse({"success": True, "message": "Post deleted successfully"})
