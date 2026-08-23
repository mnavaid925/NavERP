import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):
    """5.7 Stock Movement & Transfers — the governed-transfer spine evolution.

    Two new states (pending_approval / approved) that inventory.TransferApproval tier
    chains drive, plus a nullable routing FK onto the movement itself. Additive only:
    every existing row stays exactly where its status was.
    """

    dependencies = [
        ('inventory', '0012_transferroute_transferapprovalrule_transferapproval'),
        ('scm', '0034_remove_integrationmessage_scm_msg_tnt_status_idx_and_more'),
    ]

    operations = [
        migrations.AlterField(
            model_name='stocktransfer',
            name='status',
            field=models.CharField(choices=[('draft', 'Draft'), ('pending_approval', 'Pending Approval'), ('approved', 'Approved'), ('in_transit', 'In Transit'), ('completed', 'Completed'), ('cancelled', 'Cancelled')], default='draft', max_length=16),
        ),
        migrations.AddField(
            model_name='stocktransfer',
            name='route',
            field=models.ForeignKey(blank=True, help_text='How this movement travels (5.7 Transfer Routing)', null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='transfers', to='inventory.transferroute'),
        ),
    ]
