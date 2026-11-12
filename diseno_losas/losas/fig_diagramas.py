"""Diagramas de momentos, de cortante y de aprovechamiento de un paño."""
from __future__ import annotations

import numpy as np

from .cortante import PHI_CORTANTE
from .fig_planta import GRIS, INF, SUP, num
from .indices import indices
from .modelos import Piso, ResultadoPano

VERDE, ROJO, AMBAR = "#3C9D5B", "#C8443B", "#E0A32E"


def _curva(M1: float, M2: float, Mp: float, n: int = 81):
    """Parábola esquemática con momentos negativos M1 y M2 en los extremos y momento
    positivo máximo Mp (carga uniforme equivalente). Devuelve (ξ, M)."""
    xi = np.linspace(0, 1, n)

    def forma(k):
        return -M1 * (1 - xi) - M2 * xi + 4 * k * xi * (1 - xi)

    if Mp <= 0:
        return xi, forma(0.0)
    a, b = 0.0, Mp + max(M1, M2) + 1.0
    for _ in range(60):
        k = (a + b) / 2
        if forma(k).max() < Mp:
            a = k
        else:
            b = k
    return xi, forma((a + b) / 2)


def dibujar_momentos(ax, r: ResultadoPano, direccion: str, fs: float = 7.5) -> None:
    """Momentos de diseño en una dirección ('corta' o 'larga'), con el armado."""
    p = r.pano
    b0, b1 = r.largos if direccion == "corta" else r.cortos
    L = r.Lx if direccion == "corta" else r.Ly
    eje = r.dir_corta if direccion == "corta" else ("Y" if r.dir_corta == "X" else "X")
    M1, M2, Mp = r.M_dis.get(b0, 0.0), r.M_dis.get(b1, 0.0), r.M_pos[direccion]
    libre = "libre" in (p.cond[b0], p.cond[b1])
    if not (M1 or M2 or Mp):
        arm = r.flexion.get(f"pos_{direccion}")
        ax.text(0.5, 0.5, f"Dirección {direccion} ({eje}), L = {num(L)} m\n\nSin flexión de diseño "
                "en esta dirección.\nSe coloca acero mínimo"
                + (f": inf. {arm.armado}" if arm else "") + ".", ha="center", va="center",
                fontsize=fs + 1, transform=ax.transAxes, color=GRIS)
        ax.set_xticks([])
        ax.set_yticks([])
        ax.set_title(f"Momentos, dirección {direccion} ({eje})", fontsize=fs + 1)
        return
    escala = max(M1, M2, Mp, 1.0)
    ax.axhline(0, color="black", lw=0.9)
    if not libre and (M1 or M2 or Mp):
        xi, M = _curva(M1, M2, Mp)
        x = xi * L
        ax.plot(x, M, color="#333333", lw=1.3)
        ax.fill_between(x, 0, M, where=M >= 0, color=INF, alpha=0.22, interpolate=True)
        ax.fill_between(x, 0, M, where=M <= 0, color=SUP, alpha=0.22, interpolate=True)
        x_pos = float(x[int(np.argmax(M))])
    else:
        x_pos = L / 2
        for xv, Mv, c in ((0, -M1, SUP), (x_pos, Mp, INF), (L, -M2, SUP)):
            if Mv:
                ax.plot([xv, xv], [0, Mv], color=c, lw=3)
    arm = {k: (r.flexion[k].armado + (" mín." if r.flexion[k].constructivo else ""))
           for k in (f"pos_{direccion}", f"neg_{b0}", f"neg_{b1}") if k in r.flexion}
    ax.text(x_pos, Mp + 0.07 * escala, f"M+ = {num(Mp, 0)}\ninf. {arm.get('pos_' + direccion, '-')}",
            ha="center", va="top", fontsize=fs, color=INF, linespacing=0.95)
    for xv, Mv, b, ha in ((0, M1, b0, "left"), (L, M2, b1, "right")):
        if p.cond[b] == "libre":
            texto = f"borde {b}\nlibre"
        else:
            texto = f"M− = {num(Mv, 0)}\nsup. {arm.get('neg_' + b, '-')}\n(borde {b})"
        ax.text(xv + (0.02 if ha == "left" else -0.02) * L, -Mv - 0.07 * escala, texto, ha=ha,
                va="bottom", fontsize=fs, color=SUP if p.cond[b] != "libre" else GRIS,
                linespacing=0.95)
        if p.cond[b] != "libre":
            ax.plot([xv], [0], marker="^", color="black", ms=7, clip_on=False, zorder=5)
    ax.set_xlim(-0.03 * L, 1.03 * L)
    ax.set_ylim(Mp + 0.55 * escala, -max(M1, M2) - 0.75 * escala)     # positivo hacia abajo
    ax.set_xlabel(f"Posición en {eje} (m)", fontsize=fs)
    ax.set_ylabel("M (kg·m/m)", fontsize=fs)
    ax.tick_params(labelsize=fs - 0.5)
    ax.grid(alpha=0.25)
    nota = "valores de diseño; forma esquemática" if not libre else "valores de diseño"
    ax.set_title(f"Momentos, dirección {direccion} ({eje}), L = {num(L)} m ({nota})", fontsize=fs + 1)


