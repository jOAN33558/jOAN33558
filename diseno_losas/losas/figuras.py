"""Láminas de figuras generadas con los datos de cada diseño.

Las figuras se dibujan a partir de la entrada y de los resultados, por lo que cambian
con cada paño y con cada corrida del programa.
"""
from __future__ import annotations

from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
import numpy as np  # noqa: E402
from matplotlib.colors import LinearSegmentedColormap  # noqa: E402

from .cargas import cargas_pano, peso_propio  # noqa: E402
from .fig_diagramas import (AMBAR, ROJO, VERDE, dibujar_aprovechamiento,  # noqa: E402
                            dibujar_cortante, dibujar_momentos)
from .fig_planta import dibujar_planta, num  # noqa: E402
from .fig_seccion import dibujar_seccion, dibujar_seccion_tipo  # noqa: E402
from .indices import GRUPOS, maximos  # noqa: E402
from .modelos import MENSAJE_MEF, ResultadoPano, ResultadoPiso  # noqa: E402

DPI = 100


def _guardar(fig, ruta: Path) -> Path:
    ruta.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(ruta, dpi=DPI, facecolor="white")
    plt.close(fig)
    return ruta


def figura_pano(rp: ResultadoPiso, r: ResultadoPano, ruta: str | Path) -> Path:
    """Lámina del paño: planta, sección, momentos, cortante y aprovechamiento."""
    piso, p = rp.piso, r.pano
    if not r.calculado:
        fig, (ax, at) = plt.subplots(1, 2, figsize=(12, 6.5), constrained_layout=True,
                                     gridspec_kw=dict(width_ratios=[1.2, 1]))
        dibujar_planta(ax, piso, r)
        at.axis("off")
        texto = "\n\n".join(["PAÑO FUERA DE ALCANCE: NO SE CALCULÓ"] + ["- " + m for m in r.motivos]
                            + [MENSAJE_MEF])
        at.text(0.02, 0.92, texto, va="top", ha="left", fontsize=11, wrap=True,
                transform=at.transAxes)
        return _guardar(fig, Path(ruta))
    fig = plt.figure(figsize=(17, 9.6), constrained_layout=True)
    gs = fig.add_gridspec(6, 3, width_ratios=[1.05, 1.0, 1.0])
    dibujar_planta(fig.add_subplot(gs[:, 0]), piso, r)
    dibujar_seccion(fig.add_subplot(gs[0:3, 1]), piso, r)
    dibujar_aprovechamiento(fig.add_subplot(gs[3:6, 1]), r)
    dibujar_momentos(fig.add_subplot(gs[0:2, 2]), r, "corta")
    dibujar_momentos(fig.add_subplot(gs[2:4, 2]), r, "larga")
    dibujar_cortante(fig.add_subplot(gs[4:6, 2]), piso, r)
    c = r.cargas
    fig.suptitle(f"PAÑO {p.id}  -  {r.resultado}     Lx = {num(r.Lx)} m, Ly = {num(r.Ly)} m,  "
                 f"D = {num(c.D, 0)}, L = {num(c.L, 0)}, qu = {num(c.qu, 0)} kg/m² ({c.combo})",
                 fontsize=12, fontweight="bold",
                 color="#1B5E20" if r.cumple else "#9C0006")
    return _guardar(fig, Path(ruta))


