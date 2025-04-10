# accounts/management/commands/create_default_digievolve_admin.py
from django.core.management.base import BaseCommand
from accounts.models import User
from django.utils import timezone
from django.conf import settings

class Command(BaseCommand):
    help = 'Creates the default DigiEvolve admin user'

    def add_arguments(self, parser):
        parser.add_argument(
            '--reset',
            action='store_true',
            help='Reset the password if the admin already exists',
        )

    def handle(self, *args, **options):
        try:
            # Default admin credentials
            DEFAULT_ADMIN = {
                'username': 'digievolvehub',
                'email': 'info@digievolvehub.com',
                'password': 'DigievolveHub123$',
                'first_name': 'DigiEvolve',
                'last_name': 'Admin',
                'admin_type': 'super_admin'
            }

            user, created = User.objects.get_or_create(
                username=DEFAULT_ADMIN['username'],
                defaults={
                    'email': DEFAULT_ADMIN['email'],
                    'first_name': DEFAULT_ADMIN['first_name'],
                    'last_name': DEFAULT_ADMIN['last_name'],
                    'is_staff': True,  # For Django admin access if needed
                    'is_student': False,  # Not a student
                    'user_type': 'admin',
                    'admin_type': DEFAULT_ADMIN['admin_type'],
                    'is_active_admin': True,
                    'is_active': True,
                    'last_admin_login': timezone.now()
                }
            )

            if created:
                user.set_password(DEFAULT_ADMIN['password'])
                user.save()

                self.stdout.write(
                    self.style.SUCCESS(f'''
Successfully created default DigiEvolve admin:
- Username: {DEFAULT_ADMIN['username']}
- Email: {DEFAULT_ADMIN['email']}
- Admin Type: {user.get_admin_type_display()}
- Name: {user.full_name}

This admin can log in at: /accounts/login/
'''))

            elif options['reset']:
                user.set_password(DEFAULT_ADMIN['password'])
                user.is_student = False  # Ensure this is set to False
                user.user_type = 'admin'
                user.admin_type = DEFAULT_ADMIN['admin_type']
                user.is_active_admin = True
                user.last_admin_login = timezone.now()
                user.save()

                self.stdout.write(
                    self.style.SUCCESS(f"Reset password for default admin: {DEFAULT_ADMIN['username']}")
                )

            else:
                self.stdout.write(
                    self.style.SUCCESS(f"Default admin already exists: {DEFAULT_ADMIN['username']}")
                )

        except Exception as e:
            self.stdout.write(
                self.style.ERROR(f"Error: {str(e)}")
            )