# accounts/management/commands/create_superuser.py
from django.core.management.base import BaseCommand
from accounts.models import User
from django.utils import timezone
import os

class Command(BaseCommand):
    help = 'Creates a Django superuser non-interactively'

    def add_arguments(self, parser):
        parser.add_argument('--email', type=str, help='Email address for the superuser')
        parser.add_argument('--username', type=str, help='Username for the superuser')
        parser.add_argument('--password', type=str, help='Password for the superuser')
        parser.add_argument('--first_name', type=str, help='First name of the superuser')
        parser.add_argument('--last_name', type=str, help='Last name of the superuser')
        parser.add_argument('--non-interactive', action='store_true', help='Run without prompting for input')

    def handle(self, *args, **kwargs):
        # Check if we're in a non-interactive environment
        non_interactive = kwargs.get('non_interactive') or not os.isatty(0)

        # Use environment variables as defaults in non-interactive mode
        if non_interactive:
            email = kwargs.get('email') or os.environ.get('DJANGO_SUPERUSER_EMAIL', 'super@digievolvehub.com')
            username = kwargs.get('username') or os.environ.get('DJANGO_SUPERUSER_USERNAME', 'superadmin')
            password = kwargs.get('password') or os.environ.get('DJANGO_SUPERUSER_PASSWORD', 'changeme123')
            first_name = kwargs.get('first_name') or 'Super'
            last_name = kwargs.get('last_name') or 'Admin'
        else:
            email = kwargs.get('email') or input('Email: ')
            username = kwargs.get('username') or input('Username: ')
            password = kwargs.get('password') or input('Password: ')
            first_name = kwargs.get('first_name') or input('First name (optional): ')
            last_name = kwargs.get('last_name') or input('Last name (optional): ')

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

            # Create the superuser
            superuser = User.objects.create_superuser(
                username=username,
                email=email,
                password=password,
                first_name=first_name,
                last_name=last_name,
                user_type='admin',
                is_student=False,
                admin_type='super_admin',
                is_active_admin=True,
                is_active=True,
                last_admin_login=timezone.now()
            )

            self.stdout.write(
                self.style.SUCCESS(f'Successfully created Django superuser: {username} ({email})')
            )

        except Exception as e:
            self.stdout.write(
                self.style.ERROR(f'Error creating superuser: {str(e)}')
            )