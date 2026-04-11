import django.db.models.deletion
from django.db import migrations, models


def migrate_driver_areas(apps, schema_editor):
    """Map existing area strings to Area FKs for DriverProfile."""
    DriverProfile = apps.get_model("authentication", "DriverProfile")
    Area = apps.get_model("common", "Area")

    area_map = {a.name.lower(): a for a in Area.objects.all()}

    for driver in DriverProfile.objects.all():
        old_value = (driver.area_old or "").strip().lower()
        area_obj = area_map.get(old_value)
        if area_obj:
            driver.area = area_obj
            driver.save(update_fields=["area"])


def migrate_agent_areas(apps, schema_editor):
    """Map existing area strings to Area FKs for AgentProfile."""
    AgentProfile = apps.get_model("authentication", "AgentProfile")
    Area = apps.get_model("common", "Area")

    area_map = {a.name.lower(): a for a in Area.objects.all()}

    for agent in AgentProfile.objects.all():
        old_value = (agent.area_old or "").strip().lower()
        area_obj = area_map.get(old_value)
        if area_obj:
            agent.area = area_obj
            agent.save(update_fields=["area"])


class Migration(migrations.Migration):

    dependencies = [
        ("authentication", "0009_agentprofile_invite_token_used"),
        ("common", "0002_seed_lagos_areas"),
    ]

    operations = [
        # --- DriverProfile ---
        # 1. Rename old CharField to area_old
        migrations.RenameField(
            model_name="driverprofile",
            old_name="area",
            new_name="area_old",
        ),
        # 2. Add new FK column
        migrations.AddField(
            model_name="driverprofile",
            name="area",
            field=models.ForeignKey(
                null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                related_name="drivers",
                to="common.area",
            ),
        ),
        # 3. Copy data
        migrations.RunPython(migrate_driver_areas, migrations.RunPython.noop),
        # 4. Drop old column
        migrations.RemoveField(
            model_name="driverprofile",
            name="area_old",
        ),

        # --- AgentProfile ---
        # 1. Rename old CharField to area_old
        migrations.RenameField(
            model_name="agentprofile",
            old_name="area",
            new_name="area_old",
        ),
        # 2. Add new FK column
        migrations.AddField(
            model_name="agentprofile",
            name="area",
            field=models.ForeignKey(
                null=True,
                blank=True,
                on_delete=django.db.models.deletion.SET_NULL,
                related_name="agents",
                to="common.area",
            ),
        ),
        # 3. Copy data
        migrations.RunPython(migrate_agent_areas, migrations.RunPython.noop),
        # 4. Drop old column
        migrations.RemoveField(
            model_name="agentprofile",
            name="area_old",
        ),
    ]
