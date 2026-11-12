"""Prueba obligatoria 3 y volado con carga de borde."""
import pytest

from conftest import un_pano
from losas.volado import longitud_desarrollo, solicitaciones


def test_volado_carga_uniforme():
    """Prueba obligatoria 3: M = q·L²/2 y V = q·L."""
    D, L, luz = 500.0, 200.0, 1.5
    q = 1.2 * D + 1.6 * L
    Mu, Vu, combo, M_D, M_L = solicitaciones(D, L, luz)
    assert Mu == pytest.approx(q * luz**2 / 2)
    assert Vu == pytest.approx(q * luz)
    assert combo == "1,2D + 1,6L"
    assert M_D == pytest.approx(D * luz**2 / 2) and M_L == pytest.approx(L * luz**2 / 2)


def test_volado_gobierna_1_4D_sin_carga_viva():
    Mu, Vu, combo, _, _ = solicitaciones(600.0, 0.0, 1.0)
    assert combo == "1,4D"
    assert Mu == pytest.approx(1.4 * 600 / 2) and Vu == pytest.approx(1.4 * 600)


def test_volado_con_carga_de_borde():
    D, L, luz, P = 500.0, 200.0, 1.2, 150.0
    q, Pu = 1.2 * D + 1.6 * L, 1.2 * P
    Mu, Vu, _, _, _ = solicitaciones(D, L, luz, P_D=P)
    assert Mu == pytest.approx(q * luz**2 / 2 + Pu * luz)
    assert Vu == pytest.approx(q * luz + Pu)


def test_volado_dentro_del_piso():
    r = un_pano(4.0, 5.0, {"norte": "continuo", "este": "continuo"},
                pano={"volado": {"borde": "sur", "longitud": 1.20, "carga_borde": 150}})
    v = r.volados[0]
    assert v.L == pytest.approx(1.20 - 0.15)           # hasta la cara de la viga
    q = r.cargas.qu
    assert v.Mu == pytest.approx(q * v.L**2 / 2 + 1.2 * 150 * v.L)
    assert v.Vu == pytest.approx(q * v.L + 1.2 * 150)
    # el borde con volado se clasifica discontinuo y se diseña con el momento del volado
    assert r.pano.cond["sur"] == "discontinuo" and r.tipo == 6
    assert r.M_dis["sur"] == pytest.approx(v.Mu) and r.origen["sur"] == "volado"
    assert not r.flexion["neg_sur"].constructivo
    # el acero negativo se prolonga dentro del paño al menos ld
    assert v.prolongacion >= v.ld / 100
    assert v.prolongacion <= 5.0
    assert any(c.nombre.startswith("Altura h >= L/8") for c in v.checks)     # nervios: L/8
    assert v.flechas is not None and v.cortante is not None


def test_altura_minima_de_volado_macizo_es_L_sobre_10():
    r = un_pano(4.0, 5.0, losa={"tipo": "maciza", "altura": 15},
                pano={"volado": {"borde": "este", "longitud": 1.0, "medida": "cara"}})
    v = r.volados[0]
    assert v.L == pytest.approx(1.0)
    hmin = next(c for c in v.checks if c.nombre.startswith("Altura"))
    assert hmin.limite == pytest.approx(100 / 10)


def test_longitud_de_desarrollo():
    assert longitud_desarrollo(12, 210, 4200) == pytest.approx(4200 / (6.6 * 210**0.5) * 1.2)
    assert longitud_desarrollo(8, 350, 4200) == 30.0       # mínimo de 30 cm
