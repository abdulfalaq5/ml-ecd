"""Uji rugi gesek annulus power-law (app/core/hydraulics.py)."""
import math

import pytest

from app.core import hydraulics as hy

R = hy.Rheo(15, 15)


def test_rheology_from_pv_yp():
    assert R.n == pytest.approx(3.32 * math.log10(45 / 30), rel=1e-9)
    assert R.K == pytest.approx(510 * 30 / 511 ** R.n, rel=1e-9)


def test_laminar_gradient_formula_and_power_law_scaling():
    q, d2, d1, mw = 200.0, 8.5, 5.0, 10.0
    g, turb = hy.grad(q, d2, d1, mw, R)
    assert not turb
    v = q / (2.448 * (d2 ** 2 - d1 ** 2))
    n, K = R.n, R.K
    assert g == pytest.approx(K * v ** n * ((2 + 1 / n) / 0.0208) ** n / (144000 * (d2 - d1) ** (1 + n)), rel=1e-9)
    g2, turb2 = hy.grad(2 * q, d2, d1, mw, R)
    assert not turb2 and g2 / g == pytest.approx(2 ** n, rel=1e-9)        # laminar: dp ∝ v^n


def test_transition_is_continuous():
    qs = range(300, 1400, 5)
    g = [hy.grad(q, 8.5, 5.0, 10, R)[0] for q in qs]
    assert all(b >= a for a, b in zip(g, g[1:]))                         # naik terus
    assert max(b / a for a, b in zip(g, g[1:])) < 1.06                  # tanpa lompatan (langkah 5 gpm)


def test_turbulence_and_geometry():
    lam, t1 = hy.grad(300, 8.5, 5.0, 10, R)
    hi, t2 = hy.grad(900, 8.5, 5.0, 10, R)
    assert not t1 and t2 and hi > lam
    assert hy.grad(400, 8.5, 6.75, 10, R)[0] > hy.grad(400, 8.5, 5.0, 10, R)[0]   # celah sempit → rugi lebih besar
    assert hy.grad(0, 8.5, 5.0, 10, R) == (0.0, False)


def test_annular_loss_string_and_shoe():
    name, string = hy.string_for_hole(8.5)
    assert "8-1/2" in name and string[-1][2] is None and any(c[1] == 7.0 for c in string)
    assert string[-1][3] == 6.625                                          # DP 5" dengan tool joint 6-5/8"
    a, _ = hy.annular_loss(500, 8000, 10, R, 8.5, 8.5, None, string)
    b, _ = hy.annular_loss(500, 8000, 10, R, 8.5, 8.5, 4000, string)      # ID casing = lubang → sama
    c, _ = hy.annular_loss(500, 8000, 10, R, 8.5, 8.681, 4000, string)    # casing sedikit lebih besar → lebih kecil
    assert a == pytest.approx(b) and c < a
    assert hy.annular_loss(500, 9000, 10, R, 8.5, 8.681, 4000, string)[0] > c   # makin dalam makin besar
    assert "17-1/2" in hy.string_for_hole(17.5)[0]          # preset 17-1/2" (tipikal, 28 Nov)
    assert "pendekatan" in hy.string_for_hole(26.0)[0]
    assert hy.string_for_hole(8.5, "BHA_12.25_STD")[0].startswith("BHA 12-1/4")       # preset dari data section
    no_tj = tuple((nm, od, ln, None, j) for nm, od, ln, _, j in string)
    assert hy.annular_loss(500, 8000, 10, R, 8.5, 8.681, 4000, no_tj)[0] < c         # tool joint menambah rugi
    add = hy.ecd_add([500, 500], [8000, 8000], [8000, 8000], [10, 10], R, 8.5, 8.681, 4000, string)
    assert add[0] == pytest.approx(c / (0.052 * 8000))
