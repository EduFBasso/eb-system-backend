from django.apps import AppConfig


class TenancyConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'apps.tenancy'
    verbose_name = 'Tenancy'

    def ready(self):
        # Ensure signal receivers are registered when Django starts.
        from . import signals  # noqa: F401
