from django.conf import settings
from django.db import IntegrityError, models, transaction

from apps.core.utils import next_number


class TenantEventOwned(models.Model):
    tenant = models.ForeignKey("core.Tenant", on_delete=models.CASCADE, related_name="+", db_index=True)
    created_at = models.DateTimeField(auto_now_add=True, editable=False)

    class Meta:
        abstract = True


class TenantOwned(models.Model):
    tenant = models.ForeignKey("core.Tenant", on_delete=models.CASCADE, related_name="+", db_index=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        abstract = True


class TenantNumbered(TenantOwned):
    NUMBER_PREFIX = ""
    number = models.CharField(max_length=20, editable=False)

    class Meta:
        abstract = True

    def save(self, *args, **kwargs):
        if not self.number and self.tenant_id and self.NUMBER_PREFIX:
            for _ in range(5):
                self.number = next_number(type(self), self.tenant, self.NUMBER_PREFIX)
                try:
                    with transaction.atomic():
                        return super().save(*args, **kwargs)
                except IntegrityError:
                    self.number = ""
            # Every attempt collided. Previously this fell through to `super().save()`, which
            # PERSISTED the row with `number == ""` -- a numbered document with no number, and
            # a second one silently violates the (tenant, number) unique constraint that the
            # whole prefix system exists to provide. Five collisions mean a concurrent writer is
            # winning the race every time, so refusing is the only honest outcome: the caller
            # learns the row was not written instead of finding an unnumbered document later.
            raise IntegrityError(
                f"Could not allocate a unique {self.NUMBER_PREFIX} number for "
                f"{type(self).__name__} after 5 attempts. Another writer is holding the "
                f"sequence; retry, or pass an explicit `number=`."
            )
        return super().save(*args, **kwargs)
