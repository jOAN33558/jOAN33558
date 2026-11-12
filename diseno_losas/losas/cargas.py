"""Cargas de la losa y combinaciones 1,4D y 1,2D + 1,6L (NEC-SE-CG / ACI 318-19 5.3.1)."""
from __future__ import annotations

from dataclasses import dataclass, replace

from .memoria import Memoria, fmt
from .modelos import Cargas, Losa, Materiales, Pano, Piso


@dataclass
class CargasPano:
    pp: float        # peso propio, kg/m²
    sobre: float     # acabados + paredes + otras, kg/m²
    D: float
    L: float
    qu: float
    combo: str

    @property
    def qs(self) -> float:
        return self.D + self.L


def mayorar(D: float, L: float) -> tuple[float, str]:
    u1, u2 = 1.4 * D, 1.2 * D + 1.6 * L
    return (u1, "1,4D") if u1 > u2 else (u2, "1,2D + 1,6L")


def peso_propio(losa: Losa, mat: Materiales, mem: Memoria | None = None) -> float:
    g = mat.peso_hormigon
    if not losa.nervada:
        pp = losa.altura / 100 * g
        if mem:
            mem.paso("Peso propio (losa maciza)", "h·γh", f"{fmt(losa.altura / 100)}·{fmt(g, 0)}",
                     pp, "kg/m²")
        return pp
    s, el, bw, hn = losa.separacion_nervios, losa.loseta, losa.ancho_nervio, losa.hn
    n = 100 / s
    loseta = el / 100 * g
    nervios = (2 * n * bw * hn / 10000 - n**2 * (bw / 100) ** 2 * hn / 100) * g
    pp = loseta + nervios + losa.peso_bloques
    if mem:
        mem.paso("Peso de la loseta", "el·γh", f"{fmt(el / 100)}·{fmt(g, 0)}", loseta, "kg/m²")
        mem.paso("Peso de nervios (dos direcciones, sin duplicar cruces)",
                 "[2·n·bw·hn − n²·bw²·hn]·γh,  n = 100/s",
                 f"[2·{fmt(n)}·{fmt(bw / 100)}·{fmt(hn / 100)} − {fmt(n)}²·{fmt(bw / 100)}²·"
                 f"{fmt(hn / 100)}]·{fmt(g, 0)}", nervios, "kg/m²")
        mem.dato("Peso de bloques", losa.peso_bloques, "kg/m²")
        mem.paso("Peso propio de la losa", "loseta + nervios + bloques", "", pp, "kg/m²")
    return pp


def cargas_de(base: Cargas, reemplazos: dict) -> Cargas:
    validos = {k: v for k, v in reemplazos.items() if k in ("acabados", "paredes", "otras", "viva")}
    return replace(base, **validos)


def cargas_pano(piso: Piso, reemplazos: dict, pp: float, mem: Memoria | None = None,
                titulo: str = "") -> CargasPano:
    c = cargas_de(piso.cargas, reemplazos)
    sobre = c.acabados + c.paredes + c.otras
    D = pp + sobre
    qu, combo = mayorar(D, c.viva)
    if mem:
        if titulo:
            mem.seccion(titulo)
        mem.dato("Peso propio de la losa", pp, "kg/m²", "Hoja DATOS")
        mem.paso("Carga adicional permanente", "acabados + paredes + otras",
                 f"{fmt(c.acabados)} + {fmt(c.paredes)} + {fmt(c.otras)}", sobre, "kg/m²")
        mem.paso("Carga permanente", "D = pp + adicional", f"{fmt(pp)} + {fmt(sobre)}", D, "kg/m²")
        mem.dato("Carga viva" + (f" ({c.uso})" if c.uso else ""), c.viva, "kg/m²", "NEC-SE-CG")
        mem.paso("1,4D", "1,4·D", f"1,4·{fmt(D)}", 1.4 * D, "kg/m²", referencia="NEC-SE-CG")
        mem.paso("1,2D + 1,6L", "1,2·D + 1,6·L", f"1,2·{fmt(D)} + 1,6·{fmt(c.viva)}",
                 1.2 * D + 1.6 * c.viva, "kg/m²", referencia="NEC-SE-CG")
        mem.paso("Carga de diseño", "qu = máx(1,4D ; 1,2D + 1,6L)", "", qu, "kg/m²",
                 f"Gobierna {combo}", "ACI 318-19, 5.3.1")
    return CargasPano(pp, sobre, D, c.viva, qu, combo)


def pano_cargas(piso: Piso, pano: Pano, pp: float, mem: Memoria | None = None) -> CargasPano:
    return cargas_pano(piso, pano.cargas, pp, mem, "3. CARGAS")
