"""Losa en una dirección: franja continua de 1 m de ancho.

Se usan los coeficientes de ACI 318-19 6.5 cuando se cumplen sus condiciones;
en caso contrario, viga continua por rigidez con alternancia de carga viva.
"""
from __future__ import annotations

from dataclasses import dataclass, field

from .cargas import mayorar
from .viga_continua import patrones, resolver

METODO_ACI = "Coeficientes ACI 318-19, 6.5"
METODO_RIGIDEZ = "Viga continua por rigidez (ACI 318-19, 6.6)"


@dataclass
class Voladizo:
    L: float          # m, hasta el eje del apoyo
    D: float          # kg/m²
    Lv: float         # kg/m², viva
    P_D: float = 0.0  # kg/m en la punta
    P_L: float = 0.0

    def momento(self, fD: float, fL: float) -> float:
        return (fD * self.D + fL * self.Lv) * self.L**2 / 2 + (fD * self.P_D + fL * self.P_L) * self.L


@dataclass
class Franja:
    ids: list[str]
    luces: list[float]            # m, centro a centro
    D: list[float]
    L: list[float]
    bv: list[float]               # cm, ancho de viga en cada apoyo (n+1)
    vol_izq: Voladizo | None = None
    vol_der: Voladizo | None = None

    @property
    def n(self) -> int:
        return len(self.luces)

    @property
    def ln(self) -> list[float]:
        return [L - (self.bv[i] + self.bv[i + 1]) / 200 for i, L in enumerate(self.luces)]


@dataclass
class ResultadoFranja:
    metodo: str
    razones: list[str]                       # por qué no aplica ACI 6.5
    M_apoyo: list[float]                     # kg·m/m, magnitud, n+1
    M_pos: list[float]                       # kg·m/m por vano
    V_izq: list[float]                       # kg/m en la cara del apoyo izquierdo
    V_der: list[float]
    wu: list[float]
    servicio: list[dict] = field(default_factory=list)   # por vano: nivel -> (flecha/EI=1, M+)


def condiciones_aci(fr: Franja) -> list[str]:
    """Condiciones de ACI 318-19 6.5.1 que NO se cumplen (lista vacía = aplica)."""
    r = []
    if fr.n < 2:
        r.append("hay menos de dos vanos (6.5.1d)")
    if fr.vol_izq or fr.vol_der:
        r.append("la franja tiene volado, no cubierto por los coeficientes")
    ln = fr.ln
    for i in range(fr.n - 1):
        if max(ln[i], ln[i + 1]) > 1.2 * min(ln[i], ln[i + 1]) + 1e-9:
            r.append(f"las luces de {fr.ids[i]} y {fr.ids[i + 1]} difieren más de 20 % (6.5.1e)")
    for i in range(fr.n):
        if fr.L[i] > 3 * fr.D[i] + 1e-9:
            r.append(f"en {fr.ids[i]} la carga viva supera 3 veces la permanente (6.5.1c)")
    return r


def _coeficientes_aci(fr: Franja) -> ResultadoFranja:
    n, ln = fr.n, fr.ln
    wu = [mayorar(d, l)[0] for d, l in zip(fr.D, fr.L)]
    M_pos = [wu[i] * ln[i] ** 2 / (14 if i in (0, n - 1) else 16) for i in range(n)]
    M_ap = [0.0] * (n + 1)
    M_ap[0] = wu[0] * ln[0] ** 2 / 24          # apoyo exterior monolítico con viga de borde
    M_ap[n] = wu[-1] * ln[-1] ** 2 / 24
    for j in range(1, n):
        lprom = (ln[j - 1] + ln[j]) / 2
        w = max(wu[j - 1], wu[j])
        den = 9 if n == 2 else (10 if j in (1, n - 1) else 11)
        M_ap[j] = w * lprom**2 / den
    V_izq = [wu[i] * ln[i] / 2 * (1.15 if (i == n - 1 and n > 1) else 1.0) for i in range(n)]
    V_der = [wu[i] * ln[i] / 2 * (1.15 if (i == 0 and n > 1) else 1.0) for i in range(n)]
    return ResultadoFranja(METODO_ACI, [], M_ap, M_pos, V_izq, V_der, wu)


def _cargas_caso(fr: Franja, fD: float, fL: float, patron: list[bool] | None):
    """Cargas por vano y momentos de volado para un caso. El patrón cubre la lista
    extendida [volado izq] + vanos + [volado der]."""
    k = 1 if fr.vol_izq else 0
    on = (lambda i: True) if patron is None else (lambda i: patron[i])
    w = [fD * fr.D[i] + (fL * fr.L[i] if on(i + k) else 0.0) for i in range(fr.n)]
    mi = fr.vol_izq.momento(fD, fL if on(0) else 0.0) if fr.vol_izq else 0.0
    md = fr.vol_der.momento(fD, fL if on(fr.n + k) else 0.0) if fr.vol_der else 0.0
    return w, mi, md


def _rigidez(fr: Franja, razones: list[str]) -> ResultadoFranja:
    n = fr.n
    ext = n + (1 if fr.vol_izq else 0) + (1 if fr.vol_der else 0)
    casos = [(1.4, 0.0, None)] + [(1.2, 1.6, p) for p in patrones(ext)]
    M_ap, M_pos = [0.0] * (n + 1), [0.0] * n
    V_izq, V_der, wu = [0.0] * n, [0.0] * n, [0.0] * n
    for fD, fL, patron in casos:
        w, mi, md = _cargas_caso(fr, fD, fL, patron)
        sol = resolver(fr.luces, w, mi, md)
        M_ap = [max(a, b) for a, b in zip(M_ap, sol.M_apoyo)]
        M_pos = [max(a, b) for a, b in zip(M_pos, sol.M_pos)]
        for i in range(n):
            wu[i] = max(wu[i], w[i])
            V_izq[i] = max(V_izq[i], sol.V_izq[i] - w[i] * fr.bv[i] / 200)
            V_der[i] = max(V_der[i], sol.V_der[i] - w[i] * fr.bv[i + 1] / 200)
    return ResultadoFranja(METODO_RIGIDEZ, razones, M_ap, M_pos, V_izq, V_der, wu)


def _servicio(fr: Franja, i: int, psi: float) -> dict:
    """Flecha elástica en el centro del vano i (con EI = 1 kg·cm²) y M+ de servicio,
    para D, D+L y carga sostenida. La viva se coloca en el vano y en vanos alternos."""
    k = 1 if fr.vol_izq else 0
    ext = fr.n + k + (1 if fr.vol_der else 0)
    patron = [(j - (i + k)) % 2 == 0 for j in range(ext)]
    niveles = {}
    for nombre, fL in (("D", 0.0), ("DL", 1.0), ("SOST", psi)):
        w, mi, md = _cargas_caso(fr, 1.0, fL, patron)
        sol = resolver(fr.luces, w, mi, md)
        niveles[nombre] = (sol.flecha_centro(i, fr.luces[i], w[i], 1.0), sol.M_pos[i])
    return niveles


def analizar(fr: Franja, psi: float = 0.0) -> ResultadoFranja:
    razones = condiciones_aci(fr)
    res = _coeficientes_aci(fr) if not razones else _rigidez(fr, razones)
    res.servicio = [_servicio(fr, i, psi) for i in range(fr.n)]
    return res
