"""SCM 4.7 Demand Planning — the statistical method library.

**Pure Python + ``Decimal``. Zero ORM, zero numpy/pandas/scikit.** Every number a planner sees has to
be reproducible and explainable (the "glass box" the enterprise planning suites sell), and adding a
scientific-stack dependency to a Django/HTMX CRUD app to compute a moving average would be a poor
trade. The engines here are the deterministic classics every demand-planning product ships as its
baseline tier; ML/ensemble engines are a documented later pass.

Conventions
-----------
* A *series* is a plain ``list[Decimal]`` in chronological order — the caller (``_history.py``)
  owns where the numbers came from.
* Every engine returns a ``list[Decimal]`` of exactly ``horizon`` values, and NEVER raises on a short
  or empty series: an item with two months of history still has to produce a forecast, so each engine
  degrades to the best it can do (usually the naive/mean answer) rather than blowing up a page.
* Nothing here rounds to a display precision — the model fields do that on save.
"""
from decimal import Decimal, InvalidOperation

ZERO = Decimal("0")
ONE = Decimal("1")


# ----------------------------------------------------------------------------- basic statistics
def _d(value):
    """Coerce anything numeric-ish to Decimal, mapping junk to 0 rather than raising."""
    if isinstance(value, Decimal):
        return value
    try:
        return Decimal(str(value))
    except (InvalidOperation, TypeError, ValueError):
        return ZERO


def mean(series):
    series = [_d(v) for v in series]
    if not series:
        return ZERO
    return sum(series, ZERO) / Decimal(len(series))


def std_dev(series):
    """Sample standard deviation (n-1). Returns 0 for a series of fewer than two points."""
    series = [_d(v) for v in series]
    n = len(series)
    if n < 2:
        return ZERO
    mu = mean(series)
    variance = sum(((v - mu) ** 2 for v in series), ZERO) / Decimal(n - 1)
    if variance <= ZERO:
        return ZERO
    return variance.sqrt()


def clip_outliers(series, sigma=Decimal("3")):
    """Clamp points more than ``sigma`` standard deviations from the mean back to the boundary.

    Clamping rather than dropping keeps the series' length and period alignment intact — a promotion
    spike distorts the fit, but deleting the month would silently shift every later period.
    """
    series = [_d(v) for v in series]
    sigma = _d(sigma)
    if len(series) < 3 or sigma <= ZERO:
        return series
    mu, sd = mean(series), std_dev(series)
    if sd <= ZERO:
        return series
    low, high = mu - sigma * sd, mu + sigma * sd
    return [min(max(v, low), high) for v in series]


# ----------------------------------------------------------------------------- forecast engines
def naive(series, horizon):
    """Repeat the last observation."""
    last = _d(series[-1]) if series else ZERO
    return [last] * horizon


def seasonal_naive(series, horizon, period=12):
    """Repeat the observation one full season back — the honest baseline for seasonal demand."""
    series = [_d(v) for v in series]
    if not series:
        return [ZERO] * horizon
    period = max(int(period or 1), 1)
    out = []
    for i in range(horizon):
        idx = len(series) - period + (i % period)
        out.append(series[idx] if 0 <= idx < len(series) else series[-1])
    return out


def moving_average(series, horizon, window=3):
    """Flat forecast at the mean of the last ``window`` points."""
    series = [_d(v) for v in series]
    if not series:
        return [ZERO] * horizon
    window = max(int(window or 3), 1)
    return [mean(series[-window:])] * horizon


def weighted_moving_average(series, horizon, window=3):
    """Moving average with linearly increasing weights — the most recent point counts the most."""
    series = [_d(v) for v in series]
    if not series:
        return [ZERO] * horizon
    window = max(int(window or 3), 1)
    tail = series[-window:]
    weights = [Decimal(i + 1) for i in range(len(tail))]
    total = sum(weights, ZERO)
    if total <= ZERO:
        return [ZERO] * horizon
    value = sum((v * w for v, w in zip(tail, weights)), ZERO) / total
    return [value] * horizon


def exponential_smoothing(series, horizon, alpha=Decimal("0.3")):
    """Simple exponential smoothing (no trend, no season). ``alpha`` is clamped to (0, 1]."""
    series = [_d(v) for v in series]
    if not series:
        return [ZERO] * horizon
    alpha = _clamp_fraction(alpha, Decimal("0.3"))
    level = series[0]
    for value in series[1:]:
        level = alpha * value + (ONE - alpha) * level
    return [level] * horizon


