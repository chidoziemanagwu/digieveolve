# accounts/signals.py
import logging
from django.db.models.signals import post_migrate
from django.dispatch import receiver
from .models import User
from django.conf import settings
from django.db import transaction

logger = logging.getLogger(__name__)

DEFAULT_ADMIN = {
    'email': settings.DEFAULT_ADMIN_EMAIL,
    'username': settings.DEFAULT_ADMIN_USERNAME,
    'password': settings.DEFAULT_ADMIN_PASSWORD,
    'admin_type': 'super_admin'
}

# We no longer need the post_save signal for creating student profiles
# since we're using a custom User model that includes all the necessary fields

@receiver(post_migrate)
def create_default_admin(sender, **kwargs):
    """Create default admin user after migration"""
    # Only run this for the accounts app
    if sender.name != 'accounts':
        return

    try:
        # Check if the default admin already exists
        if not User.objects.filter(username=DEFAULT_ADMIN['username']).exists():
            with transaction.atomic():
                # Create user with admin privileges
                user = User.objects.create_user(
                    username=DEFAULT_ADMIN['username'],
                    email=DEFAULT_ADMIN['email'],
                    password=DEFAULT_ADMIN['password']
                )

                # Set user as staff and superuser
                user.is_staff = True
                user.is_superuser = True

                # Set admin-specific fields
                user.admin_type = DEFAULT_ADMIN['admin_type']
                user.is_active_admin = True
                user.user_type = 'admin'

                user.save()

                logger.info(f"Created default admin: {DEFAULT_ADMIN['username']}")
        else:
            logger.info("Default admin already exists")

    except Exception as e:
        logger.error(f"Error creating default admin: {str(e)}")