"""core — 0.15 Localization & Regional Settings.

**What already exists, and what 0.15 therefore does NOT re-declare.** An inventory of the two apps that
own the currency and tax spine found:

* `accounting.Currency` — the ISO 4217 master, and deliberately **GLOBAL** (no `tenant` FK), with its
  own docstring saying so. Bullet 2's "currencies" is already built.
* `accounting.ExchangeRate` — the tenant's dated spot rates (`rate_date`, `rate`, `source` ∈
  manual/feed, unique on `(tenant, currency, rate_date)`). Bullet 2's "exchange rates" is already built.
* `accounting.TaxCode` — the tenant's tax master with `jurisdiction`, `tax_type`, `rate_pct` and its
  payable GL account. Bullet 4's "region-specific tax rules" is already built.
* `core.BusinessCalendar.timezone_name` (0.10) — an IANA name, but for the **working-day** calendar.
  That is a different zone from the tenant's *display* zone; both are legitimate and neither is the
  other's duplicate.
* `core.SettingDefinition` / `SettingValue` (0.10) — the generic key/value settings engine. A language
  is not a string; it is a row with an RTL flag. A time zone is not a string; it is a row with an offset
  and a DST flag. Registry ≠ setting, so none of this is expressed as a setting definition.

**What genuinely did not exist anywhere** (grep across `apps/` returns nothing for `Language`,
`TimeZone`, `Locale`, `LocaleProfile`, `RegionalSetting`, `LocalizationProfile`, `StatutoryRule`):

1. **`Language`** — bullet 1's "language packs … RTL support". Registers *which* languages a workspace
   offers and which of them read right-to-left. It deliberately does **not** store the UI strings:
   `config/settings.py` has `USE_I18N = True` and no `LOCALE_PATHS`, so the strings are Django's
   `gettext`/`.po` layer. Every translation-management product surveyed (Lokalise, Phrase, Crowdin)
   treats translation as a content pipeline over locale files, not as operational DB rows.
2. **`TimeZone`** — bullet 5's "time zones and daylight-saving handling". Only a free-text
   `BusinessCalendar.timezone_name` existed; there was no registry, no offset and no DST flag.
3. **`LocaleProfile`** — bullets 2, 3 and 5's tenant half: the workspace's base currency, default
   language, display time zone and regional format patterns. This is where NetSuite's "subsidiary base
   currency" and Dynamics' "legal-entity default format" land.
4. **`UserLocalePreference`** — bullet 5's per-user half. NetSuite, Salesforce and ServiceNow all put
   locale/language/time zone on the **user** with the tenant supplying the default, which is exactly
   this shape (and the reason `date_format` may be blank = "inherit").
5. **`StatutoryRule`** — bullet 4's absent half. `accounting.TaxCode` is a *rate*; e-invoicing is a
   per-jurisdiction **compliance mode** (Italy SDI, India GST IRN, PEPPOL) attached to the entity, not
   to the rate — the Avalara/Stripe-Tax split. This points at `accounting.TaxCode` by string.

**Nothing here converts anything.** There is no scheduler, no rate fetcher and no translation service,
so a language records that a locale is offered, a zone records its offset for display, and a statutory
rule records a compliance obligation. The one place a real conversion is needed, the code says to use
the standard library (`zoneinfo`) rather than the stored offset — see `TimeZone`.
"""
import re

from django.core.exceptions import ValidationError

from apps.core.models._base import *  # noqa: F401,F403


#: A regional format pattern may contain only these characters. Free text would be a formatting
#: foot-gun the moment something interpolates it, so the allow-list is enforced at the model edge as
#: well as in the form. Letters carry the tokens (yyyy, MM, dd, HH), digits appear in numeric patterns,
#: and the rest are the separators a real locale uses.
FORMAT_TOKEN_RE = re.compile(r"^[A-Za-z0-9#,. /:\-']+$")


