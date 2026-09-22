"""core 0013 — 0.16 Backup, Recovery & Data Lifecycle.

Creates the seven models this sub-module adds: BackupJob, DataArchive, RestoreRecord,
EnvironmentInstance, RecoveryPosture, RecoveryDrill and LegalHold.

The number was reserved at Phase 0 with an empty operations list so a concurrent 7.18 session could not
take it. `makemigrations` then emitted this state under a second name (0014), because a placeholder with
no operations is not something it fills in place; the operations were folded back into this file and the
generated duplicate removed, so there is one migration per sub-module and its name says what it does.

Nothing here creates, dumps, restores or provisions anything at runtime — these are register tables for
evidence that a human records after doing the work out of band. See apps/core/models/Backup.py.
"""
import django.db.models.deletion
import django.utils.timezone
from django.conf import settings
from django.db import migrations, models




class Migration(migrations.Migration):

    dependencies = [
        ('core', '0012_language_timezone_localeprofile_userlocalepreference_and_more'),
        ('tenants', '0004_usagerecord'),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name='BackupJob',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('name', models.CharField(max_length=150)),
                ('scope_label', models.CharField(blank=True, help_text="What is covered, e.g. 'nav_erp schema' or 'ACME tenant'.", max_length=255)),
                ('backup_type', models.CharField(choices=[('full', 'Full'), ('incremental', 'Incremental'), ('differential', 'Differential'), ('log', 'Transaction log'), ('snapshot', 'Snapshot')], default='full', max_length=16)),
                ('frequency', models.CharField(choices=[('manual', 'Manual only'), ('hourly', 'Hourly'), ('daily', 'Daily'), ('weekly', 'Weekly')], default='manual', help_text='A recorded intention. Nothing in NavERP runs it.', max_length=10)),
                ('retention_days', models.PositiveIntegerField(blank=True, null=True)),
                ('target_location', models.CharField(blank=True, help_text='Where it was written. Free text — NavERP has no storage client.', max_length=255)),
                ('storage_tier', models.CharField(choices=[('standard', 'Standard'), ('infrequent', 'Infrequent access'), ('archive', 'Archive'), ('deep_archive', 'Deep archive'), ('tape', 'Tape / offline')], default='standard', max_length=16)),
                ('encryption_scheme', models.CharField(choices=[('none', 'None'), ('aes256', 'AES-256'), ('rsa', 'RSA'), ('managed', 'Provider-managed'), ('other', 'Other')], default='none', max_length=16)),
                ('size_bytes', models.BigIntegerField(blank=True, null=True)),
                ('checksum', models.CharField(blank=True, max_length=128)),
                ('integrity_method', models.CharField(choices=[('none', 'Not checked'), ('checksum', 'Checksum'), ('hash', 'Cryptographic hash'), ('restore_test', 'Restore test'), ('vendor_reported', 'Vendor reported')], default='none', max_length=16)),
                ('integrity_verified_at', models.DateTimeField(blank=True, null=True)),
                ('status', models.CharField(choices=[('queued', 'Queued'), ('running', 'Running'), ('success', 'Success'), ('warning', 'Warning — partial'), ('failed', 'Failed'), ('cancelled', 'Cancelled')], default='queued', max_length=16)),
                ('failure_reason', models.CharField(choices=[('n_a', 'Not applicable'), ('source_unreachable', 'Source unreachable'), ('auth_failed', 'Authentication failed'), ('insufficient_space', 'Insufficient space'), ('timeout', 'Timed out'), ('integrity_check_failed', 'Integrity check failed'), ('cancelled_by_operator', 'Cancelled by operator'), ('quota', 'Licence or quota'), ('partial_scope_skipped', 'Partial — some scope skipped'), ('unknown', 'Unknown')], default='n_a', max_length=24)),
                ('attempt_count', models.PositiveSmallIntegerField(default=1)),
                ('is_immutable', models.BooleanField(default=False, help_text='Recorded claim about the target. NavERP cannot enforce this.')),
                ('retain_until', models.DateTimeField(blank=True, null=True)),
                ('started_at', models.DateTimeField(blank=True, null=True)),
                ('finished_at', models.DateTimeField(blank=True, null=True)),
                ('evidence', models.CharField(blank=True, max_length=255)),
                ('notes', models.TextField(blank=True)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('encryption_key', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='+', to='tenants.encryptionkey')),
                ('performed_by', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='+', to=settings.AUTH_USER_MODEL)),
                ('tenant', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='backup_jobs', to='core.tenant')),
            ],
            options={
                'ordering': ['-started_at', '-id'],
            },
        ),
        migrations.CreateModel(
            name='DataArchive',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('name', models.CharField(max_length=150)),
                ('model_label', models.CharField(blank=True, help_text="`app_label.Model` that was archived — 0.8's vocabulary.", max_length=120)),
                ('content_description', models.TextField(blank=True)),
                ('location', models.CharField(help_text='URI or path where the archive IS.', max_length=255)),
                ('storage_tier', models.CharField(choices=[('hot', 'Hot'), ('cool', 'Cool'), ('archive', 'Archive'), ('glacier', 'Glacier'), ('deep_archive', 'Deep archive'), ('offline', 'Offline'), ('tape', 'Tape')], default='archive', max_length=16)),
                ('format', models.CharField(choices=[('sql', 'SQL dump'), ('csv', 'CSV'), ('jsonl', 'JSON Lines'), ('parquet', 'Parquet'), ('tarball', 'Tarball'), ('native', 'Native / proprietary'), ('other', 'Other')], default='sql', max_length=16)),
                ('record_count', models.PositiveIntegerField(blank=True, null=True)),
                ('size_bytes', models.BigIntegerField(blank=True, null=True)),
                ('checksum', models.CharField(blank=True, max_length=128)),
                ('immutable', models.BooleanField(default=False, help_text='Recorded claim. Immutability is enforced by the storage, not by NavERP.')),
                ('archived_at', models.DateTimeField(blank=True, null=True)),
                ('restored_at', models.DateTimeField(blank=True, null=True)),
                ('expires_at', models.DateTimeField(blank=True, null=True)),
                ('status', models.CharField(choices=[('active', 'Active'), ('restored', 'Restored'), ('expired', 'Expired'), ('lost', 'Lost'), ('destroyed', 'Destroyed')], default='active', max_length=12)),
                ('notes', models.TextField(blank=True)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('disposal', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='archives', to='core.disposalrecord')),
                ('encryption_key', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='+', to='tenants.encryptionkey')),
                ('policy', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='archives', to='core.retentionpolicy')),
                ('tenant', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='data_archives', to='core.tenant')),
            ],
            options={
                'ordering': ['-archived_at', '-id'],
            },
        ),
        migrations.CreateModel(
            name='EnvironmentInstance',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('name', models.CharField(max_length=150)),
                ('kind', models.CharField(choices=[('production', 'Production'), ('development', 'Development'), ('test', 'Test'), ('staging', 'Staging'), ('training', 'Training'), ('sandbox', 'Sandbox'), ('preview', 'Preview')], default='sandbox', max_length=16)),
                ('tier', models.CharField(blank=True, max_length=20)),
                ('copy_scope', models.CharField(choices=[('none', 'Empty — no data'), ('metadata_only', 'Metadata / configuration only'), ('summary', 'Summary — data subset'), ('full', 'Full copy')], default='metadata_only', max_length=16)),
                ('subset_rule', models.TextField(blank=True, help_text='Which data, how much, and from where. Declared, not run.')),
                ('copy_includes_pii', models.BooleanField(default=False)),
                ('masking_required', models.BooleanField(default=False, help_text='Copying production PII downward is the classic compliance failure. Records the obligation; NavERP does not mask.')),
                ('status', models.CharField(choices=[('requested', 'Requested'), ('provisioning', 'Provisioning'), ('active', 'Active'), ('refreshing', 'Refreshing'), ('ready_to_activate', 'Ready to activate'), ('suspended', 'Suspended'), ('expired', 'Expired'), ('reaped', 'Reaped')], default='requested', max_length=20)),
                ('refreshed_at', models.DateTimeField(blank=True, null=True)),
                ('refresh_interval_days', models.PositiveSmallIntegerField(blank=True, null=True)),
                ('expires_at', models.DateTimeField(blank=True, null=True)),
                ('storage_limit_mb', models.PositiveIntegerField(blank=True, help_text='Declared capacity. Not enforced here.', null=True)),
                ('is_active', models.BooleanField(default=True)),
                ('notes', models.TextField(blank=True)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('refresh_source', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='refreshed_from', to='core.environmentinstance')),
                ('source_environment', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='derived_environments', to='core.environmentinstance')),
                ('tenant', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='environment_instances', to='core.tenant')),
            ],
            options={
                'ordering': ['name'],
            },
        ),
        migrations.CreateModel(
            name='LegalHold',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('name', models.CharField(max_length=150)),
                ('custodian', models.CharField(blank=True, max_length=200)),
                ('matter_reference', models.CharField(blank=True, help_text='Case or matter number.', max_length=150)),
                ('issuing_authority', models.CharField(blank=True, help_text='Court, regulator, or internal counsel.', max_length=200)),
                ('scope', models.TextField(blank=True, help_text='What data and systems the hold covers.')),
                ('model_label', models.CharField(blank=True, max_length=120)),
                ('issued_at', models.DateTimeField(default=django.utils.timezone.now)),
                ('status', models.CharField(choices=[('active', 'Active'), ('released', 'Released'), ('expired', 'Expired'), ('superseded', 'Superseded')], default='active', max_length=12)),
                ('released_at', models.DateTimeField(blank=True, null=True)),
                ('release_reason', models.CharField(blank=True, help_text='Documenting the release is what proves good faith.', max_length=255)),
                ('authority_reference', models.CharField(blank=True, help_text='Preservation order or notice reference.', max_length=255)),
                ('notes', models.TextField(blank=True)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('issued_by', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='+', to=settings.AUTH_USER_MODEL)),
                ('released_by', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='released_legal_holds', to=settings.AUTH_USER_MODEL)),
                ('retention_policy', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='legal_holds', to='core.retentionpolicy')),
                ('subject_party', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='+', to='core.party')),
                ('tenant', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='legal_holds', to='core.tenant')),
            ],
            options={
                'ordering': ['-issued_at', '-id'],
            },
        ),
        migrations.CreateModel(
            name='RecoveryDrill',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('name', models.CharField(max_length=150)),
                ('kind', models.CharField(choices=[('planned_failover', 'Planned failover'), ('unplanned_failover', 'Unplanned failover'), ('test_failover', 'Test failover (isolated)'), ('tabletop', 'Tabletop exercise'), ('backup_restore_test', 'Backup restore test')], default='test_failover', max_length=24)),
                ('scheduled_for', models.DateField(blank=True, null=True)),
                ('performed_at', models.DateTimeField(blank=True, null=True)),
                ('outcome', models.CharField(choices=[('not_run', 'Not yet run'), ('passed', 'Passed'), ('partial', 'Partial'), ('failed', 'Failed')], default='not_run', max_length=10)),
                ('measured_rpo_minutes', models.PositiveIntegerField(blank=True, null=True)),
                ('measured_rto_minutes', models.PositiveIntegerField(blank=True, null=True)),
                ('participants', models.CharField(blank=True, max_length=255)),
                ('findings', models.TextField(blank=True, help_text='What the drill actually showed. The deliverable.')),
                ('follow_up_actions', models.TextField(blank=True)),
                ('evidence', models.CharField(blank=True, max_length=255)),
                ('notes', models.TextField(blank=True)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('performed_by', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='+', to=settings.AUTH_USER_MODEL)),
                ('tenant', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='recovery_drills', to='core.tenant')),
            ],
            options={
                'ordering': ['-performed_at', '-id'],
            },
        ),
        migrations.CreateModel(
            name='RecoveryPosture',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('rpo_target_minutes', models.PositiveIntegerField(blank=True, help_text='Recovery point objective: how much data loss is acceptable.', null=True)),
                ('rto_target_minutes', models.PositiveIntegerField(blank=True, help_text='Recovery time objective: how long an outage may last.', null=True)),
                ('replication_mode', models.CharField(choices=[('none', 'None'), ('sync', 'Synchronous'), ('async', 'Asynchronous')], default='none', max_length=10)),
                ('primary_region', models.CharField(blank=True, max_length=80)),
                ('dr_region', models.CharField(blank=True, max_length=80)),
                ('backup_retention_days', models.PositiveIntegerField(blank=True, null=True)),
                ('dr_plan_reference', models.CharField(blank=True, help_text='Where the plan itself lives. NavERP stores the reference, not the document.', max_length=255)),
                ('last_reviewed_at', models.DateField(blank=True, null=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('tenant', models.OneToOneField(on_delete=django.db.models.deletion.CASCADE, related_name='recovery_posture', to='core.tenant')),
            ],
            options={
                'verbose_name': 'recovery posture',
                'verbose_name_plural': 'recovery posture',
            },
        ),
        migrations.CreateModel(
            name='RestoreRecord',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('scope', models.CharField(choices=[('full_instance', 'Full instance'), ('per_tenant', 'Per tenant'), ('table', 'Table'), ('record', 'Record'), ('sandbox_refresh', 'Sandbox refresh'), ('archive_retrieval', 'Archive retrieval')], default='full_instance', max_length=20)),
                ('target_time', models.DateTimeField(blank=True, null=True)),
                ('status', models.CharField(choices=[('planned', 'Planned'), ('running', 'Running'), ('succeeded', 'Succeeded'), ('partial', 'Partial'), ('failed', 'Failed'), ('rolled_back', 'Rolled back')], default='planned', max_length=16)),
                ('reason', models.CharField(blank=True, max_length=255)),
                ('started_at', models.DateTimeField(blank=True, null=True)),
                ('finished_at', models.DateTimeField(blank=True, null=True)),
                ('outcome', models.TextField(blank=True)),
                ('is_verified', models.BooleanField(default=False)),
                ('evidence', models.CharField(blank=True, max_length=255)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('archive', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='restores', to='core.dataarchive')),
                ('backup', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='restores', to='core.backupjob')),
                ('requested_by', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='+', to=settings.AUTH_USER_MODEL)),
                ('target_environment', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='restores', to='core.environmentinstance')),
                ('tenant', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='restore_records', to='core.tenant')),
            ],
            options={
                'ordering': ['-created_at', '-id'],
            },
        ),
        migrations.AddIndex(
            model_name='backupjob',
            index=models.Index(fields=['tenant', '-started_at'], name='bkpjob_tenant_at_idx'),
        ),
        migrations.AddIndex(
            model_name='backupjob',
            index=models.Index(fields=['tenant', 'status'], name='bkpjob_tenant_status_idx'),
        ),
        migrations.AddIndex(
            model_name='dataarchive',
            index=models.Index(fields=['tenant', 'status'], name='darch_tenant_status_idx'),
        ),
        migrations.AddIndex(
            model_name='environmentinstance',
            index=models.Index(fields=['tenant', 'kind'], name='envinst_tenant_kind_idx'),
        ),
        migrations.AddIndex(
            model_name='legalhold',
            index=models.Index(fields=['tenant', 'status'], name='lghold_tenant_status_idx'),
        ),
        migrations.AddIndex(
            model_name='legalhold',
            index=models.Index(fields=['tenant', 'model_label'], name='lghold_tenant_model_idx'),
        ),
        migrations.AddIndex(
            model_name='recoverydrill',
            index=models.Index(fields=['tenant', 'outcome'], name='drill_tenant_outcome_idx'),
        ),
        migrations.AddIndex(
            model_name='restorerecord',
            index=models.Index(fields=['tenant', '-created_at'], name='recrec_tenant_at_idx'),
        ),
    ]
