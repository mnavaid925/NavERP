"""core 0013 — 0.16 Backup, Recovery & Data Lifecycle.

Placeholder committed at CLAIM time (Phase 0) to take the migration number before the concurrent
7.18 session can. The operations are filled in during Integrate (Phase 3) once the four models
exist; `makemigrations core` will generate the real state operations into this same file.
"""
from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ("core", "0012_language_timezone_localeprofile_userlocalepreference_and_more"),
    ]

    operations = []
