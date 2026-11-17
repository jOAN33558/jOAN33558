"""Figura de planta de un paño: bordes, vecinos, dimensiones, momentos y armado."""
from __future__ import annotations

from math import hypot

from matplotlib.patches import Circle, Rectangle

from .modelos import BORDES, Piso, ResultadoPano

AZUL, INF, SUP, GRIS = "#1F3A93", "#0B6E2E", "#B4420A", "#555555"
NERVIO = "#A9DCC3"
NORMAL = {"sur": (0, -1), "norte": (0, 1), "oeste": (-1, 0), "este": (1, 0)}   # hacia fuera


def num(x: float, nd: int = 2) -> str:
    return f"{x:.{nd}f}".replace(".", ",")


def _extremos(W: float, H: float, borde: str):
    return {"sur": ((0, 0), (W, 0)), "norte": ((0, H), (W, H)),
            "oeste": ((0, 0), (0, H)), "este": ((W, 0), (W, H))}[borde]


def _borde(ax, W: float, H: float, borde: str, cond: str) -> None:
    """Convención de las tablas: rayado = continuo, trazos = discontinuo, línea = libre."""
    (x0, y0), (x1, y1) = _extremos(W, H, borde)
    nx, ny = NORMAL[borde]
    L = hypot(x1 - x0, y1 - y0)
    tx, ty = (x1 - x0) / L, (y1 - y0) / L
    ax.plot([x0, x1], [y0, y1], color=AZUL, lw=2.4, solid_capstyle="projecting", zorder=5)
    if cond == "continuo":
        n = max(4, int(L / 0.17))
        for i in range(n + 1):
            px, py = x0 + tx * L * i / n, y0 + ty * L * i / n
            ax.plot([px, px + nx * 0.17 + tx * 0.11], [py, py + ny * 0.17 + ty * 0.11],
                    color=GRIS, lw=0.8, zorder=4)
    elif cond == "discontinuo":
        e = 0.12
        ax.plot([x0 - nx * e + tx * e, x1 - nx * e - tx * e],
                [y0 - ny * e + ty * e, y1 - ny * e - ty * e],
                color=AZUL, lw=1.8, ls=(0, (4, 3)), zorder=5)


def _etiqueta_exterior(ax, W, H, borde, texto, dist, fs) -> None:
    (x0, y0), (x1, y1) = _extremos(W, H, borde)
    nx, ny = NORMAL[borde]
    ax.text((x0 + x1) / 2 + nx * dist, (y0 + y1) / 2 + ny * dist, texto, ha="center",
            va="center", fontsize=fs, color=GRIS, rotation=90 if nx else 0)


def _superior(ax, W, H, borde, texto, largo, fuera, tenue, fs) -> None:
    """Varilla superior perpendicular al borde con su etiqueta de dos líneas."""
    color, alpha = SUP, 0.55 if tenue else 1.0
    if borde in ("norte", "sur"):
        x, y = 0.74 * W, (H if borde == "norte" else 0.0)
        s = -1 if borde == "norte" else 1
        ax.plot([x, x], [y - s * fuera, y + s * largo], color=color, lw=2.2, alpha=alpha, zorder=6)
        ax.text(x - 0.06, y + s * min(largo, 0.9) * 0.5, texto, color=color, fontsize=fs,
                alpha=alpha, rotation=90, ha="right", va="center", zorder=7, linespacing=0.95)
    else:
        x, y = (W if borde == "este" else 0.0), 0.15 * H
        s = -1 if borde == "este" else 1
        ax.plot([x - s * fuera, x + s * largo], [y, y], color=color, lw=2.2, alpha=alpha, zorder=6)
        ax.text(x + s * largo * 0.5, y + 0.06, texto, color=color, fontsize=fs, alpha=alpha,
                ha="center", va="bottom", zorder=7, linespacing=0.95)


def _volado(ax, W, H, borde, L, texto, fs) -> None:
    xy, w, h = {"norte": ((0, H), W, L), "sur": ((0, -L), W, L),
                "este": ((W, 0), L, H), "oeste": ((-L, 0), L, H)}[borde]
    ax.add_patch(Rectangle(xy, w, h, fc="#F3F0E6", ec=GRIS, lw=1.0, hatch="..", zorder=1))
    ax.text(xy[0] + w * 0.30, xy[1] + h * 0.5, texto, ha="center", va="center", fontsize=fs,
            rotation=90 if borde in ("este", "oeste") else 0, zorder=8, linespacing=0.95,
            bbox=dict(boxstyle="round,pad=0.2", fc="white", ec="#999999", lw=0.5))


def _armado(r: ResultadoPano, clave: str) -> str:
    x = r.flexion.get(clave)
    return "-" if x is None else x.armado + (" mín." if x.constructivo else "")


