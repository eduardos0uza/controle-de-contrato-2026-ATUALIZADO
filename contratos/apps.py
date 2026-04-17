import os

from django.apps import AppConfig
from django.db.models.signals import post_migrate


class ContratosConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'contratos'

    def ready(self):
        from .roles import ensure_roles
        from .scheduler import start_scheduler
        from .signals import register_signals

        register_signals()
        post_migrate.connect(ensure_roles, sender=self)
        if os.environ.get('RUN_MAIN') == 'true':
            start_scheduler()
