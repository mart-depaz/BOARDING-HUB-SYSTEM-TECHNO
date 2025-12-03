# students app views.py


import ast
import base64
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
from django.http import JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.template.loader import render_to_string
from django.utils import timezone
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_http_methods
from properties.models import Post as PropertiesPost
from properties.models import PostReaction as PropertiesPostReaction

# Post models (created below in properties.models)
from .models import Comment, Post, PostImage, PostReaction

ALLOWED_SECTIONS = {"home", "my-home", "survey", "notifications", "trash", "profile"}


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


@login_required
def student_dashboard(request, section="home"):
    """Student Dashboard with neon console sections."""
    try:
        profile = request.user.profile
        if profile.role != "student":
            messages.error(request, "Access denied. Students only.")
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

    # Fetch surveys from ALL schools (so all students see all surveys)
    from core.models import Survey
    surveys = []
    pending_surveys = 0
    try:
        student = request.user.student_profile
        # Get ALL active surveys for students or both recipients
        all_surveys = Survey.objects.filter(
            status='active',
            recipient_type__in=['students', 'both']  # Show surveys for students or both
        ).order_by('-created_at')
        
        # Add a flag indicating if this survey is REQUIRED for this student
        # (only required if the survey's school matches the student's school)
        surveys = []
        for survey in all_surveys:
            is_required = survey.school == student.school if student.school else False
            surveys.append({
                'survey': survey,
                'is_required': is_required,
                'school_name': survey.school.name if survey.school else 'Unknown School'
            })
        
        pending_surveys = len(surveys)
    except Exception:
        surveys = []
        pending_surveys = 0

    # Build a public posts feed (includes others' posts and your own) - ordered by newest first (news feed algorithm)
    try:
        posts_qs = (
            Post.objects.filter(is_public=True)
            .select_related("author")
            .prefetch_related("images", "comments")
            .order_by("-created_at")[:50]
        )

        student_posts = []
        for p in posts_qs:
            liked = False
            if request.user.is_authenticated:
                liked = PostReaction.objects.filter(post=p, user=request.user).exists()
            student_posts.append(
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
                    "comments": [
                        {
                            "author": c.author.get_full_name()
                            if c.author
                            else c.author_name,
                            "timestamp": c.created_at.strftime("%b %d, %Y %H:%M"),
                            "text": c.text,
                        }
                        for c in p.comments.all().order_by("created_at")
                    ],
                    "source": "student",
                    "liked": liked,
                }
            )
    except Exception:
        student_posts = []

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

    student_location_data = [
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
        "student_location_data": student_location_data,
        "boarders_list": boarders_list,
        "student_posts": student_posts,
        "payments": payments,
        "payment_stats": payment_stats,
        "payment_calendar": payment_calendar,
        "notifications_feed": notifications_feed,
        "surveys": surveys,
        "pending_surveys": pending_surveys,
    }

    return render(request, "students/owner_dashboard_students.html", context)


@login_required
def trash_page(request):
    """Trash page for deleted posts with categorization."""
    try:
        profile = request.user.profile
        if profile.role != "student":
            messages.error(request, "Access denied. Students only.")
            return redirect("accounts:login")
    except UserProfile.DoesNotExist:
        messages.error(request, "User profile not found.")
        return redirect("accounts:login")

    context = {
        "section": "trash",
        "user": request.user,
    }

    return render(request, "students/trash_students.html", context)


# ==================== ROOM API ENDPOINTS ====================
import ast
import json

from core.models import Property, Room, RoomImage
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_http_methods