def figura_general(rp: ResultadoPiso, ruta: str | Path) -> Path:
    """Sección tipo de la losa y composición de las cargas generales."""
    piso, losa, mat = rp.piso, rp.piso.losa, rp.piso.materiales
    fig, (a1, a2, a3) = plt.subplots(1, 3, figsize=(17, 4.6), constrained_layout=True,
                                     gridspec_kw=dict(width_ratios=[1.5, 1.2, 0.9]))
    dibujar_seccion_tipo(a1, piso, fs=8.5)
    pp = peso_propio(losa, mat)
    cg = piso.cargas
    if losa.nervada:
        loseta = losa.loseta / 100 * mat.peso_hormigon
        partes = [("Loseta", loseta), ("Nervios", pp - loseta - losa.peso_bloques),
                  ("Bloques", losa.peso_bloques)]
    else:
        partes = [("Losa maciza", pp)]
    partes += [("Acabados", cg.acabados), ("Paredes", cg.paredes), ("Otras", cg.otras)]
    partes = [(n, v) for n, v in partes if v > 0]
    colores = ["#7F8C8D", "#95A5A6", "#D9C89E", "#5DA5DA", "#F5A65B", "#B39DDB"]
    izq = 0.0
    for (nombre, v), col in zip(partes, colores):
        a2.barh(["Permanente D"], [v], left=izq, color=col, edgecolor="white", label=nombre)
        if v > 0.06 * (pp + cg.acabados + cg.paredes + cg.otras):
            a2.text(izq + v / 2, 0, f"{nombre}\n{num(v, 0)}", ha="center", va="center", fontsize=7.5)
        izq += v
    a2.barh(["Viva L"], [cg.viva], color="#E57373", edgecolor="white")
    a2.text(cg.viva / 2, 1, num(cg.viva, 0), ha="center", va="center", fontsize=8)
    a2.text(izq, 0, f"  D = {num(izq, 0)}", va="center", ha="left", fontsize=8.5, fontweight="bold")
    a2.set_xlim(0, max(izq, cg.viva) * 1.22)
    a2.set_xlabel("kg/m²", fontsize=8)
    a2.tick_params(labelsize=8)
    a2.invert_yaxis()
    a2.grid(axis="x", alpha=0.25)
    a2.set_title("Cargas de servicio generales del piso", fontsize=9.5)
    c = cargas_pano(piso, {}, pp)
    combos = [("1,4D", 1.4 * c.D), ("1,2D + 1,6L", 1.2 * c.D + 1.6 * c.L)]
    barras = a3.bar([n for n, _ in combos], [v for _, v in combos],
                    color=[VERDE if n == c.combo else "#BDBDBD" for n, _ in combos])
    for b, (_, v) in zip(barras, combos):
        a3.text(b.get_x() + b.get_width() / 2, v, num(v, 0), ha="center", va="bottom", fontsize=8.5)
    a3.set_ylim(0, max(v for _, v in combos) * 1.18)
    a3.set_ylabel("kg/m²", fontsize=8)
    a3.tick_params(labelsize=8)
    a3.grid(axis="y", alpha=0.25)
    a3.set_title(f"Combinaciones: gobierna {c.combo}", fontsize=9.5)
    return _guardar(fig, Path(ruta))


def figura_aprovechamiento_piso(rp: ResultadoPiso, ruta: str | Path) -> Path:
    """Mapa de aprovechamiento: mayor índice de cada grupo de verificación por paño."""
    ids = list(rp.panos)
    datos = np.full((len(ids), len(GRUPOS)), np.nan)
    for i, r in enumerate(rp.panos.values()):
        m = maximos(r)
        for j, g in enumerate(GRUPOS):
            if g in m:
                datos[i, j] = m[g]
    fig, ax = plt.subplots(figsize=(9, 1.6 + 0.48 * len(ids)), constrained_layout=True)
    mapa = LinearSegmentedColormap.from_list("uso", [(0, "#E8F5E9"), (0.45, VERDE), (0.499, AMBAR),
                                                     (0.5, ROJO), (1, "#7B1F1A")])
    mapa = mapa.with_extremes(bad="#E4E4E4")
    ax.imshow(np.ma.masked_invalid(datos), cmap=mapa, vmin=0, vmax=2, aspect="auto")
    for i, r in enumerate(rp.panos.values()):
        for j in range(len(GRUPOS)):
            v = datos[i, j]
            texto = "sin calcular" if not r.calculado else ("-" if np.isnan(v) else f"{num(v * 100, 0)} %")
            ax.text(j, i, texto, ha="center", va="center", fontsize=9,
                    color="white" if (not np.isnan(v) and v > 0.75) else "black",
                    fontweight="bold" if (not np.isnan(v) and v > 1) else "normal")
    ax.set_xticks(range(len(GRUPOS)))
    ax.set_xticklabels(GRUPOS, fontsize=9.5)
    ax.set_yticks(range(len(ids)))
    ax.set_yticklabels([f"{i}  ({rp.panos[i].resultado})" for i in ids], fontsize=9)
    ax.xaxis.tick_top()
    ax.set_xticks(np.arange(-0.5, len(GRUPOS)), minor=True)
    ax.set_yticks(np.arange(-0.5, len(ids)), minor=True)
    ax.grid(which="minor", color="white", lw=2)
    ax.tick_params(which="both", length=0)
    ax.set_title("Aprovechamiento máximo por paño (demanda / capacidad; cumple hasta 100 %)",
                 fontsize=10.5, pad=24)
    return _guardar(fig, Path(ruta))


def generar(rp: ResultadoPiso, carpeta: str | Path) -> dict[str, Path]:
    """Genera todas las figuras. Devuelve {id de paño | 'general' | 'aprovechamiento': ruta}."""
    carpeta = Path(carpeta)
    rutas = {"general": figura_general(rp, carpeta / "general.png"),
             "aprovechamiento": figura_aprovechamiento_piso(rp, carpeta / "aprovechamiento.png")}
    for id_, r in rp.panos.items():
        seguro = "".join(ch if ch.isalnum() or ch in "-_" else "_" for ch in id_)
        rutas[id_] = figura_pano(rp, r, carpeta / f"pano_{seguro}.png")
    return rutas
