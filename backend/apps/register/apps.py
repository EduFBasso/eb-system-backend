# backend\apps\register\apps.py
import os
import json
import logging
from django.apps import AppConfig

logger = logging.getLogger(__name__)


class RegisterConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'apps.register'

    def ready(self):
        # One-time admin creation hook. Set ONE_OFF_ADMIN as JSON in env vars, e.g.
        # {"email":"you@example.com","password":"StrongPass123!","first_name":"Admin","last_name":"Clinic"}
        payload = os.environ.get('ONE_OFF_ADMIN')
        if not payload:
            return
        try:
            data = json.loads(payload)
        except Exception:
            logger.exception('ONE_OFF_ADMIN is not valid JSON')
            return

        try:
            # Use the project's user model. This project uses email as the USERNAME_FIELD,
            # so pass email/password to create_superuser to avoid unexpected kwarg errors.
            from django.contrib.auth import get_user_model
            User = get_user_model()

            # Defensive: if DB is not ready yet (migrations), any query may fail; handle gracefully.
            try:
                has_super = User.objects.filter(is_superuser=True).exists()
            except Exception as e:
                logger.warning('ONE_OFF_ADMIN: database not ready or inaccessible at startup: %s', e)
                return

            if not has_super:
                User.objects.create_superuser(
                    email=data.get('email', 'admin@example.com'),
                    password=data.get('password', 'ChangeMe123!'),
                    first_name=data.get('first_name', 'Admin'),
                    last_name=data.get('last_name', 'Clinic'),
                    display_name=data.get('display_name', ''),
                )
                logger.warning('ONE_OFF_ADMIN: created superuser')
            else:
                logger.info('ONE_OFF_ADMIN: superuser already exists, skipping')
        except Exception:
            logger.exception('Failed to create one-off admin')
