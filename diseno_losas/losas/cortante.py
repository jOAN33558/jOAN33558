"""Cortante en una dirección. En losa nervada lo resisten solo los nervios."""
from __future__ import annotations

from math import sqrt

from .memoria import Memoria, estado, fmt
from .modelos import Losa, Materiales, ResultadoCortante

PHI_CORTANTE = 0.75


def geometria_nervios_ok(losa: Losa) -> bool:
    """Límites de ACI 318-19 9.8.1.2 a 9.8.1.4 que habilitan el aumento de 9.8.1.5."""
    return (losa.ancho_nervio >= 10 and losa.altura <= 3.5 * losa.ancho_nervio
            and losa.separacion_nervios - losa.ancho_nervio <= 75)


def factor_nervios(losa: Losa) -> float:
    return 1.1 if losa.nervada and geometria_nervios_ok(losa) else 1.0


def vc_unitario(mat: Materiales, metodo: str, d: float, rho_w: float | None) -> tuple[float, str, str]:
    """Esfuerzo resistente del hormigón (kg/cm²), sin el factor de nervios.

    - "nec": 0,53·√f'c (NEC-SE-HM, igual a la hoja de referencia).
    - "aci318_19": Tabla 22.5.5.1(c), sin estribos: 2,1·λs·ρw^(1/3)·√f'c <= 1,33·√f'c.
    """
    raiz = sqrt(mat.fc)
    if metodo == "aci318_19" and rho_w:
        lam_s = min(1.0, sqrt(2 / (1 + 0.04 * d)))
        vc = min(2.1 * lam_s * rho_w ** (1 / 3) * raiz, 1.33 * raiz)
        return (vc, "2,1·λs·ρw^(1/3)·√f'c",
                f"2,1·{fmt(lam_s, 3)}·{fmt(rho_w, 4)}^(1/3)·√{fmt(mat.fc, 0)}")
    return 0.53 * raiz, "0,53·√f'c", f"0,53·√{fmt(mat.fc, 0)}"


def verificar(V_cara: float, qu: float, d: float, mat: Materiales, losa: Losa,
              metodo: str = "nec", As_m: float | None = None, ubicacion: str = "",
              mem: Memoria | None = None) -> ResultadoCortante:
    """Verifica el cortante por metro de losa.

    ``V_cara`` es el cortante en la cara del apoyo (kg/m); se reduce a la distancia d
    con la carga qu (kg/m²). En losa nervada, si no cumple en los nervios se revisa el
    borde del macizado (donde la sección vuelve a ser de nervios) y la zona maciza.
    """
    Vu = max(0.0, V_cara - qu * d / 100)
    b = losa.ancho_nervio * 100 / losa.separacion_nervios if losa.nervada else 100.0
    rho = As_m / (b * d) if As_m else None
    vc0, f_txt, s_txt = vc_unitario(mat, metodo, d, rho)
    factor = factor_nervios(losa)
    vc = factor * vc0
    vu = Vu / (PHI_CORTANTE * b * d)
    res = ResultadoCortante(Vu, vu, vc, estado(vu <= vc), ubicacion=ubicacion)
    ref_vc = "ACI 318-19, 22.5.5.1" if metodo == "aci318_19" else "NEC-SE-HM / ACI 318, 22.5"
    if mem:
        if ubicacion:
            mem.nota(f"Cortante en {ubicacion}:")
        mem.paso("  Cortante a la distancia d de la cara", "Vu = V,cara − qu·d",
                 f"{fmt(V_cara)} − {fmt(qu)}·{fmt(d / 100, 3)}", Vu, "kg/m")
        mem.paso("  Esfuerzo actuante" + (" (solo nervios)" if losa.nervada else ""),
                 "vu = Vu/(φ·b·d),  φ = 0,75" + (",  b = bw·100/s" if losa.nervada else ",  b = 100"),
                 f"{fmt(Vu)}/(0,75·{fmt(b)}·{fmt(d)})", vu, "kg/cm²")
        mem.paso("  Esfuerzo resistente", ("1,1·" if factor > 1 else "") + f_txt,
                 ("1,1·" if factor > 1 else "") + s_txt, vc, "kg/cm²",
                 estado(vu <= vc) + ": vu <= vc",
                 ref_vc + ("; 9.8.1.5 (+10 %)" if factor > 1 else ""))
    if vu <= vc or not losa.nervada:
        return res
    # Macizado: zona sin bloques junto a la viga
    x = losa.macizado
    res.Vu_mac = max(0.0, V_cara - qu * x)
    res.vu_mac = res.Vu_mac / (PHI_CORTANTE * b * d)
    rho_mac = As_m / (100 * d) if As_m else None
    vc_mac, _, _ = vc_unitario(mat, metodo, d, rho_mac)
    vu_solido = Vu / (PHI_CORTANTE * 100 * d)
    ok = res.vu_mac <= vc and vu_solido <= vc_mac and x * 100 > d
    res.estado = "CUMPLE con macizado" if ok else "NO CUMPLE"
    if mem:
        mem.paso("  Cortante en el borde del macizado", "Vu,mac = V,cara − qu·x,mac",
                 f"{fmt(V_cara)} − {fmt(qu)}·{fmt(x, 3)}", res.Vu_mac, "kg/m",
                 referencia=f"Macizado de {fmt(x, 3)} m desde la cara de la viga")
        mem.paso("  Esfuerzo en nervios al borde del macizado", "vu,mac = Vu,mac/(φ·b·d)",
                 f"{fmt(res.Vu_mac)}/(0,75·{fmt(b)}·{fmt(d)})", res.vu_mac, "kg/cm²",
                 estado(res.vu_mac <= vc) + ": vu,mac <= vc", "ACI 318-19, 9.8.1.5")
        mem.paso("  Esfuerzo en la zona maciza (b = 100 cm)", "vu = Vu/(φ·100·d)",
                 f"{fmt(Vu)}/(0,75·100·{fmt(d)})", vu_solido, "kg/cm²",
                 estado(vu_solido <= vc_mac) + f": <= {fmt(vc_mac)}", ref_vc)
        mem.nota("  Resultado: " + (f"CUMPLE macizando {fmt(x, 3)} m junto a la viga."
                                    if ok else "NO CUMPLE ni con macizado: aumentar la altura "
                                    "de la losa o el ancho de nervio."))
    return res
