"""Inventory 5.17 — InventoryReportSnapshot [IRS-].

Deliberately scoped to THIS sub-module's model only: the QualityControl batch
that autodetect wanted to bundle here belongs to the concurrent 5.15 session,
which will generate its own migration for those models (one migration per
owner — bundling someone else's pending models forks their history).
"""
from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ("inventory", "0021_alter_alertrule_overstock_pct_and_more"),
    ]

    operations = [
        migrations.CreateModel(
            name="InventoryReportSnapshot",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("number", models.CharField(editable=False, max_length=20)),
                ("report_type", models.CharField(choices=[("valuation", "Inventory Valuation"), ("turnover", "Stock Turnover"), ("aging", "Aging Analysis"), ("abc", "ABC Analysis")], max_length=12)),
                ("title", models.CharField(blank=True, help_text="Optional caption; defaults to '<type> — <date>'.", max_length=120)),
                ("window_days", models.PositiveIntegerField(blank=True, help_text="Trailing window in days for turnover/ABC.", null=True)),
                ("summary", models.JSONField(default=dict)),
                ("notes", models.TextField(blank=True)),
                ("generated_by", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name="inventory_snapshots", to=settings.AUTH_USER_MODEL)),
                ("location", models.ForeignKey(blank=True, help_text="Optional scope; blank = every location.", null=True, on_delete=django.db.models.deletion.SET_NULL, related_name="report_snapshots", to="scm.location")),
                ("tenant", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="+", to="core.tenant")),
            ],
            options={
                "ordering": ["-created_at"],
                "indexes": [
                    models.Index(fields=["tenant", "created_at"], name="inv_irs_tnt_created_idx"),
                    models.Index(fields=["tenant", "report_type"], name="inv_irs_tnt_type_idx"),
                ],
            },
        ),
    ]
