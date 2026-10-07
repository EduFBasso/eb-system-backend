from django.db import migrations, models


CONSTRAINT_NAME = "tenant_ecosystem_not_empty"


def ensure_ecosystem_constraint(apps, schema_editor):
    tenant_model = apps.get_model("authentication", "Tenant")
    constraint = models.CheckConstraint(
        condition=~models.Q(ecosystem=""),
        name=CONSTRAINT_NAME,
    )
    table_name = tenant_model._meta.db_table

    with schema_editor.connection.cursor() as cursor:
        constraints = schema_editor.connection.introspection.get_constraints(
            cursor,
            table_name,
        )

    if CONSTRAINT_NAME not in constraints:
        schema_editor.add_constraint(tenant_model, constraint)


class Migration(migrations.Migration):
    dependencies = [
        ("authentication", "0004_fix_systemuser_m2m_columns"),
    ]

    operations = [
        migrations.RunPython(
            ensure_ecosystem_constraint,
            reverse_code=migrations.RunPython.noop,
        ),
    ]
