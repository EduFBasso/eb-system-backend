from django.db import migrations, models
from django.db.models.functions import Lower


OLD_CONSTRAINT_NAME = "uq_tenant_membership_login_alias"
NEW_CONSTRAINT_NAME = "uq_tenant_membership_login_alias_ci"


def normalize_and_ensure_login_alias_constraint(apps, schema_editor):
    tenant_membership = apps.get_model("authentication", "TenantMembership")
    memberships = tenant_membership.objects.exclude(login_alias="").only(
        "id", "tenant_id", "login_alias"
    )
    seen = {}
    updates = []
    for membership in memberships.iterator():
        normalized = membership.login_alias.strip().lower()
        key = (membership.tenant_id, normalized)
        previous_id = seen.get(key)
        if previous_id is not None and previous_id != membership.id:
            raise RuntimeError(
                "Conflito de login_alias após normalização no tenant "
                f"{membership.tenant_id}: {normalized}"
            )
        seen[key] = membership.id
        if normalized != membership.login_alias:
            updates.append((membership.id, normalized))

    for membership_id, normalized in updates:
        tenant_membership.objects.filter(pk=membership_id).update(
            login_alias=normalized
        )

    table_name = tenant_membership._meta.db_table
    with schema_editor.connection.cursor() as cursor:
        constraints = schema_editor.connection.introspection.get_constraints(
            cursor,
            table_name,
        )

    if OLD_CONSTRAINT_NAME in constraints:
        schema_editor.remove_constraint(
            tenant_membership,
            models.UniqueConstraint(
                fields=("tenant", "login_alias"),
                name=OLD_CONSTRAINT_NAME,
            ),
        )

    if NEW_CONSTRAINT_NAME not in constraints:
        schema_editor.add_constraint(
            tenant_membership,
            models.UniqueConstraint(
                models.F("tenant"),
                Lower("login_alias"),
                condition=models.Q(login_alias__gt=""),
                name=NEW_CONSTRAINT_NAME,
            ),
        )


class Migration(migrations.Migration):
    dependencies = [
        ("authentication", "0005_ensure_tenant_ecosystem_constraint"),
    ]

    operations = [
        migrations.RunPython(
            normalize_and_ensure_login_alias_constraint,
            reverse_code=migrations.RunPython.noop,
        ),
    ]
