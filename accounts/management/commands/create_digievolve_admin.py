# accounts/management/commands/create_digievolve_admin.py
from django.core.management.base import BaseCommand
from accounts.models import User
from django.utils import timezone

class Command(BaseCommand):
    help = 'Creates a new DigiEvolve admin user for the custom admin dashboard'

    def add_arguments(self, parser):
        # Required arguments
        parser.add_argument('--email', type=str, help='Email address for the admin')
        parser.add_argument('--username', type=str, help='Username for the admin')
        parser.add_argument('--password', type=str, help='Password for the admin')
        parser.add_argument('--admin_type', type=str, choices=['super_admin', 'content_admin', 'support_admin'],
                          help='Type of admin (super_admin, content_admin, or support_admin)')

        # Optional arguments
        parser.add_argument('--first_name', type=str, help='First name of the admin')
        parser.add_argument('--last_name', type=str, help='Last name of the admin')
        parser.add_argument('--phone', type=str, help='Phone number of the admin')

    def handle(self, *args, **kwargs):
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
                    self.style.ERROR(f'User with email "{email}" already exists')
                )
                return

            if User.objects.filter(username=username).exists():
                self.stdout.write(
                    self.style.ERROR(f'User with username "{username}" already exists')
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
                self.style.SUCCESS(f'''
Successfully created DigiEvolve admin:
- Username: {username}
- Email: {email}
- Admin Type: {admin.get_admin_type_display()}
- Name: {admin.full_name if admin.full_name else "Not provided"}
- Phone: {phone if phone else "Not provided"}

This admin can log in at: /accounts/login/
'''))

        except Exception as e:
            self.stdout.write(
                self.style.ERROR(f'Error creating admin user: {str(e)}')
            )