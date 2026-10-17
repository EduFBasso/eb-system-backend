from django.db import migrations


def backfill_people(apps, schema_editor):
    Client = apps.get_model("legal", "LegalClient")
    Person = apps.get_model("legal", "LegalPerson")

    for client in Client.objects.filter(person__isnull=True).iterator():
        person_type = "company" if len((client.document or "").strip()) == 14 else "individual"
        person = Person.objects.create(
            tenant_id=client.tenant_id,
            person_type=person_type,
            name=client.name or "Pessoa sem nome",
            document=client.document or "",
            email=client.email or "",
            phone=client.phone or "",
        )
        client.person_id = person.id
        client.save(update_fields=["person"])


class Migration(migrations.Migration):
    dependencies = [
        ("legal", "0002_legalcaseparty_legalperson_legalrepresentation_and_more"),
    ]

    operations = [migrations.RunPython(backfill_people, migrations.RunPython.noop)]
