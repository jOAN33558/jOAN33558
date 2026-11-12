"""Prueba obligatoria 1: reproducir el paño de la hoja de referencia."""
import pytest


def test_clasificacion_y_cargas(referencia):
    r = referencia
    assert r.clasificacion == "Bidireccional"
    assert r.tipo == 6
    assert r.beta == pytest.approx(0.8)
    assert r.cargas.D == pytest.approx(495.6)
    assert r.cargas.qu == pytest.approx(994.72)
    assert r.cargas.combo == "1,2D + 1,6L"


def test_momentos_de_la_hoja(referencia):
    r = referencia
    assert round(r.M_dis["este"]) == 1783       # My(-), borde largo continuo
    assert round(r.M_pos["corta"]) == 988       # My(+)
    assert round(r.M_dis["norte"]) == 1356      # Mx(-), borde corto continuo
    assert round(r.M_pos["larga"]) == 587       # Mx(+)
    assert r.M_dis["oeste"] == 0 and r.M_dis["sur"] == 0


def test_armado_por_nervio(referencia):
    f = referencia.flexion
    assert f["neg_este"].armado == "1Ø16"
    assert f["pos_corta"].armado == "1Ø12"
    assert f["neg_norte"].armado == "1Ø14"
    assert f["pos_larga"].armado == "1Ø12"
    assert all(x.cumple for x in f.values())
    assert all(x.eps_t >= 0.005 for x in f.values())


def test_peraltes_y_ancho_comprimido(referencia):
    r = referencia
    assert r.d["corta"] == pytest.approx(16.7)     # 20 - 2,5 - 1,6/2
    assert r.d["larga"] == pytest.approx(15.2)     # 20 - 2,5 - 1,6 - 1,4/2
    assert r.flexion["neg_este"].b == pytest.approx(20.0)    # solo nervios
    assert r.flexion["pos_corta"].b == pytest.approx(100.0)


def test_cortante_como_la_hoja(referencia):
    c = referencia.cortante
    assert c.Vu == pytest.approx(994.72 * (2.0 - 0.15 - 0.167))
    assert c.vu == pytest.approx(6.683, abs=1e-3)
    assert c.vc == pytest.approx(1.1 * 0.53 * 210 ** 0.5)
    assert c.estado == "CUMPLE"


def test_altura_equivalente(referencia):
    he = next(c for c in referencia.checks if c.nombre.startswith("Altura equivalente"))
    assert he.valor == pytest.approx(14.50, abs=0.01)
    assert he.limite == pytest.approx(12.5)
    assert he.cumple
