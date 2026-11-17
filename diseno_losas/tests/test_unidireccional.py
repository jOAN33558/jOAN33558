"""Prueba obligatoria 2 y casos de losa en una dirección."""
import pytest

from conftest import calcular, un_pano
from losas import unidireccional as uni
from losas.viga_continua import patrones, resolver


def test_un_vano_simplemente_apoyado_da_qL2_sobre_8():
    """Prueba obligatoria 2."""
    r = un_pano(2.0, 6.0)        # Lx/Ly = 0,33; todos los bordes discontinuos
    assert r.clasificacion == "Unidireccional"
    assert r.metodo == uni.METODO_RIGIDEZ
    q = r.cargas.qu
    assert r.M_pos["corta"] == pytest.approx(q * 2.0**2 / 8)
    assert r.M_borde["oeste"] == pytest.approx(0.0, abs=1e-6)
    assert r.M_borde["este"] == pytest.approx(0.0, abs=1e-6)


def test_viga_simple_momento_y_cortante():
    s = resolver([5.0], [1000.0])
    assert s.M_pos[0] == pytest.approx(1000 * 25 / 8)
    assert s.V_izq[0] == pytest.approx(2500) and s.V_der[0] == pytest.approx(2500)
    assert s.M_apoyo == [0.0, 0.0]


def test_dos_vanos_desiguales_contra_solucion_exacta():
    L1, L2, w = 4.0, 6.0, 800.0
    s = resolver([L1, L2], [w, w])
    assert s.M_apoyo[1] == pytest.approx(w * (L1**3 + L2**3) / (8 * (L1 + L2)))


def test_volado_en_la_viga_continua():
    s = resolver([4.0], [0.0], M_vol_izq=500.0)
    assert s.M_apoyo[0] == pytest.approx(500.0)
    assert s.M_apoyo[1] == pytest.approx(0.0, abs=1e-9)


def test_flecha_viga_simple():
    s = resolver([4.0], [1000.0])
    EI = 2.0e10
    assert s.flecha_centro(0, 4.0, 1000.0, EI) == pytest.approx(5 * 10 * 400**4 / (384 * EI))


def test_patrones_de_carga_viva():
    p = patrones(3)
    assert [True, True, True] in p and [True, False, True] in p and [False, True, False] in p
    assert [True, True, False] in p and [False, True, True] in p


def test_coeficientes_aci_cuando_cumple_condiciones():
    """Dos vanos iguales de 2 x 6 m: aplica ACI 318-19 6.5."""
    panos = [{"id": "P1", "ejes_x": ["A", "B"], "ejes_y": ["1", "2"]},
             {"id": "P2", "ejes_x": ["B", "C"], "ejes_y": ["1", "2"]}]
    res = calcular(panos, [2.0, 2.0], [6.0])
    r = res.panos["P1"]
    assert r.metodo == uni.METODO_ACI
    q, ln = r.cargas.qu, 2.0 - 0.30
    assert r.M_borde["este"] == pytest.approx(q * ln**2 / 9)     # primer apoyo interior, 2 vanos
    assert r.M_pos["corta"] == pytest.approx(q * ln**2 / 14)     # vano extremo
    assert r.M_borde["oeste"] == pytest.approx(q * ln**2 / 24)   # viga de borde
    assert r.V_cara["este"] == pytest.approx(1.15 * q * ln / 2)
    assert res.panos["P2"].M_dis["oeste"] == pytest.approx(r.M_dis["este"])


def test_luces_distintas_usan_rigidez():
    panos = [{"id": "P1", "ejes_x": ["A", "B"], "ejes_y": ["1", "2"]},
             {"id": "P2", "ejes_x": ["B", "C"], "ejes_y": ["1", "2"]}]
    r = calcular(panos, [2.0, 3.0], [7.0]).panos["P1"]
    assert r.metodo == uni.METODO_RIGIDEZ
    fr = uni.Franja(["P1", "P2"], [2.0, 3.0], [500, 500], [200, 200], [30, 30, 30])
    assert any("20 %" in x for x in uni.condiciones_aci(fr))


def test_altura_minima_tabla_9_3_1_1():
    r = un_pano(2.0, 6.0)
    v = next(c for c in r.checks if c.nombre.startswith("Altura h"))
    assert v.limite == pytest.approx(200 / 16)       # nervios, simplemente apoyado
    macizo = un_pano(2.0, 6.0, losa={"tipo": "maciza", "altura": 12})
    v = next(c for c in macizo.checks if c.nombre.startswith("Altura h"))
    assert v.limite == pytest.approx(200 / 20)       # maciza, Tabla 7.3.1.1


def test_apoyada_en_dos_bordes_es_unidireccional():
    r = un_pano(4.0, 5.0, {"norte": "libre", "sur": "libre"})
    assert r.clasificacion == "Unidireccional" and r.dir_corta == "X"
    assert r.M_pos["corta"] == pytest.approx(r.cargas.qu * 16 / 8)
