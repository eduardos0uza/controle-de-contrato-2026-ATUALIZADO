from django.apps import AppConfig
from django.db.models.signals import post_migrate


class AdminPanelConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'admin_panel'

    def ready(self):
        from .roles import ensure_admin_roles
        post_migrate.connect(ensure_admin_roles, sender=self)
