"""Utilidades comunes de las pruebas."""
import copy
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from losas import disenar_piso, piso_desde_dict  # noqa: E402

# Datos de la hoja de referencia (Losas_Alivianadas_Tabla_9.7.xlsx)
BASE = {
    "materiales": {"fc": 210, "fy": 4200, "peso_hormigon": 2400, "recubrimiento": 2.5},
    "losa": {"tipo": "nervada", "altura": 20, "loseta": 5, "ancho_nervio": 10,
             "separacion_nervios": 50, "peso_bloques": 96},
    "cargas": {"acabados": 0, "paredes": 0, "otras": 150, "viva": 250},
    "vigas": {"b": 30, "h": 35},
}


def armar(panos, dist_x, dist_y, **cambios):
    """Arma el diccionario de entrada con ejes A, B, C... en X y 1, 2, 3... en Y."""
    d = copy.deepcopy(BASE)
    d["ejes"] = {"x": {"nombres": [chr(65 + i) for i in range(len(dist_x) + 1)],
                       "distancias": dist_x},
                 "y": {"nombres": [str(i + 1) for i in range(len(dist_y) + 1)],
                       "distancias": dist_y}}
    d["panos"] = panos
    for seccion, valores in cambios.items():
        d[seccion] = {**d.get(seccion, {}), **valores} if isinstance(valores, dict) else valores
    return d


def calcular(panos, dist_x, dist_y, **cambios):
    return disenar_piso(piso_desde_dict(armar(panos, dist_x, dist_y, **cambios)))


def un_pano(lx, ly, bordes=None, **cambios):
    """Un solo paño P1 entre los ejes A-B y 1-2."""
    pano = {"id": "P1", "ejes_x": ["A", "B"], "ejes_y": ["1", "2"], "bordes": bordes or {}}
    pano.update(cambios.pop("pano", {}))
    return calcular([pano], [lx], [ly], **cambios).panos["P1"]


@pytest.fixture
def referencia():
    """Paño de la hoja de referencia: 4 x 5 m, tipo 6, Lx/Ly = 0,8."""
    return un_pano(4.0, 5.0, {"norte": "continuo", "este": "continuo",
                              "sur": "discontinuo", "oeste": "discontinuo"})
