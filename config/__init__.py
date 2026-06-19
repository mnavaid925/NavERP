"""NavERP project package.

Two bootstrap concerns live here because they must take effect *before* Django
touches the database backend:

1. PyMySQL is registered as the MySQLdb driver (XAMPP ships MySQL/MariaDB and we
   talk to it via PyMySQL — no compiled mysqlclient needed on Windows).

2. MariaDB 10.4 compatibility shim (lessons L4 / L23).
   Django 5.1's minimum supported MariaDB is 10.5; XAMPP ships 10.4.x. Two things
   are required to run on 10.4 — lowering the version floor is NOT enough on its own:
     a) relax the minimum-version gate, and
     b) force the INSERT ... RETURNING feature flags OFF. Because 10.5 is Django's
        floor, the mysql backend no longer version-gates RETURNING and enables it for
        ANY MariaDB; on 10.4 that produces `pymysql.err.ProgrammingError (1064)` on the
        very first `INSERT ... RETURNING django_migrations.id`. Assigning a plain value
        overrides the cached_property descriptor on the class.
"""
import pymysql

pymysql.install_as_MySQLdb()

try:
    from django.db.backends.mysql.features import DatabaseFeatures

    # (a) relax the version floor
    DatabaseFeatures.minimum_database_version = (10, 4)

    def _check_database_version_supported(self):  # no-op: we knowingly run on 10.4
        return None

    DatabaseFeatures.check_database_version_supported = _check_database_version_supported

    # (b) force RETURNING off (must override the cached_property — L23)
    DatabaseFeatures.can_return_columns_from_insert = False
    DatabaseFeatures.can_return_rows_from_bulk_insert = False
except Exception:  # pragma: no cover - Django not importable yet (e.g. tooling)
    pass
