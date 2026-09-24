from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("sales", "0002_alter_leadroutingrule_max_open_leads_and_more"),
    ]

    operations = [
        migrations.AddConstraint(
            model_name="leadnurtureenrollment",
            constraint=models.UniqueConstraint(fields=("tenant", "number"), name="sales_lne_tenant_number_uniq"),
        ),
    ]
