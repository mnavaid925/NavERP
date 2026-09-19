"""TOTP (RFC 6238) and the adaptive risk score — the two pure functions 0.4 needs.

Both live here rather than in the views so they are independently testable: a TOTP bug is a lockout
bug, and a risk score buried in a request handler cannot be exercised with fixed inputs.

No third-party dependency: RFC 6238 is HMAC-SHA1 over a big-endian counter, truncated — about
fifteen lines. Adding `pyotp` for that would put a supply-chain edge on the login path.
"""
import base64
import hashlib
import hmac
import ipaddress
import secrets
import struct
import time
from urllib.parse import quote

#: RFC 6238 defaults, and what every authenticator app assumes.
DIGITS = 6
PERIOD = 30
#: Accept the code from the previous and next window too. A phone clock a few seconds off is the
#: single most common cause of "the code is wrong" lockouts; +/-1 window (90s total) is the
#: conventional tolerance and still leaves a 30s effective replay window.
WINDOW_DRIFT = 1


def generate_secret(length=32):
    """A fresh base32 secret. `length` is in BYTES (32 bytes = 52 base32 chars, the RFC's SHA-1 size)."""
    return base64.b32encode(secrets.token_bytes(length)).decode("ascii").rstrip("=")


def _hotp(key, counter, digits=DIGITS):
    digest = hmac.new(key, struct.pack(">Q", counter), hashlib.sha1).digest()
    offset = digest[-1] & 0x0F
    truncated = struct.unpack(">I", digest[offset:offset + 4])[0] & 0x7FFFFFFF
    return str(truncated % (10 ** digits)).zfill(digits)


def totp(secret, at=None, digits=DIGITS, period=PERIOD):
    """The code for `secret` at time `at` (defaults to now)."""
    padded = secret.upper() + "=" * (-len(secret) % 8)
    try:
        key = base64.b32decode(padded, casefold=True)
    except Exception:
        return None
    counter = int((at if at is not None else time.time()) // period)
    return _hotp(key, counter, digits)


def verify_totp(secret, code, at=None, window=WINDOW_DRIFT):
    """Constant-time check of `code` against the current window +/- `window`.

    Returns the matched counter (truthy even at 0) or None, so the caller can refuse to reuse a
    counter — a TOTP code is valid for its whole window, and without this a shoulder-surfed code
    could be replayed for another 30 seconds.
    """
    if not secret or not code:
        return None
    code = str(code).strip().replace(" ", "")
    if not code.isdigit():
        return None
    now = at if at is not None else time.time()
    counter = int(now // PERIOD)
    for offset in range(-window, window + 1):
        candidate = counter + offset
        expected = totp(secret, at=candidate * PERIOD)
        if expected and hmac.compare_digest(expected, code):
            return candidate
    return None


def provisioning_uri(secret, account, issuer="NavERP"):
    """The otpauth:// URI an authenticator app scans. `account` is normally the user's email."""
    label = quote(f"{issuer}:{account}")
    return (f"otpauth://totp/{label}?secret={secret}"
            f"&issuer={quote(issuer)}&algorithm=SHA1&digits={DIGITS}&period={PERIOD}")


def generate_backup_codes(count=8):
    """Single-use recovery codes. Returned in plaintext ONCE; only hashes are stored."""
    return [f"{secrets.token_hex(2)}-{secrets.token_hex(2)}" for _ in range(count)]


def hash_backup_code(code):
    return hashlib.sha256(code.strip().lower().encode()).hexdigest()


# ------------------------------------------------------------------ adaptive risk scoring
#: Signals and their weights. Deliberately a readable table rather than a model: the score is a
#: policy, and a policy that can be edited per row cannot be reasoned about in an incident.
RISK_WEIGHTS = {
    "new_ip": 30,
    "new_device": 30,
    "recent_failures": 40,
}


def is_public_ip(ip):
    """True for a routable address. Private/loopback addresses are normal in dev and on a LAN, so
    they must not raise the score — otherwise every developer looks like an attacker."""
    if not ip:
        return False
    try:
        addr = ipaddress.ip_address(ip)
    except ValueError:
        return False
    return not (addr.is_private or addr.is_loopback or addr.is_link_local or addr.is_reserved)


def risk_score(*, ip, user_agent, seen_ips, seen_agents, recent_failure_count, threshold_failures=3):
    """Score a login attempt from observable signals. Returns (score, reasons).

    This is a HEURISTIC, not a model, and it is named as one everywhere it surfaces. It answers
    "does this look like the same person?" using three things the app actually knows. It does NOT
    do geo-IP lookup, device fingerprinting or behavioural analysis — those need data this repo
    does not have, and claiming them would be the dishonest part.
    """
    score = 0
    reasons = []
    if ip and is_public_ip(ip) and ip not in seen_ips:
        score += RISK_WEIGHTS["new_ip"]
        reasons.append("new_ip")
    if user_agent and user_agent not in seen_agents:
        score += RISK_WEIGHTS["new_device"]
        reasons.append("new_device")
    if recent_failure_count >= threshold_failures:
        score += RISK_WEIGHTS["recent_failures"]
        reasons.append("recent_failures")
    return score, reasons


#: At or above this, a user WITH a second factor is challenged (which MFA already does) and the
#: attempt is flagged on the register. A user WITHOUT one is flagged but never blocked — silently
#: locking someone out on a heuristic would be worse than the risk it guards against.
RISK_STEP_UP_THRESHOLD = 40
