"""Pure-Python ports of the indicators in /workspace/backtests/backtest.py (pandas ewm(adjust=False) semantics).
NaN is represented as float('nan'); comparisons with NaN are False, exactly like pandas/numpy."""
import math

NAN = float("nan")


def ewm(xs, alpha):
    """pandas Series.ewm(alpha=..., adjust=False).mean() for series without NaNs after the first value(s)."""
    out, prev = [], None
    for x in xs:
        if x is None or (isinstance(x, float) and math.isnan(x)):
            out.append(NAN if prev is None else prev)
            continue
        prev = x if prev is None else (1 - alpha) * prev + alpha * x
        out.append(prev)
    return out


def ema(xs, n):
    return ewm(xs, 2.0 / (n + 1))


def rma(xs, n):
    return ewm(xs, 1.0 / n)


def true_range(h, l, c):
    tr = []
    for i in range(len(c)):
        if i == 0:
            tr.append(h[0] - l[0])  # pandas max(axis=1) skips the NaN from close.shift()
        else:
            pc = c[i - 1]
            tr.append(max(h[i] - l[i], abs(h[i] - pc), abs(l[i] - pc)))
    return tr


def atr(h, l, c, n):
    return rma(true_range(h, l, c), n)


def _div(a, b):
    if b == 0 or math.isnan(a) or math.isnan(b):
        if b == 0 and not math.isnan(a) and a != 0:
            return math.copysign(math.inf, a)
        return NAN
    return a / b


def dmi(h, l, c, n=14):
    pdm, mdm = [0.0], [0.0]
    for i in range(1, len(c)):
        up, dn = h[i] - h[i - 1], -(l[i] - l[i - 1])
        pdm.append(up if (up > dn and up > 0) else 0.0)
        mdm.append(dn if (dn > up and dn > 0) else 0.0)
    a = atr(h, l, c, n)
    rp, rm = rma(pdm, n), rma(mdm, n)
    pdi = [100 * _div(x, y) for x, y in zip(rp, a)]
    mdi = [100 * _div(x, y) for x, y in zip(rm, a)]
    dx = []
    for p, m in zip(pdi, mdi):
        s = p + m
        v = NAN if (s == 0 or math.isnan(s)) else 100 * _div(abs(p - m), s)
        dx.append(0.0 if math.isnan(v) else v)
    return pdi, mdi, rma(dx, n)


def supertrend(h, l, c, n=10, m=3.0):
    a = atr(h, l, c, n)
    hl2 = [(x + y) / 2 for x, y in zip(h, l)]
    ub = [x + m * y for x, y in zip(hl2, a)]
    lb = [x - m * y for x, y in zip(hl2, a)]
    fub, flb, d = ub[:], lb[:], [1.0] * len(c)
    for i in range(1, len(c)):
        fub[i] = ub[i] if (ub[i] < fub[i - 1] or c[i - 1] > fub[i - 1]) else fub[i - 1]
        flb[i] = lb[i] if (lb[i] > flb[i - 1] or c[i - 1] < flb[i - 1]) else flb[i - 1]
        if d[i - 1] == -1 and c[i] > fub[i - 1]:
            d[i] = 1.0
        elif d[i - 1] == 1 and c[i] < flb[i - 1]:
            d[i] = -1.0
        else:
            d[i] = d[i - 1]
    return d
