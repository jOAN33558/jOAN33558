"""Viga continua sobre apoyos simples por el método de rigidez (pendiente-deflexión).

Franja de 1 m de losa. Luces en m, cargas uniformes en kg/m, momentos en kg·m.
Los momentos negativos (sobre apoyo) se devuelven como magnitud positiva.
"""
from __future__ import annotations

from dataclasses import dataclass

import numpy as np


@dataclass
class Solucion:
    M_apoyo: list[float]     # magnitud del momento negativo en cada apoyo (n+1)
    M_pos: list[float]       # momento positivo máximo en cada vano
    V_izq: list[float]       # cortante en el extremo izquierdo de cada vano (al eje)
    V_der: list[float]       # cortante en el extremo derecho de cada vano (al eje)

    def flecha_centro(self, i: int, luz: float, w: float, EI: float) -> float:
        """Flecha en el centro del vano i (cm). luz en m, w en kg/m, EI en kg·cm²."""
        L = luz * 100.0
        wc = w / 100.0                                   # kg/cm
        Ma, Mb = self.M_apoyo[i] * 100.0, self.M_apoyo[i + 1] * 100.0
        return 5 * wc * L**4 / (384 * EI) - (Ma + Mb) * L**2 / (16 * EI)


def resolver(luces: list[float], w: list[float], M_vol_izq: float = 0.0,
             M_vol_der: float = 0.0) -> Solucion:
    """Resuelve la viga con carga uniforme w[i] en cada vano.

    ``M_vol_izq`` y ``M_vol_der`` son los momentos (magnitud) que los volados
    transmiten a los apoyos extremos. Sin volado el extremo es articulado.
    EI es constante (sección prismática), por lo que no interviene en los momentos.
    """
    n = len(luces)
    if n == 0 or len(w) != n:
        raise ValueError("Deben darse tantas cargas como vanos.")
    K = np.zeros((n + 1, n + 1))
    F = np.zeros(n + 1)
    for i, (L, q) in enumerate(zip(luces, w)):
        k = 1.0 / L
        K[i, i] += 4 * k
        K[i, i + 1] += 2 * k
        K[i + 1, i] += 2 * k
        K[i + 1, i + 1] += 4 * k
        mep = q * L**2 / 12
        F[i] += mep            # -MEP_ab = +wL²/12
        F[i + 1] -= mep        # -MEP_ba = -wL²/12
    F[0] -= M_vol_izq          # equilibrio del nudo con el volado izquierdo
    F[n] += M_vol_der
    theta = np.linalg.solve(K, F)
    M_apoyo = [0.0] * (n + 1)
    M_pos, V_izq, V_der = [], [], []
    for i, (L, q) in enumerate(zip(luces, w)):
        k = 1.0 / L
        m_ab = 2 * k * (2 * theta[i] + theta[i + 1]) - q * L**2 / 12
        m_ba = 2 * k * (theta[i] + 2 * theta[i + 1]) + q * L**2 / 12
        izq, der = -m_ab, m_ba          # magnitudes de momento negativo en los extremos
        M_apoyo[i] = max(M_apoyo[i], izq) if i else izq
        M_apoyo[i + 1] = der
        va = q * L / 2 + (izq - der) / L
        vb = q * L - va
        V_izq.append(va)
        V_der.append(vb)
        if q > 0 and 0 < va / q < L:
            M_pos.append(max(0.0, -izq + va**2 / (2 * q)))
        else:
            M_pos.append(max(0.0, -izq, -der))
    M_apoyo = [float(abs(m)) if abs(m) > 1e-9 else 0.0 for m in M_apoyo]
    return Solucion(M_apoyo, M_pos, V_izq, V_der)


def patrones(n: int) -> list[list[bool]]:
    """Patrones de carga viva para n tramos (ACI 318-19, 6.4.2): todos, alternados
    y dos tramos adyacentes cargados con alternancia en el resto."""
    todos = [True] * n
    lista = [todos, [i % 2 == 0 for i in range(n)], [i % 2 == 1 for i in range(n)]]
    for j in range(1, n):          # apoyo entre los tramos j-1 y j
        p = [False] * n
        for i in range(n):
            if i in (j - 1, j) or (i > j and (i - j) % 2 == 0) or (i < j - 1 and (j - 1 - i) % 2 == 0):
                p[i] = True
        lista.append(p)
    unicos = []
    for p in lista:
        if p not in unicos:
            unicos.append(p)
    return unicos