class Language(models.Model):
    """A language the platform can present. **GLOBAL** — shared across all tenants (no `tenant` FK),
    the same posture `accounting.Currency` takes and for the same reason: a language is a fact about
    the world, not about a workspace. Giving it a tenant FK would mean every workspace re-typing
    "French".

    This registers WHICH languages are offered and which read right-to-left. It does **not** store the
    translated strings — those live in Django's `gettext` catalogue (`.po` files), which is how every
    translation-management product in this space models them.
    """

    code = models.CharField(max_length=8, unique=True,
                            help_text="ISO 639-1 code, e.g. 'en', 'fr', 'ar'.")
    name = models.CharField(max_length=60)
    native_name = models.CharField(max_length=60, blank=True,
                                   help_text="The language's own name, e.g. 'العربية'.")
    #: Bullet 1's right-to-left support. A flag on the language rather than a separate setting,
    #: because it is a property of the language and cannot vary per workspace.
    is_rtl = models.BooleanField(default=False, help_text="Rendered right-to-left.")
    is_default = models.BooleanField(default=False, help_text="The platform fallback language.")
    is_active = models.BooleanField(default=True)

    class Meta:
        ordering = ["name"]

    def __str__(self):
        return self.name


class TimeZone(models.Model):
    """An IANA time zone the platform can present. **GLOBAL** — no `tenant` FK, same reasoning as
    `Language`.

    **The stored `utc_offset_minutes` is for display and ordering only.** It is the zone's *standard*
    offset and is wrong for roughly half the year anywhere that observes DST. Any actual conversion
    must call ``zoneinfo.ZoneInfo(self.name)``, which carries the real transition rules; doing
    arithmetic against this column is precisely how a DST bug ships.
    """

    name = models.CharField(max_length=64, unique=True,
                            help_text="IANA name, e.g. 'Europe/London'.")
    label = models.CharField(max_length=100, help_text="Human label, e.g. 'London (GMT/BST)'.")
    #: Standard offset. DISPLAY ONLY — see the class docstring.
    utc_offset_minutes = models.IntegerField(default=0)
    observes_dst = models.BooleanField(default=False)
    is_active = models.BooleanField(default=True)

    class Meta:
        ordering = ["utc_offset_minutes", "name"]

    def __str__(self):
        return self.label

    @property
    def offset_display(self):
        """`utc_offset_minutes` as a UTC offset — `UTC+05:30`, `UTC-08:00`, `UTC+00:00`.

        A template cannot format a minutes integer into an offset, so the conversion lives here
        rather than rendering `UTC+330` (which reads as 330 hours). DISPLAY ONLY, exactly like the
        column it formats: this is the zone's *standard* offset and is wrong for roughly half the
        year anywhere that observes DST — see the class docstring.
        """
        sign = "-" if self.utc_offset_minutes < 0 else "+"
        hours, minutes = divmod(abs(self.utc_offset_minutes), 60)
        return "UTC%s%02d:%02d" % (sign, hours, minutes)


