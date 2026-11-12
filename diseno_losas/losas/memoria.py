"""Registro de la memoria de cálculo: dato, fórmula, sustitución, resultado y verificación."""
from __future__ import annotations

from dataclasses import dataclass, field


def fmt(x, nd: int = 2) -> str:
    """Número con coma decimal para los textos de la memoria."""
    if x is None:
        return "-"
    if isinstance(x, str):
        return x
    return f"{x:.{nd}f}".replace(".", ",")


def estado(ok: bool) -> str:
    return "CUMPLE" if ok else "NO CUMPLE"


@dataclass
class Paso:
    concepto: str
    formula: str = ""
    sustitucion: str = ""
    resultado: float | str | None = None
    unidad: str = ""
    verificacion: str = ""
    referencia: str = ""
    clase: str = "paso"        # paso | seccion | nota
    nd: int = 2


@dataclass
class Memoria:
    pasos: list[Paso] = field(default_factory=list)

    def seccion(self, titulo: str) -> None:
        self.pasos.append(Paso(titulo, clase="seccion"))

    def nota(self, texto: str) -> None:
        self.pasos.append(Paso(texto, clase="nota"))

    def paso(self, concepto, formula="", sustitucion="", resultado=None, unidad="",
             verificacion="", referencia="", nd=2) -> None:
        self.pasos.append(Paso(concepto, formula, sustitucion, resultado, unidad,
                               verificacion, referencia, "paso", nd))

    def dato(self, concepto, valor, unidad="", referencia="", nd=2) -> None:
        self.paso(concepto, "Dato", "", valor, unidad, "", referencia, nd)