def dibujar_cortante(ax, piso: Piso, r: ResultadoPano, fs: float = 7.5) -> None:
    """Cortante desde la cara de la viga frente a la resistencia de la sección."""
    losa, rc = piso.losa, r.cortante
    d = r.d["corta"] / 100
    if r.clasificacion == "Bidireccional":
        V_cara, q, donde = r.V_cara["general"], r.cargas.qu, "franja corta"
    else:
        borde, V_cara = max(r.V_cara.items(), key=lambda t: t[1])
        q, donde = r.servicio["wu"], f"apoyo {borde}"
    b = losa.ancho_nervio * 100 / losa.separacion_nervios if losa.nervada else 100.0
    phiVc = PHI_CORTANTE * rc.vc * b * r.d["corta"]
    x_fin = max(V_cara / q, 1.6 * max(d, losa.macizado if losa.nervada else d))
    x = np.linspace(0, x_fin, 50)
    V = np.maximum(V_cara - q * x, 0)
    ax.plot(x, V, color="#333333", lw=1.4, label="Vu(x)")
    ax.axhline(phiVc, color=VERDE, lw=1.4, ls="--",
               label="φ·Vc " + ("de los nervios" if losa.nervada else "de la losa"))
    ax.fill_between(x, phiVc, V, where=V > phiVc, color=ROJO, alpha=0.20, interpolate=True)
    ax.axvline(d, color=GRIS, lw=0.8, ls=":")
    ax.text(d, 0, " d", fontsize=fs, color=GRIS, va="bottom", ha="left")
    ok = rc.Vu <= phiVc + 1e-6
    ax.plot([d], [rc.Vu], "o", color=VERDE if ok else (AMBAR if rc.cumple else ROJO), ms=7, zorder=5)
    ax.annotate(f"Vu(d) = {num(rc.Vu, 0)}", (d, rc.Vu), xytext=(6, 11), textcoords="offset points",
                fontsize=fs)
    if losa.nervada and not ok:
        xm = losa.macizado
        ax.axvspan(0, xm, color=AMBAR, alpha=0.15)
        ax.axvline(xm, color=AMBAR, lw=1.0, ls="-.")
        ax.plot([xm], [rc.Vu_mac], "s", color=VERDE if rc.cumple else ROJO, ms=7, zorder=5)
        ax.annotate(f"borde del macizado ({num(xm, 3)} m)\nVu = {num(rc.Vu_mac, 0)}", (xm, rc.Vu_mac),
                    xytext=(10, -8), textcoords="offset points", fontsize=fs, linespacing=0.95,
                    va="top")
    ax.set_xlim(0, x_fin)
    ax.set_ylim(0, max(V_cara, phiVc) * 1.25)
    ax.set_xlabel("Distancia desde la cara de la viga (m)", fontsize=fs)
    ax.set_ylabel("V (kg/m)", fontsize=fs)
    ax.tick_params(labelsize=fs - 0.5)
    ax.grid(alpha=0.25)
    ax.legend(fontsize=fs - 0.5, loc="upper right", frameon=False)
    ax.set_title(f"Cortante, {donde}: {rc.estado}", fontsize=fs + 1,
                 color="black" if rc.estado == "CUMPLE" else (ROJO if not rc.cumple else "#8A5A00"))


def dibujar_aprovechamiento(ax, r: ResultadoPano, fs: float = 7.5) -> None:
    """Barras de demanda / capacidad de cada verificación (cumple si <= 100 %)."""
    lista = indices(r)[::-1]
    color = {"ok": VERDE, "no": ROJO, "aviso": AMBAR}
    valores = [min(i.valor, 3.0) for i in lista]
    y = np.arange(len(lista))
    ax.barh(y, valores, color=[color[i.estado] for i in lista], height=0.68, zorder=3)
    ax.axvline(1.0, color="black", lw=1.1, zorder=4)
    tope = max(1.3, max(valores, default=1.0) * 1.18)
    for yi, i, v in zip(y, lista, valores):
        ax.text(v + 0.012 * tope, yi, f"{num(i.valor * 100, 0)} %", va="center", ha="left",
                fontsize=fs - 0.5, zorder=5)
    ax.set_yticks(y)
    ax.set_yticklabels([i.nombre for i in lista], fontsize=fs - 0.5)
    ax.set_xlim(0, tope)
    ax.set_ylim(-0.6, len(lista) - 0.4)
    ax.xaxis.set_major_formatter(lambda v, _: f"{v * 100:.0f} %")
    ax.tick_params(axis="x", labelsize=fs - 0.5)
    ax.grid(axis="x", alpha=0.25, zorder=0)
    ax.set_title("Aprovechamiento: demanda / capacidad (cumple hasta 100 %)", fontsize=fs + 1)
