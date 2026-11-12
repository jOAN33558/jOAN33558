"""Plano esquemático (PNG) con los paños, su tipo y el armado."""
from __future__ import annotations

from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
from matplotlib.lines import Line2D  # noqa: E402
from matplotlib.patches import Circle, Patch, Rectangle  # noqa: E402

from .modelos import BORDES, Pano, ResultadoPano, ResultadoPiso  # noqa: E402

COLOR = {"CUMPLE": "#E7F3E7", "NO CUMPLE": "#F9DDDD", "FUERA DE ALCANCE": "#E4E4E4"}
ESTILO_BORDE = {"continuo": dict(color="black", lw=2.6, ls="-"),
                "discontinuo": dict(color="#1F4E9C", lw=1.6, ls=(0, (5, 3))),
                "libre": dict(color="#C00000", lw=1.4, ls=(0, (1, 2)))}
INF, SUP = "#0B6E2E", "#B4420A"


def _fmt(x: float) -> str:
    return f"{x:.2f}".replace(".", ",")


def _segmento(p: Pano, borde: str, dentro: float):
    """Extremos del borde, desplazado hacia dentro del paño."""
    if borde == "norte":
        return (p.x0 + dentro, p.x1 - dentro), (p.y1 - dentro, p.y1 - dentro)
    if borde == "sur":
        return (p.x0 + dentro, p.x1 - dentro), (p.y0 + dentro, p.y0 + dentro)
    if borde == "este":
        return (p.x1 - dentro, p.x1 - dentro), (p.y0 + dentro, p.y1 - dentro)
    return (p.x0 + dentro, p.x0 + dentro), (p.y0 + dentro, p.y1 - dentro)


def _armado(r: ResultadoPano, clave: str) -> str:
    x = r.flexion.get(clave)
    return "-" if x is None else x.armado + (" mín." if x.constructivo else "")


def _dibujar_superior(ax, p: Pano, borde: str, texto: str, largo_dentro: float,
                      largo_fuera: float, fs: float, frac: float = 0.5) -> None:
    """Varilla superior perpendicular al borde, con su etiqueta."""
    if borde in ("norte", "sur"):
        x = p.x0 + frac * p.ancho_x
        y = p.y1 if borde == "norte" else p.y0
        s = -1 if borde == "norte" else 1
        ax.plot([x, x], [y + s * largo_dentro, y - s * largo_fuera], color=SUP, lw=2.0, zorder=6)
        ax.text(x + 0.06, y + s * largo_dentro * 0.55, texto, color=SUP, fontsize=fs,
                rotation=90, va="center", ha="left", zorder=7)
    else:
        y = p.y0 + frac * p.ancho_y
        x = p.x1 if borde == "este" else p.x0
        s = -1 if borde == "este" else 1
        ax.plot([x + s * largo_dentro, x - s * largo_fuera], [y, y], color=SUP, lw=2.0, zorder=6)
        ax.text(x + s * largo_dentro * 0.55, y + 0.06, texto, color=SUP, fontsize=fs,
                va="bottom", ha="center", zorder=7)


