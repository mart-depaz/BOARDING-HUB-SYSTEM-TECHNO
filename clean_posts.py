#!/usr/bin/env python
import os
import sys

import django

# Add the project directory to the Python path
project_path = os.path.dirname(os.path.abspath(__file__))
sys.path.append(project_path)

# Set up Django environment
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "library_root.settings")
django.setup()

from properties.models import Comment as PropertyComment
from properties.models import Post as PropertyPost
from properties.models import PostImage as PropertyPostImage
from properties.models import PostReaction as PropertyPostReaction
from students.models import Comment as StudentComment
from students.models import Post as StudentPost
from students.models import PostImage as StudentPostImage
from students.models import PostReaction as StudentPostReaction


def clean_all_posts():
    """Delete all posts and related data from both students and properties apps"""
    try:
        # Delete all student posts and related data
        student_reactions = StudentPostReaction.objects.all().delete()
        student_comments = StudentComment.objects.all().delete()
        student_images = StudentPostImage.objects.all().delete()
        student_posts = StudentPost.objects.all().delete()

        # Delete all property posts and related data
        property_reactions = PropertyPostReaction.objects.all().delete()
        property_comments = PropertyComment.objects.all().delete()
        property_images = PropertyPostImage.objects.all().delete()
        property_posts = PropertyPost.objects.all().delete()

        print("✅ All posts have been deleted successfully!")
        print(
            f"Deleted: {student_posts[0]} student posts, {property_posts[0]} property posts"
        )
        print(
            f"Deleted: {student_comments[0]} student comments, {property_comments[0]} property comments"
        )
        print(
            f"Deleted: {student_images[0]} student images, {property_images[0]} property images"
        )
        print(
            f"Deleted: {student_reactions[0]} student reactions, {property_reactions[0]} property reactions"
        )

    except Exception as e:
        print(f"❌ Error cleaning posts: {str(e)}")


if __name__ == "__main__":
    clean_all_posts()