def holt_linear(series, horizon, alpha=Decimal("0.3"), beta=Decimal("0.1")):
    """Holt's double exponential smoothing — level + trend, so the forecast slopes."""
    series = [_d(v) for v in series]
    if len(series) < 2:
        return naive(series, horizon)
    alpha = _clamp_fraction(alpha, Decimal("0.3"))
    beta = _clamp_fraction(beta, Decimal("0.1"))
    level, trend = series[0], series[1] - series[0]
    for value in series[1:]:
        prev_level = level
        level = alpha * value + (ONE - alpha) * (level + trend)
        trend = beta * (level - prev_level) + (ONE - beta) * trend
    return [level + trend * Decimal(i + 1) for i in range(horizon)]


def holt_winters(series, horizon, period=12, alpha=Decimal("0.3"), beta=Decimal("0.1"),
                 gamma=Decimal("0.3")):
    """Additive Holt-Winters — level + trend + season.

    Needs two full seasons to initialise honestly; with less it falls back to ``holt_linear`` rather
    than fitting a seasonal component to noise.
    """
    series = [_d(v) for v in series]
    period = max(int(period or 12), 2)
    if len(series) < 2 * period:
        return holt_linear(series, horizon, alpha, beta)
    alpha = _clamp_fraction(alpha, Decimal("0.3"))
    beta = _clamp_fraction(beta, Decimal("0.1"))
    gamma = _clamp_fraction(gamma, Decimal("0.3"))

    season_means = [mean(series[i * period:(i + 1) * period]) for i in range(len(series) // period)]
    level = season_means[0]
    trend = (season_means[1] - season_means[0]) / Decimal(period)
    seasonals = [series[i] - season_means[0] for i in range(period)]

    for i, value in enumerate(series):
        idx = i % period
        prev_level = level
        level = alpha * (value - seasonals[idx]) + (ONE - alpha) * (level + trend)
        trend = beta * (level - prev_level) + (ONE - beta) * trend
        seasonals[idx] = gamma * (value - level) + (ONE - gamma) * seasonals[idx]

    start = len(series)
    return [level + trend * Decimal(i + 1) + seasonals[(start + i) % period] for i in range(horizon)]


def linear_trend(series, horizon):
    """Ordinary least-squares straight line through the series, projected forward."""
    series = [_d(v) for v in series]
    n = len(series)
    if n < 2:
        return naive(series, horizon)
    xs = [Decimal(i) for i in range(n)]
    x_bar, y_bar = mean(xs), mean(series)
    denominator = sum(((x - x_bar) ** 2 for x in xs), ZERO)
    if denominator <= ZERO:
        return [y_bar] * horizon
    slope = sum(((x - x_bar) * (y - y_bar) for x, y in zip(xs, series)), ZERO) / denominator
    intercept = y_bar - slope * x_bar
    return [intercept + slope * Decimal(n + i) for i in range(horizon)]


def _clamp_fraction(value, default):
    """Smoothing constants must live in (0, 1] — a hand-typed 0 or 7 would silently break the fit."""
    value = _d(value)
    if value <= ZERO or value > ONE:
        return default
    return value


# ----------------------------------------------------------------------------- method dispatch
#: Methods ``run_method`` can actually execute, mapped to how ``method_parameter`` is read.
METHOD_PARAMETER_HELP = {
    "naive": "unused",
    "seasonal_naive": "season length (periods)",
    "moving_average": "window N",
    "weighted_moving_average": "window N",
    "exponential_smoothing": "alpha 0-1",
    "holt_linear": "alpha 0-1",
    "holt_winters": "season length (periods)",
    "like_item": "unused (scale % is its own field)",
    "manual": "unused",
    "best_fit": "unused",
}

#: The engines ``best_fit`` competes. ``like_item``/``manual`` are copy/typed, not fitted, and
#: ``best_fit`` obviously cannot compete against itself.
_FITTABLE = ("naive", "seasonal_naive", "moving_average", "weighted_moving_average",
             "exponential_smoothing", "holt_linear", "holt_winters")


def run_method(method, series, horizon, parameter=None, season_period=12):
    """Run one engine by name. Unknown/typed methods fall back to ``moving_average``."""
    horizon = max(int(horizon or 0), 0)
    if horizon == 0:
        return []
    parameter = _d(parameter) if parameter is not None else None
    if method == "naive":
        return naive(series, horizon)
    if method == "seasonal_naive":
        return seasonal_naive(series, horizon, int(parameter or season_period))
    if method == "moving_average":
        return moving_average(series, horizon, int(parameter or 3))
    if method == "weighted_moving_average":
        return weighted_moving_average(series, horizon, int(parameter or 3))
    if method == "exponential_smoothing":
        return exponential_smoothing(series, horizon, parameter or Decimal("0.3"))
    if method == "holt_linear":
        return holt_linear(series, horizon, parameter or Decimal("0.3"))
    if method == "holt_winters":
        return holt_winters(series, horizon, int(parameter or season_period))
    if method == "linear_trend":
        return linear_trend(series, horizon)
    return moving_average(series, horizon, int(parameter or 3))


def best_fit(series, horizon, season_period=12):
    """Compete every fittable engine on a hold-out tail and keep the lowest-MAPE one.

    Returns ``(method_name, values)``. The hold-out is the last ~25 % of the series (min 1, max 6
    points): each engine is fitted on the earlier part and scored against the part it never saw, so
    the winner is chosen on out-of-sample error rather than on how well it memorised the history.
    With too little history to hold anything out, ``moving_average`` wins by default — an honest
    "not enough data to choose" rather than a coin flip.
    """
    series = [_d(v) for v in series]
    holdout = min(max(len(series) // 4, 1), 6)
    train = series[:-holdout]
    actual = series[-holdout:]
    if len(train) < 3 or not actual:
        return "moving_average", moving_average(series, horizon)
    best_name, best_error = None, None
    for name in _FITTABLE:
        try:
            predicted = run_method(name, train, holdout, season_period=season_period)
        except (InvalidOperation, ZeroDivisionError, ValueError):
            continue  # a degenerate series must not take the whole selection down
        error = mape(actual, predicted)
        if error is None:
            continue
        if best_error is None or error < best_error:
            best_name, best_error = name, error
    if best_name is None:
        return "moving_average", moving_average(series, horizon)
    return best_name, run_method(best_name, series, horizon, season_period=season_period)


# ----------------------------------------------------------------------------- accuracy metrics
def _pairs(actual, forecast):
    return [(_d(a), _d(f)) for a, f in zip(actual or [], forecast or [])]


def mape(actual, forecast):
    """Mean absolute percentage error. ``None`` when every actual is zero (MAPE is undefined then)."""
    pairs = [(a, f) for a, f in _pairs(actual, forecast) if a != ZERO]
    if not pairs:
        return None
    total = sum((abs(a - f) / abs(a) for a, f in pairs), ZERO)
    return (total / Decimal(len(pairs))) * Decimal("100")


def wmape(actual, forecast):
    """Weighted MAPE — Σ|a−f| / Σ|a|. Survives zero-demand periods, which is why planners prefer it."""
    pairs = _pairs(actual, forecast)
    denominator = sum((abs(a) for a, _ in pairs), ZERO)
    if denominator <= ZERO:
        return None
    return (sum((abs(a - f) for a, f in pairs), ZERO) / denominator) * Decimal("100")


def bias_pct(actual, forecast):
    """Signed error as a % of actual — positive means the forecast ran HIGH (over-forecast)."""
    pairs = _pairs(actual, forecast)
    denominator = sum((a for a, _ in pairs), ZERO)
    if denominator <= ZERO:
        return None
    return (sum((f - a for a, f in pairs), ZERO) / denominator) * Decimal("100")


def tracking_signal(actual, forecast):
    """Cumulative error ÷ mean absolute deviation. |TS| > 4 means the model is drifting, not noisy."""
    pairs = _pairs(actual, forecast)
    if not pairs:
        return None
    mad = sum((abs(f - a) for a, f in pairs), ZERO) / Decimal(len(pairs))
    if mad <= ZERO:
        return ZERO
    return sum((f - a for a, f in pairs), ZERO) / mad


def forecast_value_added(actual, baseline, final):
    """FVA — how many percentage points of error the human/consensus overrides REMOVED.

    Positive = the overrides helped; negative = the statistical baseline alone was better. The metric
    that keeps a collaborative planning process honest, so it is reported next to MAPE rather than
    buried.
    """
    base_error = wmape(actual, baseline)
    final_error = wmape(actual, final)
    if base_error is None or final_error is None:
        return None
    return base_error - final_error


# ----------------------------------------------------------------------------- safety stock
#: Service level → Z. A short lookup table beats an inverse-normal approximation here: these are the
#: levels planners actually set, and a table is auditable at a glance.
_Z_TABLE = [
    (Decimal("50"), Decimal("0.00")), (Decimal("75"), Decimal("0.67")),
    (Decimal("80"), Decimal("0.84")), (Decimal("85"), Decimal("1.04")),
    (Decimal("90"), Decimal("1.28")), (Decimal("92"), Decimal("1.41")),
    (Decimal("95"), Decimal("1.65")), (Decimal("96"), Decimal("1.75")),
    (Decimal("97"), Decimal("1.88")), (Decimal("97.5"), Decimal("1.96")),
    (Decimal("98"), Decimal("2.05")), (Decimal("99"), Decimal("2.33")),
    (Decimal("99.5"), Decimal("2.58")), (Decimal("99.9"), Decimal("3.09")),
]


def z_for_service_level(pct):
    """Z-score for a target cycle-service level (nearest tabulated level at or below ``pct``)."""
    pct = _d(pct)
    z = _Z_TABLE[0][1]
    for level, value in _Z_TABLE:
        if pct >= level:
            z = value
        else:
            break
    return z
