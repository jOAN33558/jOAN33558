"""Paño cuadrado, paño con borde libre, interpolación y losa maciza."""
import pytest

from conftest import un_pano
from losas import tablas

TODO_CONTINUO = {b: "continuo" for b in ("norte", "sur", "este", "oeste")}


def test_pano_cuadrado():
    r = un_pano(5.0, 5.0, TODO_CONTINUO)
    assert r.tipo == 1 and r.beta == pytest.approx(1.0)
    k = 0.0001 * r.cargas.qu * 25
    assert r.M_pos["corta"] == pytest.approx(k * 258)
    assert r.M_pos["larga"] == pytest.approx(r.M_pos["corta"])       # simetría
    assert {round(m, 6) for m in r.M_dis.values()} == {round(k * 564, 6)}
    assert r.flexion["neg_norte"].Mu == pytest.approx(r.flexion["neg_este"].Mu)


def test_pano_con_borde_libre():
    bordes = {"norte": "continuo", "sur": "continuo", "oeste": "continuo", "este": "libre"}
    r = un_pano(4.0, 5.0, bordes)
    assert r.tipo == 10                           # borde largo libre, resto continuo
    c = tablas.coeficientes("nervada", 10, 0.8)
    k = 0.0001 * r.cargas.qu * 16
    # envolvente con los momentos de borde libre (mxb gobierna sobre mx)
    assert r.M_dis["norte"] == pytest.approx(k * c["mxb_neg"])
    assert r.M_pos["larga"] == pytest.approx(k * c["mxb_pos"])
    assert r.M_dis["oeste"] == pytest.approx(k * c["my_neg"])
    assert "neg_este" not in r.flexion            # el borde libre no lleva acero negativo
    assert "este" not in r.M_dis
    # con un borde largo libre toda la franja corta descarga en el apoyo opuesto
    assert r.V_cara["general"] == pytest.approx(r.cargas.qu * (4.0 - 0.15))


def test_borde_corto_libre():
    bordes = {"norte": "libre", "sur": "continuo", "oeste": "discontinuo", "este": "discontinuo"}
    assert un_pano(4.0, 5.0, bordes).tipo == 15


def test_interpolacion_lineal():
    a, b = tablas.coeficientes("nervada", 6, 0.8), tablas.coeficientes("nervada", 6, 0.9)
    m = tablas.coeficientes("nervada", 6, 0.85)
    for k in tablas.COEFICIENTES:
        assert m[k] == pytest.approx((a[k] + b[k]) / 2)
    r = un_pano(4.25, 5.0, {"norte": "continuo", "este": "continuo"})
    assert r.M_pos["corta"] == pytest.approx(0.0001 * r.cargas.qu * m["my_pos"] * 4.25**2)


def test_orientacion_cuando_la_luz_corta_es_Y():
    r = un_pano(5.0, 4.0, {"norte": "continuo", "este": "continuo"})
    assert r.dir_corta == "Y" and r.Lx == 4.0 and r.Ly == 5.0 and r.tipo == 6
    assert r.M_dis["norte"] > r.M_dis["este"]     # el borde largo (norte) lleva My(-)


def test_losa_maciza_usa_tabla_9_5():
    r = un_pano(4.0, 4.0, losa={"tipo": "maciza", "altura": 15})
    assert r.tipo == 9
    q = r.cargas.qu
    assert r.cargas.D == pytest.approx(0.15 * 2400 + 150)
    assert r.M_pos["corta"] == pytest.approx(0.0001 * q * 443 * 16)
    f = r.flexion["pos_corta"]
    assert f.armado.startswith("Ø") and "@" in f.armado
    assert f.b == 100 and f.As_col >= f.As_dis - 1e-9
    assert f.As_min == pytest.approx(0.0018 * 100 * 15)
    assert r.cortante.vc == pytest.approx(0.53 * 210**0.5)    # sin aumento de nervios


def test_flecha_fisurada_no_menor_que_la_elastica(referencia):
    r = referencia
    assert 0 < r.flechas.Ie_Ig <= 1.0
    c, E, he = r.cargas, 15000 * 210**0.5, 14.50218
    elastica = 0.0001 * (c.qs / 10000) * 572 * 400**4 / (E * he**3)
    assert r.flechas.delta_L >= elastica * c.L / c.qs - 1e-9
    assert r.flechas.lim_L == pytest.approx(400 / 360)
    assert r.flechas.lim_lp == pytest.approx(400 / 480)
