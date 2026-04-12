from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("ticket", "0008_convert_area_to_fk"),
    ]

    operations = [
        migrations.SeparateDatabaseAndState(
            state_operations=[
                migrations.RemoveIndex(
                    model_name="ticket",
                    name="ticket_tick_area_b06258_idx",
                ),
            ],
            database_operations=[
                migrations.RunSQL(
                    sql="DROP INDEX IF EXISTS ticket_tick_area_b06258_idx;",
                    reverse_sql=migrations.RunSQL.noop,
                ),
            ],
        ),
    ]