class LocaleProfile(models.Model):
    """A workspace's localization profile — the single row that answers "how does this tenant want
    dates, numbers, money and time presented?".

    A OneToOne rather than a list: a tenant has exactly one default presentation, so the house
    "list + detail + create + edit + delete" CRUD shape does not apply. It is an edit page, exactly
    like 0.10's `BusinessCalendar` (the other tenant singleton).

    `base_currency` points at `accounting.Currency` by string. This model records WHICH currency is the
    tenant's base; `accounting.ExchangeRate` owns the rates against it. Re-declaring either here would
    split the ledger's own currency master from the presentation layer (L36).
    """

    FIRST_DAY_CHOICES = [(1, "Monday"), (2, "Tuesday"), (3, "Wednesday"), (4, "Thursday"),
                         (5, "Friday"), (6, "Saturday"), (7, "Sunday")]

    tenant = models.OneToOneField("core.Tenant", on_delete=models.CASCADE,
                                  related_name="locale_profile", db_index=True)
    language = models.ForeignKey("core.Language", on_delete=models.SET_NULL, null=True, blank=True,
                                 related_name="+")
    base_currency = models.ForeignKey("accounting.Currency", on_delete=models.SET_NULL, null=True,
                                      blank=True, related_name="+")
    time_zone = models.ForeignKey("core.TimeZone", on_delete=models.SET_NULL, null=True, blank=True,
                                  related_name="+")

    #: Format PATTERNS, not an enum of formats. Dynamics and CLDR both model it this way: a locale
    #: supplies a pattern and the caller formats with it, so a new regional convention is data rather
    #: than a code change.
    date_format = models.CharField(max_length=40, default="dd/MM/yyyy")
    time_format = models.CharField(max_length=40, default="HH:mm")
    number_format = models.CharField(max_length=40, default="#,##0.00")
    address_format = models.TextField(blank=True, help_text="Multi-line address template.")
    #: ISO weekday number, matching `core.BusinessCalendar.working_days`.
    first_day_of_week = models.PositiveSmallIntegerField(choices=FIRST_DAY_CHOICES, default=1)
    notes = models.TextField(blank=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["tenant__name"]

    def __str__(self):
        return "Locale · %s" % self.tenant

    def clean(self):
        super().clean()
        for field in ("date_format", "time_format", "number_format"):
            value = getattr(self, field) or ""
            if value and not FORMAT_TOKEN_RE.match(value):
                raise ValidationError({field: "A format pattern may contain letters, digits, "
                                              "# , . / : - and spaces only."})


class UserLocalePreference(models.Model):
    """One person's regional overrides — bullet 5's per-user half.

    NetSuite, Salesforce and ServiceNow all put language, time zone and format on the *user*, with the
    workspace supplying the default. `date_format` is blank-able for exactly that reason: blank means
    "inherit whatever `LocaleProfile` says", so a user overrides only what they care about.
    """

    tenant = models.ForeignKey("core.Tenant", on_delete=models.CASCADE,
                               related_name="user_locale_preferences", db_index=True)
    user = models.OneToOneField(settings.AUTH_USER_MODEL, on_delete=models.CASCADE,
                                related_name="locale_preference")
    language = models.ForeignKey("core.Language", on_delete=models.SET_NULL, null=True, blank=True,
                                 related_name="+")
    time_zone = models.ForeignKey("core.TimeZone", on_delete=models.SET_NULL, null=True, blank=True,
                                  related_name="+")
    #: Blank = inherit the tenant's pattern.
    date_format = models.CharField(max_length=40, blank=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["user__email"]

    def __str__(self):
        return "Locale pref · %s" % self.user

    def clean(self):
        super().clean()
        if self.date_format and not FORMAT_TOKEN_RE.match(self.date_format):
            raise ValidationError({"date_format": "A format pattern may contain letters, digits, "
                                                 "# , . / : - and spaces only."})


class StatutoryRule(models.Model):
    """A jurisdiction's statutory/e-invoicing obligation — bullet 4's absent half.

    `accounting.TaxCode` already owns the RATE (`jurisdiction`, `tax_type`, `rate_pct`). This owns the
    **compliance mode**, which is a different thing and belongs to a different layer: Italy's SDI and
    India's GST IRN are obligations about *how an invoice is transmitted*, not about how much tax it
    carries. Avalara and Stripe Tax draw the same line. Hence `tax_code` is an optional FK — a rule can
    be a reporting obligation with no single rate attached.
    """

    E_INVOICING_CHOICES = [
        ("none", "Not required"),
        ("peppol", "PEPPOL / EU"),
        ("sdi", "Italy SDI"),
        ("cfdi", "Mexico CFDI"),
        ("gst_irn", "India GST IRN"),
        ("other", "Other"),
    ]

    tenant = models.ForeignKey("core.Tenant", on_delete=models.CASCADE,
                               related_name="statutory_rules", db_index=True)
    name = models.CharField(max_length=150)
    #: Free text, like `core.Holiday.region` — a closed country list would be wrong for a global
    #: product, and jurisdictions do not map one-to-one onto ISO country codes.
    jurisdiction = models.CharField(max_length=120, blank=True)
    tax_code = models.ForeignKey("accounting.TaxCode", on_delete=models.SET_NULL, null=True, blank=True,
                                 related_name="statutory_rules")
    e_invoicing_required = models.BooleanField(default=False)
    e_invoicing_scheme = models.CharField(max_length=12, choices=E_INVOICING_CHOICES, default="none")
    statutory_report = models.CharField(max_length=150, blank=True,
                                        help_text="e.g. 'VAT Return (MTD)'.")
    effective_from = models.DateField()
    effective_to = models.DateField(null=True, blank=True)
    is_active = models.BooleanField(default=True)
    notes = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["jurisdiction", "name"]
        unique_together = ("tenant", "name")
        indexes = [models.Index(fields=["tenant", "is_active"], name="statrule_tenant_active_idx")]

    def __str__(self):
        return self.name

    def clean(self):
        super().clean()
        if self.effective_to and self.effective_from and self.effective_to < self.effective_from:
            raise ValidationError({"effective_to": "The end date cannot precede the start date."})
        # Coherence, checked here rather than in the form so the seeder and the admin are covered by
        # the same rule. "E-invoicing is required but no scheme is named" is not a state anyone can
        # act on, so it is refused at the only edge every writer passes through.
        if self.e_invoicing_required and self.e_invoicing_scheme == "none":
            raise ValidationError({"e_invoicing_scheme":
                                   "Choose the scheme this jurisdiction uses."})
