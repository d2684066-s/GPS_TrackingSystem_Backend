# core/apps.py
from django.apps import AppConfig
from django.db.models.signals import post_migrate

def seed_admin(sender, **kwargs):
    from .models import User
    from .utils import make_password  # wait — actually use make_password from django

    from django.contrib.auth.hashers import make_password

    if not User.objects.filter(email="admin@gceits.com").exists():
        User.objects.create(
            name="Admin",
            phone="0000000000",
            email="admin@gceits.com",
            password=make_password("Admin@12345"),
            registration_id="ADMIN001",
            role="admin",
        )
        print("Admin user seeded")


class CoreConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'core'

    def ready(self):
        post_migrate.connect(seed_admin, sender=self)