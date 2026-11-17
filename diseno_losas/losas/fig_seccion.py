"""Figura de la sección transversal a escala, con dimensiones y armado."""
from __future__ import annotations

from matplotlib.patches import Circle, Polygon, Rectangle

from .fig_planta import GRIS, INF, SUP, num
from .modelos import DisenoFlexion, Losa, Piso, ResultadoPano

HORMIGON, BLOQUE = "#D5D8DC", "#FBF4DF"


def _cota(ax, a, b, texto, fs, dx=0.0, dy=0.0, rot=0, color="black") -> None:
    ax.annotate("", xy=b, xytext=a, arrowprops=dict(arrowstyle="<->", color=color, lw=0.7,
                                                    shrinkA=0, shrinkB=0))
    ax.text((a[0] + b[0]) / 2 + dx, (a[1] + b[1]) / 2 + dy, texto, fontsize=fs, ha="center",
            va="center", rotation=rot, color=color,
            bbox=dict(boxstyle="square,pad=0.08", fc="white", ec="none", alpha=0.85))


def _hormigon(ax, losa: Losa, y0: float, n: int = 2) -> tuple[float, list[float]]:
    """Dibuja la losa (cm). Devuelve el ancho total y los ejes de los nervios."""
    h = losa.altura
    if not losa.nervada:
        ax.add_patch(Rectangle((0, y0), 100, h, fc=HORMIGON, ec="black", lw=1.2, zorder=2))
        return 100.0, []
    s, bw, hn = losa.separacion_nervios, losa.ancho_nervio, losa.hn
    ancho = n * s
    ejes = [s * (i + 0.5) for i in range(n)]
    pts = [(0, y0 + h), (ancho, y0 + h), (ancho, y0 + hn)]
    for xc in reversed(ejes):
        pts += [(xc + bw / 2, y0 + hn), (xc + bw / 2, y0), (xc - bw / 2, y0), (xc - bw / 2, y0 + hn)]
    pts.append((0, y0 + hn))
    limites = [0.0] + [v for xc in ejes for v in (xc - bw / 2, xc + bw / 2)] + [ancho]
    for xa, xb in zip(limites[::2], limites[1::2]):
        ax.add_patch(Rectangle((xa, y0), xb - xa, hn, fc=BLOQUE, ec="#B9A46A", lw=0.6,
                               hatch="....", zorder=1))
    ax.add_patch(Polygon(pts, closed=True, fc=HORMIGON, ec="black", lw=1.2, zorder=2))
    return ancho, ejes


def _barras(ax, losa: Losa, dis: DisenoFlexion, y: float, ejes: list[float], color: str,
            alpha: float = 1.0) -> None:
    radio = dis.diametro / 20
    if losa.nervada:
        for xc in ejes:
            paso = max(dis.diametro / 10 + 0.6, 2.6)
            for k in range(dis.n):
                x = xc + (k - (dis.n - 1) / 2) * paso
                ax.add_patch(Circle((x, y), radio, fc=color, ec="black", lw=0.4, alpha=alpha, zorder=5))
    else:
        x = dis.separacion / 2
        while x < 100:
            ax.add_patch(Circle((x, y), radio, fc=color, ec="black", lw=0.4, alpha=alpha, zorder=5))
            x += dis.separacion


def _dimensiones(ax, losa: Losa, y0: float, ancho: float, ejes: list[float], fs: float) -> None:
    h = losa.altura
    _cota(ax, (-6, y0), (-6, y0 + h), f"h = {num(h, 0)}", fs, dx=-5, rot=90)
    if losa.nervada:
        s, bw, hn, el = losa.separacion_nervios, losa.ancho_nervio, losa.hn, losa.loseta
        _cota(ax, (ejes[0], y0 + h + 4), (ejes[1], y0 + h + 4), f"s = {num(s, 0)}", fs, dy=3.2)
        _cota(ax, (ejes[1] - bw / 2, y0 - 4), (ejes[1] + bw / 2, y0 - 4), f"bw = {num(bw, 0)}", fs, dy=-3.4)
        _cota(ax, (ancho + 5, y0 + hn), (ancho + 5, y0 + h), f"el = {num(el, 0)}", fs, dx=9)
        _cota(ax, (ancho + 5, y0), (ancho + 5, y0 + hn), f"hn = {num(hn, 0)}", fs, dx=9)
    else:
        _cota(ax, (0, y0 - 4), (100, y0 - 4), "franja de 100 cm", fs, dy=-3.4)


