from django.apps import AppConfig
from django.db.models.signals import post_migrate

class AccountsConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'accounts'

    def ready(self):
            # Import signal handlers
            import accounts.signals
            from .signals import create_default_admin
            post_migrate.connect(create_default_admin, sender=self)