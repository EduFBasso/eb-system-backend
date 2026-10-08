from django.db import migrations


FORWARD_SQL = """
DO $$
BEGIN
    IF to_regclass('public.authentication_professional') IS NOT NULL
       AND to_regclass('public.authentication_systemuser') IS NULL THEN
        ALTER TABLE public.authentication_professional
            RENAME TO authentication_systemuser;
    END IF;

    IF to_regclass('public.authentication_professional_groups') IS NOT NULL
       AND to_regclass('public.authentication_systemuser_groups') IS NULL THEN
        ALTER TABLE public.authentication_professional_groups
            RENAME TO authentication_systemuser_groups;
    END IF;

    IF to_regclass('public.authentication_professional_user_permissions') IS NOT NULL
       AND to_regclass('public.authentication_systemuser_user_permissions') IS NULL THEN
        ALTER TABLE public.authentication_professional_user_permissions
            RENAME TO authentication_systemuser_user_permissions;
    END IF;

    IF EXISTS (
        SELECT 1
        FROM django_content_type
        WHERE app_label = 'authentication' AND model = 'professional'
    ) AND NOT EXISTS (
        SELECT 1
        FROM django_content_type
        WHERE app_label = 'authentication' AND model = 'systemuser'
    ) THEN
        UPDATE django_content_type
        SET model = 'systemuser'
        WHERE app_label = 'authentication' AND model = 'professional';
    END IF;

    UPDATE auth_permission
    SET codename = replace(codename, '_professional', '_systemuser')
    WHERE content_type_id IN (
        SELECT id
        FROM django_content_type
        WHERE app_label = 'authentication' AND model = 'systemuser'
    )
      AND codename LIKE '%_professional';

    DROP TABLE IF EXISTS public.authentication_devicesession;
END
$$;
"""


def transition_legacy_professional(apps, schema_editor):
    if schema_editor.connection.vendor != "postgresql":
        return
    with schema_editor.connection.cursor() as cursor:
        cursor.execute(FORWARD_SQL)


class Migration(migrations.Migration):
    dependencies = [
        ("authentication", "0002_alter_systemuser_options"),
    ]

    operations = [
        migrations.RunPython(
            code=transition_legacy_professional,
            reverse_code=migrations.RunPython.noop,
        ),
    ]
