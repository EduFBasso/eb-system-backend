from django.db import migrations


FORWARD_SQL = """
DO $$
BEGIN
    IF to_regclass('public.authentication_systemuser_groups') IS NOT NULL
       AND EXISTS (
           SELECT 1
           FROM information_schema.columns
           WHERE table_schema = 'public'
             AND table_name = 'authentication_systemuser_groups'
             AND column_name = 'professional_id'
       )
       AND NOT EXISTS (
           SELECT 1
           FROM information_schema.columns
           WHERE table_schema = 'public'
             AND table_name = 'authentication_systemuser_groups'
             AND column_name = 'systemuser_id'
       ) THEN
        ALTER TABLE public.authentication_systemuser_groups
            RENAME COLUMN professional_id TO systemuser_id;
    END IF;

    IF to_regclass('public.authentication_systemuser_user_permissions') IS NOT NULL
       AND EXISTS (
           SELECT 1
           FROM information_schema.columns
           WHERE table_schema = 'public'
             AND table_name = 'authentication_systemuser_user_permissions'
             AND column_name = 'professional_id'
       )
       AND NOT EXISTS (
           SELECT 1
           FROM information_schema.columns
           WHERE table_schema = 'public'
             AND table_name = 'authentication_systemuser_user_permissions'
             AND column_name = 'systemuser_id'
       ) THEN
        ALTER TABLE public.authentication_systemuser_user_permissions
            RENAME COLUMN professional_id TO systemuser_id;
    END IF;
END
$$;
"""


class Migration(migrations.Migration):
    dependencies = [
        ("authentication", "0003_transition_legacy_professional"),
    ]

    operations = [
        migrations.RunSQL(FORWARD_SQL, migrations.RunSQL.noop),
    ]