def _dibujar_pano(ax, rp: ResultadoPiso, r: ResultadoPano, fs: float, hechos: set) -> None:
    p = r.pano
    ax.add_patch(Rectangle((p.x0, p.y0), p.ancho_x, p.ancho_y, facecolor=COLOR[r.resultado],
                           edgecolor="none", zorder=1,
                           hatch=None if r.calculado else "////", alpha=0.95))
    dentro = 0.07
    for b in BORDES:
        xs, ys = _segmento(p, b, dentro)
        ax.plot(xs, ys, zorder=4, solid_capstyle="butt", **ESTILO_BORDE[p.cond[b]])
    xc, yc = (p.x0 + p.x1) / 2, (p.y0 + p.y1) / 2
    if not r.calculado:
        ax.text(xc, yc, f"{p.id}\nFUERA DE ALCANCE\nRequiere modelo de\nelementos finitos",
                ha="center", va="center", fontsize=fs + 1, fontweight="bold", zorder=8,
                bbox=dict(boxstyle="round,pad=0.25", fc="white", ec="#888888", lw=0.6))
        return
    clasif = f"Tipo {r.tipo} - Bidireccional" if r.tipo else f"Unidireccional ({r.dir_corta})"
    ax.text(p.x0 + 0.56 * p.ancho_x, p.y0 + 0.62 * p.ancho_y,
            f"{p.id}\n{clasif}\nLx/Ly = {_fmt(r.beta)}\n{r.resultado}",
            ha="center", va="center", fontsize=fs + 1, fontweight="bold", zorder=8,
            bbox=dict(boxstyle="round,pad=0.25", fc="white", ec="#888888", lw=0.6, alpha=0.92))
    # Acero inferior
    inf_x = _armado(r, "pos_corta" if r.dir_corta == "X" else "pos_larga")
    inf_y = _armado(r, "pos_corta" if r.dir_corta == "Y" else "pos_larga")
    y = p.y0 + 0.36 * p.ancho_y
    ax.plot([p.x0 + 0.28 * p.ancho_x, p.x1 - 0.10 * p.ancho_x], [y, y], color=INF, lw=2.0, zorder=6)
    ax.text(p.x0 + 0.59 * p.ancho_x, y - 0.05, f"Inf. X: {inf_x}", color=INF, fontsize=fs,
            ha="center", va="top", zorder=7)
    x = p.x0 + 0.16 * p.ancho_x
    ax.plot([x, x], [p.y0 + 0.30 * p.ancho_y, p.y1 - 0.10 * p.ancho_y], color=INF, lw=2.0, zorder=6)
    ax.text(x - 0.05, p.y0 + 0.60 * p.ancho_y, f"Inf. Y: {inf_y}", color=INF, fontsize=fs,
            rotation=90, ha="right", va="center", zorder=7)
    # Acero superior en los bordes
    for b in BORDES:
        clave = f"neg_{b}"
        if clave not in r.flexion:
            continue
        vol = next((v for v in r.volados if v.volado.borde == b), None)
        comun = next((c for c in rp.bordes_comunes
                      if (c.pano_a == p.id and c.borde_a == b) or (c.pano_b == p.id and c.borde_b == b)),
                     None)
        dentro_l = min(0.22 * p.luz_perpendicular(b), 1.1)
        frac = 0.70 if b in ("norte", "sur") else 0.14
        if comun:
            marca = (comun.eje, frozenset((comun.pano_a, comun.pano_b)))
            if marca in hechos:
                continue
            hechos.add(marca)
            _dibujar_superior(ax, p, b, f"Sup. {comun.armado}", dentro_l, dentro_l, fs, frac)
        elif vol:
            _dibujar_superior(ax, p, b, f"Sup. {_armado(r, clave)}",
                              max(vol.prolongacion, 0.3), vol.L_eje - 0.05, fs, frac)
        elif not r.flexion[clave].constructivo:
            _dibujar_superior(ax, p, b, f"Sup. {_armado(r, clave)}", dentro_l, 0.0, fs, frac)
    # Volados
    for v in r.volados:
        b, L = v.volado.borde, v.L_eje
        if b == "norte":
            xy, w, h = (p.x0, p.y1), p.ancho_x, L
        elif b == "sur":
            xy, w, h = (p.x0, p.y0 - L), p.ancho_x, L
        elif b == "este":
            xy, w, h = (p.x1, p.y0), L, p.ancho_y
        else:
            xy, w, h = (p.x0 - L, p.y0), L, p.ancho_y
        ok = all(c.cumple for c in v.checks)
        ax.add_patch(Rectangle(xy, w, h, facecolor=COLOR["CUMPLE" if ok else "NO CUMPLE"],
                               edgecolor="#555555", lw=1.0, hatch="..", zorder=1))
        ax.text(xy[0] + w * 0.28, xy[1] + h * 0.5,
                f"Volado {p.id}\nL = {_fmt(v.volado.longitud)} m\n{'CUMPLE' if ok else 'NO CUMPLE'}",
                ha="center", va="center", fontsize=fs, zorder=8,
                rotation=90 if b in ("este", "oeste") else 0,
                bbox=dict(boxstyle="round,pad=0.2", fc="white", ec="#888888", lw=0.5))


