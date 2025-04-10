# accounts/management/commands/ensure_default_admin.py
from django.core.management.base import BaseCommand
from django.contrib.auth.models import User
from accounts.models import DigiEvolveAdmin
import logging

logger = logging.getLogger(__name__)

class Command(BaseCommand):
    help = 'Ensures the default DigiEvolve admin exists'

    def add_arguments(self, parser):
        parser.add_argument(
            '--reset',
            action='store_true',
            help='Reset the password if the admin already exists',
        )

    def handle(self, *args, **options):
        # Default admin credentials
        DEFAULT_ADMIN = {
            'email': 'info@digievolvehub.com',
            'username': 'digievolvehub',
            'password': 'DigievolveHub123$',
            'admin_type': 'super_admin'
        }

        try:
            user, created = User.objects.get_or_create(
                username=DEFAULT_ADMIN['username'],
                defaults={
                    'email': DEFAULT_ADMIN['email'],
                    'is_staff': True,
                    'is_superuser': True
                }
            )

            if created:
                user.set_password(DEFAULT_ADMIN['password'])
                user.save()
                DigiEvolveAdmin.objects.create(
                    user=user,
                    admin_type=DEFAULT_ADMIN['admin_type'],
                    is_active=True
                )
                self.stdout.write(self.style.SUCCESS(
                    f"Created default admin: {DEFAULT_ADMIN['username']}"
                ))
            elif options['reset']:
                user.set_password(DEFAULT_ADMIN['password'])
                user.save()
                self.stdout.write(self.style.SUCCESS(
                    f"Reset password for admin: {DEFAULT_ADMIN['username']}"
                ))
            else:
                self.stdout.write(self.style.SUCCESS(
                    f"Default admin already exists: {DEFAULT_ADMIN['username']}"
                ))

        except Exception as e:
            self.stdout.write(self.style.ERROR(f"Error: {str(e)}"))