@login_required
@require_http_methods(["GET"])
def api_get_student_properties(request):
    """Get all properties owned by the current user (student-facing API wrapper)."""
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

        # Normalize location: if client sent a JSON/object string, convert to a readable single string
        def normalize_location(loc_raw):
            if not loc_raw:
                return ""
            # If already a string, attempt to parse JSON or Python-literal dict
            if isinstance(loc_raw, str):
                s = loc_raw.strip()
                # try JSON
                try:
                    parsed = json.loads(s)
                except Exception:
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
            # If it's already a dict/object
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

        location = normalize_location(raw_location)

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
            "students/partials/post_card_students.html",
            {
                "post": post_dict,
                "request": request,
                "post_source": "student",
                "is_server": True,
                "show_actions": True,
            },
        )
        # Debug logging to verify server received the create-post request
        try:
            print(
                f"DEBUG: Created student post id={post.id} author={request.user.username if request.user else post.author_name} is_public={post.is_public}"
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
    return render(request, "students/messenger_students.html", context)


@login_required
@require_http_methods(["POST"])
def api_boarding_key(request):
    """API endpoint to retrieve room details by boarding key"""
    import json

    try:
        data = json.loads(request.body)
        boarding_key = data.get("boarding_key", "").strip().upper()

        if not boarding_key:
            return JsonResponse(
                {"success": False, "error": "Boarding key is required"}, status=400
            )

        # Find the room with this boarding key
        room = Room.objects.filter(boarding_key=boarding_key).first()

        if not room:
            return JsonResponse(
                {"success": False, "error": "Invalid boarding key"}, status=404
            )

        # Get owner information
        owner = room.property.owner
        owner_profile = owner.profile

        # Get room images
        images = [img.image.url for img in room.images.all()]

        room_data = {
            "id": room.id,
            "name": room.name,
            "type": room.type,
            "capacity": room.capacity,
            "rate": float(room.rate or 0),
            "is_available": room.is_available,
            "boarding_key": room.boarding_key,
            "images": images,
            "property_address": room.property.address,
            "property_city": room.property.city,
            "property_province": room.property.state,
            "property_zip_code": room.property.zip_code,
        }

        owner_data = {
            "id": owner.id,
            "full_name": owner.get_full_name() or owner.username,
            "email": owner.email,
            "phone": owner_profile.phone if hasattr(owner_profile, "phone") else "",
        }

        return JsonResponse({"success": True, "room": room_data, "owner": owner_data})

    except json.JSONDecodeError:
        return JsonResponse({"success": False, "error": "Invalid JSON"}, status=400)
    except Exception as e:
        return JsonResponse({"success": False, "error": str(e)}, status=500)


@login_required
def profile_setup(request):
    """Profile setup page for students to configure their boarding preferences and profile picture"""
    try:
        profile = request.user.profile
        if profile.role != "student":
            messages.error(request, "Access denied. Students only.")
            return redirect("accounts:login")
    except UserProfile.DoesNotExist:
        messages.error(request, "User profile not found.")
        return redirect("accounts:login")

    if request.method == "POST":
        try:
            # Handle profile picture upload
            if "profile_picture" in request.FILES:
                profile.profile_picture = request.FILES["profile_picture"]

            # Handle boarding location preferences (where they want to stay)
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
            return redirect("students:profile_setup")

        except Exception as e:
            messages.error(request, f"Error updating profile: {str(e)}")

    context = {
        "section": "profile",
        "user": request.user,
        "profile": profile,
        "profile_picture_url": profile.get_profile_photo(),
    }

    return render(request, "students/profile_setup.html", context)


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
        from properties.models import Post as PropertiesPost

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
            Post.objects.filter(is_public=True)
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
            PropertiesPost.objects.filter(is_public=True)
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

        # Combine both querysets and mix recency with randomness
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

        all_posts.sort(key=lambda x: x["created_at"], reverse=True)
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
                    Post.objects.select_related("author")
                    .prefetch_related("images", "comments")
                    .get(id=post_data["id"])
                )
                reaction_model = PostReaction
            else:
                post_obj = (
                    PropertiesPost.objects.select_related("author")
                    .prefetch_related("images", "comments")
                    .get(id=post_data["id"])
                )
                reaction_model = PropertiesPostReaction

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
            post_age = now - post_data["created_at"]

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
                    "created_at": post_data["created_at"].isoformat(),
                    "created_display": timezone.localtime(
                        post_data["created_at"]
                    ).strftime("%b %d, %Y %H:%M"),
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
