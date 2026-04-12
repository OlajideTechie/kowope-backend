import django.db.models.deletion
from django.db import migrations, models


def migrate_ticket_areas(apps, schema_editor):
    """Map existing area strings to Area FKs for Ticket."""
    Ticket = apps.get_model("ticket", "Ticket")
    Area = apps.get_model("common", "Area")

    area_map = {a.name.lower(): a for a in Area.objects.all()}

    for ticket in Ticket.objects.all():
        old_value = (ticket.area_old or "").strip().lower()
        area_obj = area_map.get(old_value)
        if area_obj:
            ticket.area = area_obj
            ticket.save(update_fields=["area"])


class Migration(migrations.Migration):

    dependencies = [
        ("ticket", "0007_ticket_unique_ticket_per_payment_and_more"),
        ("common", "0002_seed_lagos_areas"),
    ]

    operations = [
        # 1. Rename old CharField to area_old
        migrations.RenameField(
            model_name="ticket",
            old_name="area",
            new_name="area_old",
        ),
        # 2. Add new FK column (nullable initially)
        migrations.AddField(
            model_name="ticket",
            name="area",
            field=models.ForeignKey(
                null=True,
                on_delete=django.db.models.deletion.CASCADE,
                related_name="tickets",
                to="common.area",
            ),
        ),
        # 3. Copy data
        migrations.RunPython(migrate_ticket_areas, migrations.RunPython.noop),
        # 4. Drop old column
        migrations.RemoveField(
            model_name="ticket",
            name="area_old",
        ),
        # 5. Make FK non-nullable to match model
        migrations.AlterField(
            model_name="ticket",
            name="area",
            field=models.ForeignKey(
                on_delete=django.db.models.deletion.CASCADE,
                related_name="tickets",
                to="common.area",
            ),
        ),
    ]
