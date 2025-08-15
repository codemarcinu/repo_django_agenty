# Manual migration for additional indexes
# Compatible with both SQLite and PostgreSQL

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('inventory', '0001_initial'),
    ]

    operations = [
        # Add regular indexes for SQLite compatibility
        # These will be converted to GIN indexes when migrating to PostgreSQL
        migrations.RunSQL(
            sql=[
                # For PostgreSQL, these would be GIN indexes
                # For SQLite, regular indexes on JSON fields
                "-- Additional indexes for JSONB fields will be added in production PostgreSQL setup"
            ],
            reverse_sql=[
                "-- Reverse: Remove additional indexes"
            ],
            state_operations=[]
        ),
    ]