def _ejes(ax, rp: ResultadoPiso, xmin, xmax, ymin, ymax, fs: float) -> None:
    piso = rp.piso
    radio = 0.28
    for nombre, x in piso.ejes_x.items():
        ax.plot([x, x], [ymin - 0.5, ymax + 0.7], color="#777777", lw=0.7, ls="-.", zorder=2)
        ax.add_patch(Circle((x, ymax + 0.7 + radio), radio, fc="white", ec="black", lw=1, zorder=9))
        ax.text(x, ymax + 0.7 + radio, nombre, ha="center", va="center", fontsize=fs + 2, zorder=10)
    for nombre, y in piso.ejes_y.items():
        ax.plot([xmin - 0.7, xmax + 0.5], [y, y], color="#777777", lw=0.7, ls="-.", zorder=2)
        ax.add_patch(Circle((xmin - 0.7 - radio, y), radio, fc="white", ec="black", lw=1, zorder=9))
        ax.text(xmin - 0.7 - radio, y, nombre, ha="center", va="center", fontsize=fs + 2, zorder=10)
    xs, ys = list(piso.ejes_x.values()), list(piso.ejes_y.values())
    for a, b in zip(xs, xs[1:]):
        ax.text((a + b) / 2, ymin - 0.45, _fmt(b - a), ha="center", va="top", fontsize=fs + 1)
    for a, b in zip(ys, ys[1:]):
        ax.text(xmax + 0.45, (a + b) / 2, _fmt(b - a), ha="left", va="center", fontsize=fs + 1,
                rotation=90)


def dibujar(rp: ResultadoPiso, ruta: str | Path) -> Path:
    ruta = Path(ruta)
    piso = rp.piso
    xmin, xmax = min(piso.ejes_x.values()), max(piso.ejes_x.values())
    ymin, ymax = min(piso.ejes_y.values()), max(piso.ejes_y.values())
    ext = {b: 0.0 for b in BORDES}
    for r in rp.panos.values():
        for v in r.volados:
            ext[v.volado.borde] = max(ext[v.volado.borde], v.L_eje)
    ancho, alto = xmax - xmin, ymax - ymin
    escala = max(0.9, min(1.5, 14 / max(ancho, alto)))
    fig, ax = plt.subplots(figsize=(max(9, ancho * escala + 4.5), max(7, alto * escala + 4.5)))
    fs = 7.0
    hechos: set = set()
    for r in rp.panos.values():
        _dibujar_pano(ax, rp, r, fs, hechos)
    _ejes(ax, rp, xmin - ext["oeste"], xmax + ext["este"], ymin - ext["sur"], ymax + ext["norte"], fs)
    ax.set_xlim(xmin - ext["oeste"] - 1.6, xmax + ext["este"] + 1.3)
    ax.set_ylim(ymin - ext["sur"] - 1.2, ymax + ext["norte"] + 1.6)
    ax.set_aspect("equal")
    ax.axis("off")
    losa = piso.losa
    unidad = "varillas por nervio" if losa.nervada else "varillas por metro"
    geo = (f"Losa nervada h = {losa.altura:g} cm (loseta {losa.loseta:g} cm, nervios "
           f"{losa.ancho_nervio:g} cm cada {losa.separacion_nervios:g} cm)" if losa.nervada
           else f"Losa maciza h = {losa.altura:g} cm")
    titulo = " - ".join(str(piso.proyecto[k]) for k in ("nombre", "piso") if piso.proyecto.get(k))
    ax.set_title(f"PLANO ESQUEMÁTICO DE LOSAS{' - ' + titulo if titulo else ''}\n{geo}. "
                 f"Armado en {unidad}. Cotas en m. No es un plano de construcción.", fontsize=10)
    leyenda = [Line2D([0], [0], label="Borde continuo", **ESTILO_BORDE["continuo"]),
               Line2D([0], [0], label="Borde discontinuo", **ESTILO_BORDE["discontinuo"]),
               Line2D([0], [0], label="Borde libre", **ESTILO_BORDE["libre"]),
               Line2D([0], [0], color=INF, lw=2, label="Acero inferior"),
               Line2D([0], [0], color=SUP, lw=2, label="Acero superior"),
               Patch(fc=COLOR["CUMPLE"], ec="#888888", label="Cumple"),
               Patch(fc=COLOR["NO CUMPLE"], ec="#888888", label="No cumple"),
               Patch(fc=COLOR["FUERA DE ALCANCE"], ec="#888888", hatch="////",
                     label="Fuera de alcance")]
    ax.legend(handles=leyenda, loc="upper center", bbox_to_anchor=(0.5, 0.02), ncol=4,
              fontsize=8, frameon=False)
    ruta.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(ruta, dpi=170, bbox_inches="tight", facecolor="white")
    plt.close(fig)
    return ruta
