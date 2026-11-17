"""Diseño a flexión: acero requerido, mínimo, varillas, bloque de compresión y εt.

Losa nervada: en momento negativo el ancho comprimido es el de los nervios
(bw·100/s por metro) y en momento positivo es el ala (100 cm por metro).
"""
from __future__ import annotations

from math import floor, pi, sqrt

from .memoria import Memoria, estado, fmt
from .modelos import DisenoFlexion, Losa, Materiales

PHI_FLEXION = 0.9
EPS_T_MIN = 0.005
SEP_MIN_MACIZA = 10.0   # cm, separación práctica mínima entre varillas


def area(diametro_mm: float) -> float:
    return pi * (diametro_mm / 10) ** 2 / 4


def acero_requerido(Mu: float, b: float, d: float, fc: float, fy: float) -> float | None:
    """As (cm²) para Mu (kg·m) en un ancho b (cm). None si la sección no alcanza."""
    if Mu <= 0:
        return 0.0
    disc = d * d - 2 * Mu * 100 / (PHI_FLEXION * 0.85 * fc * b)
    if disc < 0:
        return None
    return 0.85 * fc * b / fy * (d - sqrt(disc))


def cuantia_minima_maciza(fy: float) -> float:
    """ACI 318-19, Tablas 7.6.1.1 y 8.6.1.1 (sobre el área bruta)."""
    return 0.0020 if fy < 4200 else max(0.0018 * 4200 / fy, 0.0014)


def _elegir_nervio(As_nervio: float, losa: Losa) -> tuple[int, int, bool]:
    """(n, diámetro, alcanza): una varilla del menor diámetro posible; si no, más."""
    for n in range(1, losa.max_varillas_nervio + 1):
        for phi in losa.diametros:
            if n * area(phi) >= As_nervio - 1e-6:
                return n, phi, True
    return losa.max_varillas_nervio, losa.diametros[-1], False


def _elegir_maciza(As: float, losa: Losa, s_max: float) -> tuple[int, float, bool]:
    """(diámetro, separación en cm, alcanza)."""
    for phi in losa.diametros:
        s = min(floor(area(phi) * 100 / As / 2.5 + 1e-9) * 2.5, s_max)
        if s >= SEP_MIN_MACIZA:
            return phi, s, True
    phi = losa.diametros[-1]
    s = floor(area(phi) * 100 / As / 2.5 + 1e-9) * 2.5
    return phi, max(s, 2.5), s >= 5.0


def disenar(nombre: str, Mu: float, signo: str, d: float, mat: Materiales, losa: Losa,
            s_max: float = 45.0, mem: Memoria | None = None) -> DisenoFlexion:
    """Diseña una sección para Mu (kg·m por metro de losa). Con Mu = 0 coloca el
    acero mínimo (armado constructivo)."""
    fc, fy = mat.fc, mat.fy
    notas: list[str] = []
    if losa.nervada:
        s, bw = losa.separacion_nervios, losa.ancho_nervio
        bw_m = bw * 100 / s
        b = bw_m if signo == "-" else 100.0
        As_min = max(0.8 * sqrt(fc), 14.0) / fy * bw_m * d
        ref_min = "ACI 318-19, 9.6.1.2"
    else:
        b = 100.0
        As_min = cuantia_minima_maciza(fy) * 100 * losa.altura
        ref_min = "ACI 318-19, 7.6.1.1 / 8.6.1.1"
    As_req = acero_requerido(Mu, b, d, fc, fy)
    As_dis = max(As_req or 0.0, As_min)
    if losa.nervada:
        n, phi, alcanza = _elegir_nervio(As_dis * s / 100, losa)
        sep, As_u = 0.0, n * area(phi)
        As_col = As_u * 100 / s
        b_comp, lim_a = (bw, losa.hn) if signo == "-" else (s, losa.loseta)
        armado = f"{n}Ø{phi}"
        libre = bw - 2 * mat.recubrimiento - n * phi / 10
        if n > 1 and libre < (n - 1) * max(2.5, phi / 10):
            notas.append(f"{n} varillas Ø{phi} no caben en una capa en el nervio de "
                         f"{fmt(bw, 0)} cm: colocar en paquete vertical o aumentar bw "
                         "(ACI 318-19, 25.2.1).")
    else:
        n = 0
        phi, sep, alcanza = _elegir_maciza(As_dis, losa, s_max)
        As_u = As_col = area(phi) * 100 / sep
        b_comp, lim_a = 100.0, d
        armado = f"Ø{phi} @ {fmt(sep, 1 if sep % 1 else 0)} cm"
    a = As_u * fy / (0.85 * fc * b_comp)
    c = a / mat.beta1
    eps = 0.003 * (d - c) / c
    cumple = (As_req is not None and alcanza and a <= lim_a + 1e-9 and eps >= EPS_T_MIN)
    if As_req is None:
        notas.append("La sección no alcanza para el momento: aumentar la altura de la losa.")
    if not alcanza:
        notas.append("No hay combinación de varillas de la lista que cubra el acero requerido.")
    dis = DisenoFlexion(nombre, signo, Mu, b, d, As_req, As_min, As_dis, phi, n, sep, As_u,
                        As_col, a, eps, armado, cumple, Mu <= 0, notas)
    if mem:
        _memoria(dis, mat, losa, lim_a, ref_min, mem)
    return dis


