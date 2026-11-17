"""Deducción del tipo de paño (1 a 18) y tablas de coeficientes."""
import pytest

from losas import tablas
from losas.geometria import deducir_tipo

C, D, L = "continuo", "discontinuo", "libre"

CASOS = [
    ((C, C), (C, C), 1), ((C, D), (C, C), 2), ((C, C), (C, D), 3), ((D, D), (C, C), 4),
    ((C, C), (D, D), 5), ((C, D), (C, D), 6), ((C, D), (D, D), 7), ((D, D), (C, D), 8),
    ((D, D), (D, D), 9), ((C, L), (C, C), 10), ((C, C), (C, L), 11), ((C, L), (C, D), 12),
    ((C, D), (C, L), 13), ((C, L), (D, D), 14), ((D, D), (C, L), 15), ((D, L), (D, D), 16),
    ((D, D), (D, L), 17), ((C, L), (C, L), 18),
]


@pytest.mark.parametrize("largos, cortos, tipo", CASOS)
def test_los_18_tipos(largos, cortos, tipo):
    assert deducir_tipo(largos, cortos) == tipo
    # el orden dentro de cada par de bordes opuestos no cambia el tipo
    assert deducir_tipo(largos[::-1], cortos[::-1]) == tipo


@pytest.mark.parametrize("largos, cortos", [
    ((D, L), (C, C)), ((D, L), (C, D)), ((C, C), (D, L)), ((D, L), (C, L)),
    ((L, L), (C, C)), ((C, L), (D, L)), ((L, L), (L, C)),
])
def test_combinaciones_no_tabuladas(largos, cortos):
    assert deducir_tipo(largos, cortos) is None


@pytest.mark.parametrize("tabla", ["nervada", "maciza"])
def test_tablas_completas_y_simetricas(tabla):
    datos = tablas.cargar(tabla)
    assert sorted(datos) == list(range(1, 19))
    assert all([f["beta"] for f in filas] == [0.5, 0.6, 0.7, 0.8, 0.9, 1.0]
               for filas in datos.values())
    espejo = {"my_neg": "mx_neg", "my_pos": "mx_pos", "myb_neg": "mxb_neg", "myb_pos": "mxb_pos",
              "delta": "delta"}
    for a, b in [(1, 1), (2, 3), (4, 5), (6, 6), (7, 8), (9, 9), (10, 11), (12, 13), (14, 15),
                 (16, 17), (18, 18)]:
        ca, cb = tablas.coeficientes(tabla, a, 1.0), tablas.coeficientes(tabla, b, 1.0)
        for k, v in espejo.items():
            assert ca[k] == cb[v], (tabla, a, b, k)


def test_valores_de_la_tabla_9_7():
    c = tablas.coeficientes("nervada", 6, 0.8)
    assert (c["delta"], c["my_neg"], c["my_pos"], c["mx_neg"], c["mx_pos"]) == (572, 1120, 621, 852, 369)
    # error de imprenta corregido: paño 14, mx+ con Lx/Ly = 0,5 (impreso 8187)
    assert tablas.coeficientes("nervada", 14, 0.5)["mx_pos"] == 916
    assert tablas.coeficientes("nervada", 18, 0.5)["myb_neg"] == 5625


def test_valores_de_la_tabla_9_5():
    c = tablas.coeficientes("maciza", 1, 1.0)
    assert (c["delta"], c["my_neg"], c["my_pos"]) == (147, 512, 214)
    assert tablas.coeficientes("maciza", 16, 0.5)["delta"] == 11840


def test_fuera_de_rango():
    with pytest.raises(ValueError):
        tablas.coeficientes("nervada", 6, 0.45)
    with pytest.raises(ValueError):
        tablas.coeficientes("nervada", 19, 0.8)
