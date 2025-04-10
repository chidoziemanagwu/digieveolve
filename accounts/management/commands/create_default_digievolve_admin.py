# accounts/management/commands/create_default_digievolve_admin.py
from django.core.management.base import BaseCommand
from django.contrib.auth.models import User
from accounts.models import DigiEvolveAdmin
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
                    'is_staff': False  # No Django admin access
                }
            )

            if created:
                user.set_password(DEFAULT_ADMIN['password'])
                user.save()

                admin = DigiEvolveAdmin.objects.create(
                    user=user,
                    admin_type=DEFAULT_ADMIN['admin_type'],
                    is_active=True,
                    last_login=timezone.now()
                )

                self.stdout.write(
                    self.style.SUCCESS(f'''
Successfully created default DigiEvolve admin:
- Username: {DEFAULT_ADMIN['username']}
- Email: {DEFAULT_ADMIN['email']}
- Admin Type: {admin.get_admin_type_display()}
- Name: {admin.full_name}

This admin can log in at: /accounts/digievolveadmin/login/
'''))

            elif options['reset']:
                user.set_password(DEFAULT_ADMIN['password'])
                user.save()

                admin = DigiEvolveAdmin.objects.get(user=user)
                admin.last_login = timezone.now()
                admin.save()

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