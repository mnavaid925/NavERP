"""Make JobRequisition.public_token unique + nullable (3.6 code-review fix).

0011 added ``public_token`` as a non-null blank CharField, so every unposted requisition stored an
empty string. To make the field ``unique=True`` (matching the crm.Case/LandingPage bearer-token
convention) the duplicate empty strings must first become NULL — NULLs don't collide on a unique
constraint. Sequence: widen to nullable, blank out the empties, then add the unique constraint.
"""
from django.db import migrations, models


def blanks_to_null(apps, schema_editor):
    JobRequisition = apps.get_model("hrm", "JobRequisition")
    JobRequisition.objects.filter(public_token="").update(public_token=None)


def null_to_blanks(apps, schema_editor):
    JobRequisition = apps.get_model("hrm", "JobRequisition")
    JobRequisition.objects.filter(public_token__isnull=True).update(public_token="")


class Migration(migrations.Migration):

    dependencies = [
        ("hrm", "0011_candidate_management"),
    ]

    operations = [
        migrations.AlterField(
            model_name="jobrequisition",
            name="public_token",
            field=models.CharField(
                blank=True, editable=False, max_length=64, null=True,
                help_text="URL-safe token minted when the req is posted; powers the public careers portal."),
        ),
        migrations.RunPython(blanks_to_null, null_to_blanks),
        migrations.AlterField(
            model_name="jobrequisition",
            name="public_token",
            field=models.CharField(
                blank=True, editable=False, max_length=64, null=True, unique=True,
                help_text="URL-safe token minted when the req is posted; powers the public careers portal."),
        ),
    ]
