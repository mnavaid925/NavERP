"""EscalationPolicy is a per-tenant singleton — give the get_or_create a real
constraint to lean on so two concurrent first-touches cannot fork the knob (after
which every .get() on the singleton raises MultipleObjectsReturned).
"""
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("procurement", "0005_approvaldelegation_approvalroutingrule_and_more"),
    ]

    operations = [
        migrations.AlterUniqueTogether(
            name="escalationpolicy",
            unique_together={("tenant",)},
        ),
    ]
