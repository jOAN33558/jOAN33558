"""Flechas con cargas de servicio e inercia efectiva (ACI 318-19, 24.2).

La flecha elástica (sección bruta) se amplifica por Ig/Ie, con Ie de la
Tabla 24.2.3.5 y fr = 2·√f'c (kg/cm²). La flecha diferida usa λΔ = ξ/(1+50ρ').
"""
from __future__ import annotations

from dataclasses import dataclass
from math import sqrt

from .memoria import Memoria, estado, fmt
from .modelos import Materiales, ResultadoFlechas
from .seccion import Seccion


@dataclass
class SeccionFisurada:
    Ig: float     # cm4 por unidad (nervio o metro)
    yt: float     # cm, del centroide a la fibra traccionada
    Icr: float    # cm4 por unidad
    Mcr: float    # kg·cm por unidad
    c: float      # cm, eje neutro fisurado


def eje_neutro(b: float, bw: float, tf: float, d: float, nAs: float) -> float:
    """Eje neutro de la sección fisurada con ala comprimida de ancho b y espesor tf."""
    c = (-nAs + sqrt(nAs**2 + 2 * b * nAs * d)) / b
    if c <= tf or b == bw:
        return c
    A, B, C = bw / 2, (b - bw) * tf + nAs, -((b - bw) * tf**2 / 2 + nAs * d)
    return (-B + sqrt(B**2 - 4 * A * C)) / (2 * A)


def seccion_fisurada(sec: Seccion, mat: Materiales, signo: str, As_u: float, d: float) -> SeccionFisurada:
    """Propiedades fisuradas por unidad. Momento positivo: ala comprimida;
    negativo: comprime el alma (nervio) por abajo."""
    nAs = mat.n * As_u
    if signo == "+":
        b, bw, tf, yt = sec.b_ala, sec.bw, sec.el, sec.yg
    else:
        b, bw, tf, yt = sec.bw, sec.bw, sec.h, sec.h - sec.yg
    c = eje_neutro(b, bw, tf, d, nAs)
    Icr = b * c**3 / 3 + nAs * (d - c) ** 2
    if c > tf and b != bw:
        Icr -= (b - bw) * (c - tf) ** 3 / 3
    Icr = min(Icr, sec.Ig)
    return SeccionFisurada(sec.Ig, yt, Icr, 2.0 * sqrt(mat.fc) * sec.Ig / yt, c)


def inercia_efectiva(Ma: float, sf: SeccionFisurada) -> float:
    """ACI 318-19, Tabla 24.2.3.5."""
    if Ma <= (2 / 3) * sf.Mcr:
        return sf.Ig
    return sf.Icr / (1 - ((2 / 3) * sf.Mcr / Ma) ** 2 * (1 - sf.Icr / sf.Ig))


def evaluar(niveles: dict[str, tuple[float, float]], sf: SeccionFisurada, luz_cm: float,
            den_lp: int, lam: float, mem: Memoria | None = None,
            nombre_luz: str = "Lx") -> ResultadoFlechas:
    """Calcula flechas inmediata por viva y diferida.

    ``niveles`` contiene, para "D", "DL" y "SOST", la flecha elástica con Ig (cm) y el
    momento de servicio en la sección crítica (kg·cm por unidad).
    """
    (dD, MD), (dDL, MDL), (dS, MS) = niveles["D"], niveles["DL"], niveles["SOST"]
    Ie_D, Ie_DL, Ie_S = (inercia_efectiva(M, sf) for M in (MD, MDL, MS))
    fD, fDL = dD * sf.Ig / Ie_D, dDL * sf.Ig / Ie_DL
    fL = abs(fDL - fD)                 # magnitudes: un vano corto puede levantarse
    fS = abs(dS * sf.Ig / Ie_S)
    flp = lam * fS + fL
    res = ResultadoFlechas(fL, luz_cm / 360, flp, luz_cm / den_lp, Ie_DL / sf.Ig)
    if mem:
        mem.paso("Momento de fisuración", "Mcr = fr·Ig/yt,  fr = 2·√f'c",
                 f"2·√f'c·{fmt(sf.Ig)}/{fmt(sf.yt)}", sf.Mcr / 100, "kg·m",
                 referencia="ACI 318-19, 24.2.3.5 y 19.2.3.1")
        mem.paso("Inercia fisurada", "Icr (sección transformada, n = Es/Ec)",
                 f"eje neutro c = {fmt(sf.c)} cm", sf.Icr, "cm4")
        mem.paso("Momento de servicio con D + L", "Ma", "", MDL / 100, "kg·m",
                 "Fisurada" if MDL > (2 / 3) * sf.Mcr else "No fisurada: Ie = Ig",
                 "Compara con (2/3)·Mcr")
        mem.paso("Inercia efectiva con D + L", "Ie = Icr / [1 − ((2/3)·Mcr/Ma)²·(1 − Icr/Ig)]",
                 "", Ie_DL, "cm4", f"Ie/Ig = {fmt(Ie_DL / sf.Ig, 3)}", "ACI 318-19, Tabla 24.2.3.5")
        mem.paso("Flecha inmediata con D", "Δ,el(D)·Ig/Ie(D)", f"{fmt(dD, 3)}·{fmt(sf.Ig / Ie_D, 3)}",
                 fD, "cm", nd=3)
        mem.paso("Flecha inmediata con D + L", "Δ,el(D+L)·Ig/Ie(D+L)",
                 f"{fmt(dDL, 3)}·{fmt(sf.Ig / Ie_DL, 3)}", fDL, "cm", nd=3)
        mem.paso("Flecha inmediata por carga viva", "ΔL = |Δ(D+L) − Δ(D)|",
                 f"{fmt(fDL, 3)} − {fmt(fD, 3)}", fL, "cm",
                 f"{estado(res.cumple_L)}: <= {nombre_luz}/360 = {fmt(res.lim_L, 3)} cm",
                 "ACI 318-19, Tabla 24.2.2", nd=3)
        mem.paso("Flecha inmediata con carga sostenida", "Δ,el(sost)·Ig/Ie(sost)",
                 f"{fmt(dS, 3)}·{fmt(sf.Ig / Ie_S, 3)}", fS, "cm", nd=3)
        if dD < 0 or dDL < 0:
            mem.nota("Flecha negativa = hacia arriba (vano corto junto a vanos más largos). "
                     "Las verificaciones usan valores absolutos.")
        mem.paso("Flecha diferida más viva", "Δlp = λΔ·|Δ,sostenida| + |ΔL|",
                 f"{fmt(lam)}·{fmt(fS, 3)} + {fmt(fL, 3)}", flp, "cm",
                 f"{estado(res.cumple_lp)}: <= {nombre_luz}/{den_lp} = {fmt(res.lim_lp, 3)} cm",
                 "ACI 318-19, 24.2.4 y Tabla 24.2.2", nd=3)
    return res