def dibujar_planta(ax, piso: Piso, r: ResultadoPano, fs: float = 7.5) -> None:
    p = r.pano
    W, H = p.ancho_x, p.ancho_y
    losa = piso.losa
    ax.add_patch(Rectangle((0, 0), W, H, fc="#FBFDFB" if r.calculado else "#EDEDED", ec="none",
                           hatch=None if r.calculado else "////", zorder=0))
    if losa.nervada and r.calculado:            # nervios en las dos direcciones, a escala
        s = losa.separacion_nervios / 100
        k = 1
        while k * s < W - 1e-6:
            ax.plot([k * s, k * s], [0, H], color=NERVIO, lw=0.7, zorder=1)
            k += 1
        k = 1
        while k * s < H - 1e-6:
            ax.plot([0, W], [k * s, k * s], color=NERVIO, lw=0.7, zorder=1)
            k += 1
    ext = {b: 0.0 for b in BORDES}
    for b in BORDES:
        _borde(ax, W, H, b, p.cond[b])
        vol = p.volado_en(b)
        rv = next((v for v in r.volados if v.volado.borde == b), None)
        if vol:
            L = rv.L_eje if rv else vol.longitud
            ext[b] = L
            texto = f"Volado {num(vol.longitud)} m"
            if rv:
                texto += f"\nMu = {num(rv.Mu, 0)} kg·m/m\nVu = {num(rv.Vu, 0)} kg/m"
            _volado(ax, W, H, b, L, texto, fs - 0.5)
        else:
            vecinos = ", ".join(q for q, _ in p.vecinos[b])
            quien = (f"Paño {vecinos}" if vecinos
                     else ("Borde libre" if p.cond[b] == "libre" else "Perímetro"))
            _etiqueta_exterior(ax, W, H, b, f"{quien} ({p.cond[b]})", 0.42, fs)
    # Cotas
    yc, xc = -(0.85 + ext["sur"]), W + 0.85 + ext["este"]
    ax.annotate("", xy=(W, yc), xytext=(0, yc), arrowprops=dict(arrowstyle="<->", color="black", lw=0.8))
    ax.text(W / 2, yc - 0.07, f"{num(W)} m (eje {p.ejes_x[0]} a {p.ejes_x[1]})", ha="center",
            va="top", fontsize=fs)
    ax.annotate("", xy=(xc, H), xytext=(xc, 0), arrowprops=dict(arrowstyle="<->", color="black", lw=0.8))
    ax.text(xc + 0.07, H / 2, f"{num(H)} m (eje {p.ejes_y[0]} a {p.ejes_y[1]})", ha="left",
            va="center", fontsize=fs, rotation=90)
    # Identificación
    cx, cy = 0.55 * W, 0.64 * H
    if r.calculado:
        clasif = (f"Tipo {r.tipo} - Bidireccional" if r.tipo
                  else f"Unidireccional (dirección {r.dir_corta})")
        if r.tipo:
            ax.add_patch(Circle((cx, cy + 0.34), 0.21, fc="white", ec="black", lw=1.1, zorder=8))
            ax.text(cx, cy + 0.34, str(r.tipo), ha="center", va="center", fontsize=fs + 3,
                    fontweight="bold", zorder=9)
        ax.text(cx, cy, f"{p.id}\n{clasif}\nLx/Ly = {num(r.beta)}", ha="center", va="top",
                fontsize=fs + 0.5, fontweight="bold", zorder=8, linespacing=1.0,
                bbox=dict(boxstyle="round,pad=0.2", fc="white", ec="none", alpha=0.85))
    else:
        ax.text(W / 2, H / 2, f"{p.id}\nFUERA DE ALCANCE\nNo calculado", ha="center", va="center",
                fontsize=fs + 2, fontweight="bold", zorder=8,
                bbox=dict(boxstyle="round,pad=0.3", fc="white", ec=GRIS, lw=0.6))
    if r.calculado:
        _armado_en_planta(ax, r, W, H, fs)
    ax.set_xlim(-(1.0 + ext["oeste"]), W + 1.45 + ext["este"])
    ax.set_ylim(-(1.65 + ext["sur"]), H + 0.85 + ext["norte"])
    ax.set_aspect("equal")
    ax.axis("off")
    ax.set_title(f"Planta del paño {p.id}: bordes, momentos de diseño (kg·m/m) y armado\n"
                 "Rayado = continuo   |   Trazos = discontinuo   |   Línea simple = libre",
                 fontsize=fs + 1)


def _armado_en_planta(ax, r: ResultadoPano, W: float, H: float, fs: float) -> None:
    p = r.pano
    kx, ky = ("corta", "larga") if r.dir_corta == "X" else ("larga", "corta")
    y = 0.36 * H
    ax.annotate("", xy=(0.93 * W, y), xytext=(0.27 * W, y),
                arrowprops=dict(arrowstyle="<->", color=INF, lw=1.8), zorder=6)
    ax.text(0.48 * W, y - 0.06, f"M+ = {num(r.M_pos[kx], 0)}   inf. X: {_armado(r, 'pos_' + kx)}",
            color=INF, fontsize=fs, ha="center", va="top", zorder=7)
    x = 0.13 * W
    ax.annotate("", xy=(x, 0.93 * H), xytext=(x, 0.30 * H),
                arrowprops=dict(arrowstyle="<->", color=INF, lw=1.8), zorder=6)
    ax.text(x - 0.06, 0.615 * H, f"M+ = {num(r.M_pos[ky], 0)}   inf. Y: {_armado(r, 'pos_' + ky)}",
            color=INF, fontsize=fs, rotation=90, ha="right", va="center", zorder=7)
    minimos = []
    for b in BORDES:
        dis = r.flexion.get(f"neg_{b}")
        if dis is None:
            continue
        if dis.constructivo:            # sin momento: se lista al pie para no recargar el dibujo
            minimos.append(f"{b} {dis.armado}")
            continue
        rv = next((v for v in r.volados if v.volado.borde == b), None)
        largo = min(0.20 * p.luz_perpendicular(b), 1.0)
        fuera = 0.0
        if rv:
            largo, fuera = max(min(rv.prolongacion, 0.8 * p.luz_perpendicular(b)), 0.3), rv.L_eje - 0.06
        elif p.vecinos[b]:
            fuera = 0.28          # la varilla continúa hacia el paño vecino
        _superior(ax, W, H, b, f"M− = {num(dis.Mu, 0)}\nsup. {dis.armado}", largo, fuera, False, fs)
    if minimos:
        ax.text(W / 2, -(1.30 + sum(v.L_eje for v in r.volados if v.volado.borde == "sur")),
                "Acero superior mínimo (sin momento): " + "; ".join(minimos), ha="center",
                va="top", fontsize=fs - 0.5, color=SUP)
