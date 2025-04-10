# accounts/management/commands/create_digievolve_admin.py
from django.core.management.base import BaseCommand
from accounts.models import User
from django.utils import timezone
import os

class Command(BaseCommand):
    help = 'Creates a new DigiEvolve admin user for the custom admin dashboard'

    def add_arguments(self, parser):
        # Required arguments
        parser.add_argument('--email', type=str, help='Email address for the admin')
        parser.add_argument('--username', type=str, help='Username for the admin')
        parser.add_argument('--password', type=str, help='Password for the admin')
        parser.add_argument('--admin_type', type=str, choices=['super_admin', 'content_admin', 'support_admin'],
                          help='Type of admin (super_admin, content_admin, or support_admin)')
        parser.add_argument('--first_name', type=str, help='First name of the admin')
        parser.add_argument('--last_name', type=str, help='Last name of the admin')
        parser.add_argument('--phone', type=str, help='Phone number of the admin')
        parser.add_argument('--non-interactive', action='store_true', help='Run without prompting for input')

    def handle(self, *args, **kwargs):
        # Check if we're in a non-interactive environment
        non_interactive = kwargs.get('non_interactive') or not os.isatty(0)

        # Use environment variables as defaults in non-interactive mode
        if non_interactive:
            email = kwargs.get('email') or os.environ.get('DEFAULT_ADMIN_EMAIL', 'admin@digievolvehub.com')
            username = kwargs.get('username') or os.environ.get('DEFAULT_ADMIN_USERNAME', 'digievolvehub')
            password = kwargs.get('password') or os.environ.get('DEFAULT_ADMIN_PASSWORD', 'changeme123')
            admin_type = kwargs.get('admin_type') or 'super_admin'
            first_name = kwargs.get('first_name') or 'DigiEvolve'
            last_name = kwargs.get('last_name') or 'Admin'
            phone = kwargs.get('phone') or ''
        else:
            email = kwargs.get('email') or input('Email: ')
            username = kwargs.get('username') or input('Username: ')
            password = kwargs.get('password') or input('Password: ')
            admin_type = kwargs.get('admin_type') or input('Admin type (super_admin, content_admin, support_admin): ')
            first_name = kwargs.get('first_name') or input('First name: ')
            last_name = kwargs.get('last_name') or input('Last name: ')
            phone = kwargs.get('phone') or input('Phone (optional): ')

        try:
            # Check if user already exists
            if User.objects.filter(email=email).exists():
                self.stdout.write(
                    self.style.WARNING(f'User with email "{email}" already exists, skipping creation')
                )
                return

            if User.objects.filter(username=username).exists():
                self.stdout.write(
                    self.style.WARNING(f'User with username "{username}" already exists, skipping creation')
                )
                return

            # Create the User with admin privileges
            admin = User.objects.create_user(
                username=username,
                email=email,
                password=password,
                first_name=first_name,
                last_name=last_name,
                user_type='admin',
                is_student=False,
                admin_type=admin_type,
                is_active_admin=True,
                phone=phone,
                is_active=True,
                is_staff=True,  # For Django admin access if needed
                last_admin_login=timezone.now()
            )

            self.stdout.write(
                self.style.SUCCESS(f'Successfully created DigiEvolve admin: {username} ({email})')
            )

        except Exception as e:
            self.stdout.write(
                self.style.ERROR(f'Error creating admin user: {str(e)}')
            )