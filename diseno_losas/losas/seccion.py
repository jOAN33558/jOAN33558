"""Propiedades de la sección de losa (nervio en T o franja maciza de 1 m)."""
from __future__ import annotations

from dataclasses import dataclass

from .memoria import Memoria, fmt
from .modelos import Losa


@dataclass
class Seccion:
    nervada: bool
    h: float        # cm
    b_ala: float    # cm, ancho de la unidad (separación de nervios o 100)
    bw: float       # cm, alma de la unidad
    el: float       # cm, loseta (h en maciza)
    A: float        # cm² por unidad
    yg: float       # cm, centroide desde la fibra inferior
    Ig: float       # cm4 por unidad
    he: float       # cm, altura maciza equivalente en inercia

    @property
    def por_metro(self) -> float:
        """Unidades (nervios) por metro de losa."""
        return 100.0 / self.b_ala

    @property
    def bw_m(self) -> float:
        """Ancho de alma por metro de losa (cm/m)."""
        return self.bw * self.por_metro

    @property
    def Ig_m(self) -> float:
        return self.Ig * self.por_metro

    @property
    def hn(self) -> float:
        return self.h - self.el


def propiedades(losa: Losa, mem: Memoria | None = None) -> Seccion:
    h = losa.altura
    if not losa.nervada:
        sec = Seccion(False, h, 100.0, 100.0, h, 100.0 * h, h / 2, 100.0 * h**3 / 12, h)
        if mem:
            mem.seccion("PROPIEDADES DE LA SECCIÓN (franja maciza de 1 m)")
            mem.paso("Inercia bruta", "Ig = 100·h³/12", f"100·{fmt(h)}³/12", sec.Ig, "cm4/m")
        return sec
    s, el, bw, hn = losa.separacion_nervios, losa.loseta, losa.ancho_nervio, losa.hn
    A = s * el + bw * hn
    yg = (bw * hn * hn / 2 + s * el * (hn + el / 2)) / A
    Ig = (bw * hn**3 / 12 + bw * hn * (yg - hn / 2) ** 2
          + s * el**3 / 12 + s * el * (hn + el / 2 - yg) ** 2)
    he = (12 * Ig / s) ** (1 / 3)
    sec = Seccion(True, h, s, bw, el, A, yg, Ig, he)
    if mem:
        mem.seccion("PROPIEDADES DE LA SECCIÓN T (un nervio con su ala)")
        mem.paso("Área", "A = s·el + bw·hn", f"{fmt(s)}·{fmt(el)} + {fmt(bw)}·{fmt(hn)}",
                 A, "cm²")
        mem.paso("Centro de gravedad (desde abajo)",
                 "yg = [bw·hn·hn/2 + s·el·(hn + el/2)] / A",
                 f"[{fmt(bw)}·{fmt(hn)}·{fmt(hn / 2)} + {fmt(s)}·{fmt(el)}·{fmt(hn + el / 2)}]"
                 f" / {fmt(A)}", yg, "cm")
        mem.paso("Inercia de la sección T",
                 "I = bw·hn³/12 + bw·hn·(yg − hn/2)² + s·el³/12 + s·el·(hn + el/2 − yg)²",
                 "", Ig, "cm4")
        mem.paso("Altura maciza equivalente", "he = (12·I/s)^(1/3)",
                 f"(12·{fmt(Ig)}/{fmt(s)})^(1/3)", he, "cm", referencia="Tabla 9.7, simbología")
    return sec
