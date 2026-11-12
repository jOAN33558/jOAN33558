"""Sección, flexión, inercia efectiva y verificaciones sueltas."""
import pytest

from losas import flechas, flexion
from losas.modelos import Losa, Materiales
from losas.seccion import propiedades
from losas.verificaciones import limites_nervios, retraccion_temperatura

MAT = Materiales(fc=210, fy=4200)
LOSA = Losa("nervada", 20, 5, 10, 50, 96, [12, 14, 16, 18, 20])


def test_seccion_T_de_la_hoja():
    s = propiedades(LOSA)
    assert s.A == pytest.approx(400)
    assert s.yg == pytest.approx(13.75)
    assert s.Ig == pytest.approx(12708.33, abs=0.01)
    assert s.he == pytest.approx(14.502, abs=1e-3)
    assert s.bw_m == pytest.approx(20)


def test_acero_requerido_equilibra_el_momento():
    Mu, b, d = 1783.0, 20.0, 16.7
    As = flexion.acero_requerido(Mu, b, d, 210, 4200)
    a = As * 4200 / (0.85 * 210 * b)
    assert 0.9 * As * 4200 * (d - a / 2) / 100 == pytest.approx(Mu)
    assert flexion.acero_requerido(50000.0, b, d, 210, 4200) is None     # sección insuficiente
    assert flexion.acero_requerido(0.0, b, d, 210, 4200) == 0.0


def test_seccion_insuficiente_no_cumple():
    x = flexion.disenar("prueba", 50000.0, "-", 16.7, MAT, LOSA)
    assert not x.cumple and x.As_req is None and x.notas


def test_dos_varillas_cuando_una_no_alcanza():
    x = flexion.disenar("prueba", 3300.0, "-", 16.5, MAT, LOSA)
    assert x.n == 2 and x.As_u >= x.As_dis * 0.5 - 1e-9
    assert any("no caben" in n for n in x.notas)


def test_inercia_efectiva():
    s = propiedades(LOSA)
    sf = flechas.seccion_fisurada(s, MAT, "+", 1.131, 16.7)
    assert 0 < sf.Icr < sf.Ig
    assert sf.Mcr == pytest.approx(2 * 210**0.5 * s.Ig / 13.75)
    assert flechas.inercia_efectiva(0.5 * sf.Mcr, sf) == sf.Ig          # sin fisurar
    Ie = flechas.inercia_efectiva(3 * sf.Mcr, sf)
    assert sf.Icr < Ie < sf.Ig
    assert flechas.inercia_efectiva(1e9, sf) == pytest.approx(sf.Icr, rel=1e-3)
    # eje neutro de sección rectangular fisurada: b·c²/2 = n·As·(d − c)
    c = flechas.eje_neutro(50, 50, 99, 16.7, 10.0)
    assert 50 * c**2 / 2 == pytest.approx(10.0 * (16.7 - c))


def test_limites_de_nervios():
    assert all(v.cumple for v in limites_nervios(LOSA))
    mala = Losa("nervada", 40, 4, 8, 100, 0, [12])
    estados = [v.cumple for v in limites_nervios(mala)]
    assert estados == [False, False, False, False]


def test_malla_de_retraccion():
    texto = retraccion_temperatura(LOSA, MAT)
    assert texto.startswith("Malla electrosoldada Ø4 mm @ 13 cm")