def dibujar_seccion_tipo(ax, piso: Piso, fs: float = 7.5) -> None:
    """Sección tipo de la losa, sin armado, con sus dimensiones (cm)."""
    losa = piso.losa
    ancho, ejes = _hormigon(ax, losa, 0.0, 3 if losa.nervada else 2)
    _dimensiones(ax, losa, 0.0, ancho, ejes, fs)
    ax.set_xlim(-22, ancho + 28)
    ax.set_ylim(-14, losa.altura + 14)
    ax.set_aspect("equal")
    ax.axis("off")
    ax.set_title("Sección tipo de la losa (cm, a escala)", fontsize=fs + 1)


def dibujar_seccion(ax, piso: Piso, r: ResultadoPano, fs: float = 7.5) -> None:
    """Dos cortes de la dirección corta: en el vano (M+) y sobre el apoyo (M−)."""
    losa, mat = piso.losa, piso.materiales
    h, rec = losa.altura, mat.recubrimiento
    inf = r.flexion["pos_corta"]
    negs = [r.flexion[f"neg_{b}"] for b in r.largos if f"neg_{b}" in r.flexion]
    sup = max(negs, key=lambda x: (not x.constructivo, x.As_u)) if negs else None
    borde_sup = next((b for b in r.largos if r.flexion.get(f"neg_{b}") is sup), "")
    paso = h + 32
    unidad = "por nervio" if losa.nervada else "por metro"
    for fila, titulo in ((1, "En el vano: acero inferior"), (0, "Sobre el apoyo: acero superior")):
        y0 = fila * paso
        ancho, ejes = _hormigon(ax, losa, y0)
        ax.text(ancho / 2, y0 + h + (12 if fila else 10), titulo, ha="center", va="bottom",
                fontsize=fs + 0.5, fontweight="bold")
        y_inf = y0 + rec + inf.diametro / 20
        xd = (ejes[0] + losa.ancho_nervio / 2 + 6) if losa.nervada else 12
        if fila == 1:
            _dimensiones(ax, losa, y0, ancho, ejes, fs)
            _barras(ax, losa, inf, y_inf, ejes, INF)
            _cota(ax, (xd, y0 + h), (xd, y_inf), f"d = {num(inf.d, 1)}", fs, dx=8.5, color=INF)
            malla = (f"; malla Ø{num(losa.diametro_malla, 0)} mm en la loseta" if losa.nervada else "")
            ax.text(ancho / 2, y0 - 10.5, f"inf. {inf.armado} {unidad}{malla}", ha="center",
                    va="top", fontsize=fs + 0.5, color=INF)
            if losa.nervada:
                ax.plot([1, ancho - 1], [y0 + losa.hn + losa.loseta / 2] * 2, color=GRIS, lw=0.8,
                        ls=(0, (3, 2)), zorder=4)
        else:
            _barras(ax, losa, inf, y_inf, ejes, INF, alpha=0.35)
            if sup is not None:
                y_sup = y0 + h - rec - sup.diametro / 20
                _barras(ax, losa, sup, y_sup, ejes, SUP)
                _cota(ax, (xd, y0), (xd, y_sup), f"d = {num(sup.d, 1)}", fs, dx=8.5, color=SUP)
                nota = " mín." if sup.constructivo else ""
                ax.text(ancho / 2, y0 - 4, f"sup. {sup.armado}{nota} {unidad} (borde {borde_sup})",
                        ha="center", va="top", fontsize=fs + 0.5, color=SUP)
    ax.set_xlim(-20, ancho + 26)
    ax.set_ylim(-14, paso + h + 20)
    ax.set_aspect("equal")
    ax.axis("off")
    ax.set_title(f"Sección en la dirección corta ({r.dir_corta}), cm a escala. Recubrimiento "
                 f"{num(rec, 1)} cm", fontsize=fs + 1)
