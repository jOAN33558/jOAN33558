"""Coeficientes para losas rectangulares sustentadas perimetralmente.

- Tabla 9.7 a-d: losas nervadas.
- Tabla 9.5 a-d: losas macizas (mu = 0,20).

Los valores se transcribieron de los PDF entregados y se guardan en ``datos/``.
Única corrección: Tabla 9.7, paño 14, mx+ para Lx/Ly = 0,5 está impreso 8187
(error de imprenta) y se usa 916.
"""
from __future__ import annotations

import csv
from functools import lru_cache
from pathlib import Path

DATOS = Path(__file__).parent / "datos"
ARCHIVOS = {"nervada": "tabla_9_7_nervadas.csv", "maciza": "tabla_9_5_macizas.csv"}
NOMBRE_TABLA = {"nervada": "Tabla 9.7 (losas nervadas)",
                "maciza": "Tabla 9.5 (losas macizas, mu = 0,20)"}
COEFICIENTES = ("delta", "my_neg", "my_pos", "mx_neg", "mx_pos",
                "myb_neg", "myb_pos", "mxb_neg", "mxb_pos")
BETA_MIN, BETA_MAX = 0.5, 1.0


@lru_cache(maxsize=None)
def cargar(tabla: str) -> dict[int, list[dict]]:
    """Devuelve {tipo: filas ordenadas por beta creciente}."""
    if tabla not in ARCHIVOS:
        raise ValueError(f"Tabla desconocida: {tabla!r}")
    filas: dict[int, list[dict]] = {}
    with open(DATOS / ARCHIVOS[tabla], newline="", encoding="utf-8") as f:
        for r in csv.DictReader(f):
            fila = {k: float(v) for k, v in r.items()}
            filas.setdefault(int(fila["tipo"]), []).append(fila)
    for lista in filas.values():
        lista.sort(key=lambda r: r["beta"])
    return filas


def coeficientes(tabla: str, tipo: int, beta: float) -> dict[str, float]:
    """Coeficientes interpolados linealmente en Lx/Ly (válido de 0,5 a 1,0)."""
    if not 1 <= tipo <= 18:
        raise ValueError(f"Tipo de paño fuera de la tabla: {tipo}")
    if beta < BETA_MIN - 1e-9 or beta > BETA_MAX + 1e-9:
        raise ValueError(
            f"Lx/Ly = {beta:.3f} fuera del rango de la tabla (0,5 a 1,0)")
    beta = min(BETA_MAX, max(BETA_MIN, beta))
    filas = cargar(tabla)[tipo]
    for inf, sup in zip(filas, filas[1:]):
        if inf["beta"] - 1e-9 <= beta <= sup["beta"] + 1e-9:
            t = (beta - inf["beta"]) / (sup["beta"] - inf["beta"])
            return {k: inf[k] + t * (sup[k] - inf[k]) for k in COEFICIENTES}
    raise ValueError(f"No se pudo interpolar Lx/Ly = {beta}")  # pragma: no cover
