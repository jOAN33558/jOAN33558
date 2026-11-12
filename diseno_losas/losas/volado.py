"""Volados: solicitaciones en el empotramiento, altura mínima, flecha en la punta y
prolongación del acero negativo dentro del paño interior."""
from __future__ import annotations

from math import sqrt

from . import cortante, flechas
from .cargas import CargasPano, cargas_pano
from .memoria import Memoria, estado, fmt
from .modelos import (DisenoFlexion, Pano, Piso, ResultadoPano, ResultadoVolado, Verificacion,
                      Volado)
from .seccion import Seccion
from .verificaciones import hmin_unidireccional


def solicitaciones(D: float, L: float, luz: float, P_D: float = 0.0, P_L: float = 0.0):
    """Momento (kg·m/m) y cortante (kg/m) últimos en el empotramiento de un volado con
    carga uniforme (kg/m²) y carga de borde en la punta (kg/m).

    Devuelve (Mu, Vu, combinación, M_D, M_L) con M_D y M_L de servicio.
    """
    M_D = D * luz**2 / 2 + P_D * luz
    M_L = L * luz**2 / 2 + P_L * luz
    V_D, V_L = D * luz + P_D, L * luz + P_L
    casos = [(1.4 * M_D, 1.4 * V_D, "1,4D"),
             (1.2 * M_D + 1.6 * M_L, 1.2 * V_D + 1.6 * V_L, "1,2D + 1,6L")]
    Mu, _, combo = max(casos, key=lambda c: c[0])
    Vu = max(c[1] for c in casos)
    return Mu, Vu, combo, M_D, M_L


def longitud_desarrollo(diametro_mm: float, fc: float, fy: float) -> float:
    """ld en cm (ACI 318-19, 25.4.2.3, kg/cm²; ψt = ψe = ψg = λ = 1)."""
    db = diametro_mm / 10
    k = 6.6 if diametro_mm <= 19 else 5.3
    return max(fy / (k * sqrt(fc)) * db, 30.0)


def analizar(piso: Piso, pano: Pano, vol: Volado, pp: float, mem: Memoria) -> ResultadoVolado:
    viga = piso.viga_en(pano.eje_de(vol.borde))
    bv = viga.b if viga else 0.0
    if vol.medida == "eje":
        L, L_eje = vol.longitud - bv / 200, vol.longitud
    else:
        L, L_eje = vol.longitud, vol.longitud + bv / 200
    mem.seccion(f"5. VOLADO EN EL BORDE {vol.borde.upper()} (eje {pano.eje_de(vol.borde)})")
    mem.paso("Longitud de diseño (desde la cara de la viga)",
             "L = longitud − b,viga/2" if vol.medida == "eje" else "L = longitud (medida a la cara)",
             f"{fmt(vol.longitud)} − {fmt(bv / 200, 3)}" if vol.medida == "eje" else "", L, "m")
    c: CargasPano = cargas_pano(piso, {**pano.cargas, **vol.cargas}, pp, None)
    mem.dato("Carga permanente del volado D", c.D, "kg/m²")
    mem.dato("Carga viva del volado L", c.L, "kg/m²", "NEC-SE-CG")
    mem.dato("Carga de borde permanente P,D (antepecho)", vol.carga_borde, "kg/m")
    mem.dato("Carga de borde viva P,L", vol.carga_borde_viva, "kg/m")
    Mu, Vu, combo, M_D, M_L = solicitaciones(c.D, c.L, L, vol.carga_borde, vol.carga_borde_viva)
    fD, fL = (1.4, 0.0) if combo == "1,4D" else (1.2, 1.6)
    qu, Pu = fD * c.D + fL * c.L, fD * vol.carga_borde + fL * vol.carga_borde_viva
    mem.paso("Carga distribuida última", f"qu ({combo})", "", qu, "kg/m²")
    mem.paso("Carga de borde última", f"Pu ({combo})", "", Pu, "kg/m")
    mem.paso("Momento en el empotramiento", "Mu = qu·L²/2 + Pu·L",
             f"{fmt(qu)}·{fmt(L, 3)}²/2 + {fmt(Pu)}·{fmt(L, 3)}", Mu, "kg·m/m",
             f"Gobierna {combo}", "Estática")
    mem.paso("Cortante en el empotramiento", "Vu = qu·L + Pu",
             f"{fmt(qu)}·{fmt(L, 3)} + {fmt(Pu)}", Vu, "kg/m", referencia="Estática")
    return ResultadoVolado(vol, L, L_eje, c.D, c.L, Mu, Vu, combo, M_D, M_L)


def _flecha_punta(piso: Piso, rv: ResultadoVolado, dis: DisenoFlexion, sec: Seccion,
                  mem: Memoria):
    mat, cg, vol = piso.materiales, piso.cargas, rv.volado
    psi = cg.fraccion_viva_sostenida
    Lc = rv.L * 100
    EI = mat.E * sec.Ig_m
    niveles = {}
    for nombre, q, P in (("D", rv.D, vol.carga_borde),
                         ("DL", rv.D + rv.Lv, vol.carga_borde + vol.carga_borde_viva),
                         ("SOST", rv.D + psi * rv.Lv, vol.carga_borde + psi * vol.carga_borde_viva)):
        delta = (q / 100) * Lc**4 / (8 * EI) + P * Lc**3 / (3 * EI)
        Ma = (q * rv.L**2 / 2 + P * rv.L) * 100 / sec.por_metro
        niveles[nombre] = (delta, Ma)
    mem.nota("Flecha en la punta: Δ = q·L⁴/(8·E·I) + P·L³/(3·E·I), con inercia efectiva en el "
             "empotramiento (ACI 318-19, 24.2.3.7). No incluye el giro del apoyo.")
    sf = flechas.seccion_fisurada(sec, mat, "-", dis.As_u, dis.d)
    den = 480 if cg.soporta_mamposteria else 240
    return flechas.evaluar(niveles, sf, Lc, den, cg.lambda_diferida, mem, "L,volado")


