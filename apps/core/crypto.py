"""Reversible field encryption for secrets that must be recoverable in plaintext.

This is deliberately NOT the prefix + SHA-256 pattern used by
``apps/tenants/models/EncryptionKey.py`` and ``apps/accounting/models/Integration/IntegrationConfigs.py``.
Those models never need the plaintext back — they only ever answer "is this the same
value?" — so a one-way hash is strictly safer there and must stay.

A key used to **sign** an outbound payload is the opposite case. HMAC needs the real
key bytes at signing time, so a SHA-256 digest makes signing mathematically impossible.
The only way to protect such a key at rest while keeping it usable is reversible
encryption with the key material held OUTSIDE the database.

Threat model: a stolen database dump, a backup, a replicated row, or a log line that
captured the column. Any of those yields ciphertext alone; decrypting additionally
requires ``SECRET_KEY``/``FIELD_ENCRYPTION_KEY`` from the environment, which never
lives in the database. It is NOT a defence against full host compromise — an attacker
who already reads the process environment can decrypt, and no application-level scheme
changes that.

Values are stored with a ``fernet.v1:`` marker. That marker is what makes the scheme
migration-safe: :func:`decrypt` passes an unmarked value through unchanged (a legacy
plaintext row) and :func:`encrypt` refuses to wrap an already-encrypted one, so both
the data migration and every ``save()`` are idempotent and there is no flag day.
"""
import base64

from cryptography.fernet import Fernet, InvalidToken
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.kdf.hkdf import HKDF
from django.conf import settings
from django.core.exceptions import ImproperlyConfigured

#: Marks an encrypted value and pins the scheme, so a future algorithm change can
#: recognise and re-wrap v1 rows instead of guessing at their format.
PREFIX = "fernet.v1:"


def _fernet():
    """Build the cipher from ``FIELD_ENCRYPTION_KEY``, else derive one from ``SECRET_KEY``.

    The derived fallback is what keeps every dev box, CI run and test suite working
    without extra configuration. It is not a weakening of the threat model above: the
    derived key is a function of ``SECRET_KEY``, which lives in ``.env`` and never in
    the database, so a stolen dump is still undecryptable on its own.

    Deriving rather than using ``SECRET_KEY`` directly means rotating one does not
    silently change the other's behaviour, and the ``info`` string domain-separates
    this use from any other key derived from the same secret.
    """
    explicit = (getattr(settings, "FIELD_ENCRYPTION_KEY", "") or "").strip()
    if explicit:
        return Fernet(explicit.encode())

    secret = (getattr(settings, "SECRET_KEY", "") or "").encode()
    if not secret:
        raise ImproperlyConfigured(
            "Neither FIELD_ENCRYPTION_KEY nor SECRET_KEY is set — cannot encrypt secret fields."
        )
    derived = HKDF(
        algorithm=hashes.SHA256(), length=32, salt=None,
        info=b"naverp.field-encryption.v1",
    ).derive(secret)
    return Fernet(base64.urlsafe_b64encode(derived))


def is_encrypted(value):
    """True if ``value`` already carries the scheme marker."""
    return bool(value) and str(value).startswith(PREFIX)


def encrypt(plaintext):
    """Encrypt ``plaintext`` for storage. Idempotent, and passes blanks through.

    Re-encrypting an already-encrypted value would make it undecryptable in one step
    and is always a bug (a double-wrapped row), so it is a no-op here rather than an
    error — that keeps ``save()`` safe to call any number of times.
    """
    if not plaintext:
        return ""
    if is_encrypted(plaintext):
        return plaintext
    return PREFIX + _fernet().encrypt(str(plaintext).encode()).decode()


def decrypt(stored):
    """Return the plaintext behind ``stored``.

    An unmarked value is a pre-migration plaintext row and is returned as-is, so a
    missed row degrades to the old behaviour instead of breaking signing.

    A marked value that will not decrypt means the key changed (rotated or a different
    environment). That raises, because silently returning the ciphertext would sign
    payloads with the wrong key and produce signatures no recipient could verify —
    a failure that would otherwise surface only at the far end, long after the cause.
    """
    if not stored:
        return ""
    if not is_encrypted(stored):
        return stored
    token = str(stored)[len(PREFIX):].encode()
    try:
        return _fernet().decrypt(token).decode()
    except InvalidToken as exc:
        raise ImproperlyConfigured(
            "Could not decrypt a stored secret. FIELD_ENCRYPTION_KEY/SECRET_KEY does not "
            "match the key the value was encrypted with."
        ) from exc