def _memoria(x: DisenoFlexion, mat: Materiales, losa: Losa, lim_a: float, ref_min: str,
             mem: Memoria) -> None:
    fc, fy = mat.fc, mat.fy
    mem.nota(f"{x.nombre}:  Mu = {fmt(x.Mu)} kg·m/m,  b = {fmt(x.b)} cm,  d = {fmt(x.d)} cm"
             + ("  (sin momento: armado constructivo con acero mínimo)" if x.constructivo else ""))
    if not x.constructivo:
        mem.paso("  Acero requerido", "As = (0,85·f'c·b/fy)·[d − √(d² − 2·Mu/(φ·0,85·f'c·b))]",
                 f"(0,85·{fmt(fc, 0)}·{fmt(x.b)}/{fmt(fy, 0)})·[{fmt(x.d)} − √({fmt(x.d)}² − "
                 f"2·{fmt(x.Mu * 100, 0)}/(0,9·0,85·{fmt(fc, 0)}·{fmt(x.b)}))]",
                 x.As_req if x.As_req is not None else "No alcanza", "cm²/m",
                 "" if x.As_req is not None else "NO CUMPLE", "ACI 318-19, 22.2")
    if losa.nervada:
        mem.paso("  Acero mínimo", "As,mín = máx(0,8·√f'c ; 14)/fy · bw·d",
                 f"máx({fmt(0.8 * sqrt(fc))} ; 14)/{fmt(fy, 0)} · {fmt(losa.ancho_nervio * 100 / losa.separacion_nervios)}·{fmt(x.d)}",
                 x.As_min, "cm²/m", referencia=ref_min)
    else:
        mem.paso("  Acero mínimo", "As,mín = ρmín·100·h",
                 f"{fmt(cuantia_minima_maciza(fy), 4)}·100·{fmt(losa.altura)}", x.As_min, "cm²/m",
                 referencia=ref_min)
    mem.paso("  Acero de diseño", "máx(As ; As,mín)", "", x.As_dis, "cm²/m")
    if losa.nervada:
        s = losa.separacion_nervios
        mem.paso("  Acero por nervio", "As·s/100", f"{fmt(x.As_dis)}·{fmt(s)}/100",
                 x.As_dis * s / 100, "cm²")
        mem.paso("  Armado por nervio", "n = As,nervio / AØ (redondeo arriba)",
                 f"{x.n} varilla(s) Ø{x.diametro} mm = {fmt(x.As_u)} cm²", x.armado, "",
                 estado(x.As_u >= x.As_dis * s / 100 - 1e-6))
        b_comp = losa.ancho_nervio if x.signo == "-" else s
        txt_lim = "a <= hn" if x.signo == "-" else "a <= loseta"
    else:
        mem.paso("  Armado", "s = AØ·100/As (múltiplo de 2,5 cm)",
                 f"Ø{x.diametro} mm cada {fmt(x.separacion, 1)} cm = {fmt(x.As_col)} cm²/m",
                 x.armado, "", estado(x.As_col >= x.As_dis - 1e-6))
        b_comp, txt_lim = 100.0, "a <= d"
    mem.paso("  Bloque de compresión", "a = As·fy/(0,85·f'c·b)",
             f"{fmt(x.As_u)}·{fmt(fy, 0)}/(0,85·{fmt(fc, 0)}·{fmt(b_comp)})", x.a, "cm",
             f"{estado(x.a <= lim_a + 1e-9)}: {txt_lim} = {fmt(lim_a)} cm", "ACI 318-19, 22.2.2.4")
    mem.paso("  Deformación del acero", "εt = 0,003·(d − c)/c,  c = a/β1",
             f"0,003·({fmt(x.d)} − {fmt(x.a / mat.beta1)})/{fmt(x.a / mat.beta1)}", x.eps_t, "",
             f"{estado(x.eps_t >= EPS_T_MIN)}: εt >= 0,005", "ACI 318-19, 21.2.2", nd=4)
    for n in x.notas:
        mem.nota("  Observación: " + n)