def verificar(piso: Piso, pano: Pano, res: ResultadoPano, rv: ResultadoVolado, sec: Seccion,
              mem: Memoria) -> None:
    """Completa el volado una vez diseñado el acero negativo del borde."""
    mat, losa, borde = piso.materiales, piso.losa, rv.volado.borde
    dis = res.flexion[f"neg_{borde}"]
    mem.seccion(f"11. VERIFICACIONES DEL VOLADO (borde {borde})")
    rv.checks.append(hmin_unidireccional(rv.L, 0, losa, mat.fy, mem, voladizo=True))
    fD, fL = (1.4, 0.0) if rv.combo == "1,4D" else (1.2, 1.6)
    qu = fD * rv.D + fL * rv.Lv
    rv.cortante = cortante.verificar(rv.Vu, qu, dis.d, mat, losa, piso.opciones.cortante,
                                     dis.As_col, f"el empotramiento del volado ({borde})", mem)
    rv.checks.append(Verificacion("Cortante del volado (vu <= vc)", rv.cortante.vu,
                                  rv.cortante.vc, rv.cortante.estado, "ACI 318-19, 22.5"))
    rv.flechas = _flecha_punta(piso, rv, dis, sec, mem)
    rv.checks.append(Verificacion("Flecha en la punta por carga viva", rv.flechas.delta_L,
                                  rv.flechas.lim_L, estado(rv.flechas.cumple_L),
                                  "ACI 318-19, Tabla 24.2.2"))
    rv.checks.append(Verificacion("Flecha diferida en la punta", rv.flechas.delta_lp,
                                  rv.flechas.lim_lp, estado(rv.flechas.cumple_lp),
                                  "ACI 318-19, Tabla 24.2.2"))
    # Equilibrio con el paño interior y prolongación del acero negativo
    mem.nota("Equilibrio con el paño interior:")
    dM = rv.Mu - rv.M_pano
    mem.paso("  Momento del volado frente al momento propio del paño en el borde",
             "ΔM = Mu,volado − M(−),paño", f"{fmt(rv.Mu)} − {fmt(rv.M_pano)}", dM, "kg·m/m",
             "El borde se diseña con el mayor de los dos",
             "El desequilibrio lo toman el paño interior y la torsión de la viga")
    Lb, Lo = pano.luz_perpendicular(borde), pano.longitud_borde(borde)
    k = Lo**4 / (Lb**4 + Lo**4)
    w = 0.9 * res.cargas.D * k
    x0 = min(2 * rv.Mu / (w * Lb), Lb) if w > 0 else Lb
    mem.paso("  Fracción de carga del paño en la dirección del volado", "k = Lo⁴/(Lb⁴ + Lo⁴)",
             f"{fmt(Lo)}⁴/({fmt(Lb)}⁴ + {fmt(Lo)}⁴)", k, "", referencia="Reparto de Grashof", nd=3)
    mem.paso("  Punto de inflexión en el paño interior (carga mínima 0,9·D)",
             "x0 = 2·Mu/(0,9·D·k·Lb) <= Lb", f"2·{fmt(rv.Mu)}/({fmt(w)}·{fmt(Lb)})", x0, "m",
             "Todo el vano en momento negativo" if x0 >= Lb - 1e-9 else "",
             "Franja con el extremo lejano articulado")
    viga_ancho = sum(v.b for v in (piso.viga_en(pano.eje_de(borde)),) if v) / 100
    ln = Lb - viga_ancho
    extra = max(dis.d / 100, 12 * dis.diametro / 1000, ln / 16)
    rv.ld = longitud_desarrollo(dis.diametro, mat.fc, mat.fy)
    rv.prolongacion = min(max(x0 + extra, rv.ld / 100), Lb)
    mem.paso("  Longitud de desarrollo", "ld = fy/(6,6·√f'c)·db >= 30 cm (5,3 si Ø > 19 mm)",
             f"Ø{dis.diametro} mm", rv.ld, "cm", referencia="ACI 318-19, 25.4.2.3")
    mem.paso("  Prolongación del acero negativo dentro del paño interior",
             "máx[x0 + máx(d ; 12·db ; ln/16) ; ld]",
             f"máx[{fmt(x0)} + {fmt(extra, 3)} ; {fmt(rv.ld / 100)}]", rv.prolongacion, "m",
             "Medida desde el eje de la viga", "ACI 318-19, 7.7.3.3, 7.7.3.8 y 9.7.3.8.4")
    mem.nota("  El acero negativo del volado debe anclarse y prolongarse la longitud indicada "
             "dentro del paño interior, sin cortarse en la viga.")
