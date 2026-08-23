import django.core.validators
import django.db.models.deletion
from decimal import Decimal
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('core', '0004_add_candidate_party_role'),
        ('inventory', '0011_alter_purchaseorderdispatch_recipient'),
        ('scm', '0034_remove_integrationmessage_scm_msg_tnt_status_idx_and_more'),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name='TransferRoute',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('name', models.CharField(max_length=120)),
                ('code', models.CharField(blank=True, help_text='Short reference used on documents, e.g. RT-WH1-WH2', max_length=32)),
                ('mode', models.CharField(choices=[('direct', 'Direct Run'), ('shuttle', 'Scheduled Shuttle'), ('milk_run', 'Consolidated Milk Run'), ('freight', 'Freight Carrier')], default='direct', max_length=12)),
                ('default_transit_days', models.PositiveSmallIntegerField(default=1, help_text='Expected door-to-door days when this route is used', validators=[django.core.validators.MinValueValidator(1)])),
                ('is_active', models.BooleanField(default=True)),
                ('notes', models.TextField(blank=True)),
                ('destination_location', models.ForeignKey(blank=True, help_text='Lane end — blank means this route may end anywhere', null=True, on_delete=django.db.models.deletion.PROTECT, related_name='transfer_routes_to', to='scm.location')),
                ('origin_location', models.ForeignKey(blank=True, help_text='Lane start — blank means this route may start anywhere', null=True, on_delete=django.db.models.deletion.PROTECT, related_name='transfer_routes_from', to='scm.location')),
                ('tenant', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='+', to='core.tenant')),
            ],
            options={
                'ordering': ['name'],
                'indexes': [models.Index(fields=['tenant', 'is_active'], name='inv_trt_tnt_active_idx')],
                'unique_together': {('tenant', 'name')},
            },
        ),
        migrations.CreateModel(
            name='TransferApprovalRule',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('name', models.CharField(max_length=120)),
                ('applies_to', models.CharField(choices=[('all', 'All transfers'), ('inter_warehouse', 'Inter-warehouse only'), ('intra_warehouse', 'Intra-warehouse only')], default='all', help_text='Which kind of movement this rule governs', max_length=16)),
                ('min_units', models.DecimalField(decimal_places=4, default=Decimal('0'), help_text='Total units across all lines at which this rule starts to apply (inclusive)', max_digits=16, validators=[django.core.validators.MinValueValidator(Decimal('0'))])),
                ('max_units', models.DecimalField(blank=True, decimal_places=4, help_text='Upper bound, EXCLUSIVE — blank means open-ended above min_units', max_digits=16, null=True, validators=[django.core.validators.MinValueValidator(Decimal('0'))])),
                ('tier_count', models.PositiveIntegerField(default=1, help_text='Sequential approval sign-offs a matching transfer must clear', validators=[django.core.validators.MinValueValidator(1), django.core.validators.MaxValueValidator(10)])),
                ('is_active', models.BooleanField(default=True)),
                ('tenant', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='+', to='core.tenant')),
            ],
            options={
                'ordering': ['-min_units', 'name'],
                'indexes': [models.Index(fields=['tenant', 'is_active'], name='inv_tar_tnt_active_idx')],
                'unique_together': {('tenant', 'name')},
            },
        ),
        migrations.CreateModel(
            name='TransferApproval',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('number', models.CharField(editable=False, max_length=20)),
                ('tier', models.PositiveIntegerField(help_text='1-based position in the approval sequence', validators=[django.core.validators.MinValueValidator(1)])),
                ('decision', models.CharField(choices=[('approved', 'Approved'), ('rejected', 'Rejected')], default='approved', max_length=10)),
                ('decided_at', models.DateTimeField(default=django.utils.timezone.now, editable=False)),
                ('note', models.TextField(blank=True)),
                ('decided_by', models.ForeignKey(blank=True, editable=False, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='inventory_transfer_tier_decisions', to=settings.AUTH_USER_MODEL)),
                ('rule', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='transfer_decisions', to='inventory.transferapprovalrule')),
                ('tenant', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='+', to='core.tenant')),
                ('transfer', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='approval_decisions', to='scm.stocktransfer')),
            ],
            options={
                'ordering': ['transfer_id', 'tier'],
                'indexes': [models.Index(fields=['tenant', 'transfer'], name='inv_ta_tnt_trf_idx')],
            },
        ),
    ]
