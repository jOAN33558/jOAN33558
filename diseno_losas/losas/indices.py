"""Índices de aprovechamiento (demanda / capacidad) de las verificaciones de un paño."""
from __future__ import annotations

from dataclasses import dataclass

from .modelos import ResultadoPano

GRUPOS = ("Flexión", "Cortante", "Flechas", "Altura")


@dataclass
class Indice:
    nombre: str
    grupo: str
    valor: float      # demanda / capacidad; cumple si <= 1
    estado: str       # "ok" | "no" | "aviso"


def _estado(valor: float, cumple: bool = True) -> str:
    return "ok" if valor <= 1 + 1e-9 and cumple else "no"


def _cortante(rc, prefijo: str) -> list[Indice]:
    if rc is None:
        return []
    r = rc.vu / rc.vc
    if rc.estado == "CUMPLE con macizado":
        return [Indice(f"{prefijo}Cortante a d, sin macizar", "Cortante", r, "aviso"),
                Indice(f"{prefijo}Cortante al borde del macizado", "Cortante",
                       rc.vu_mac / rc.vc, "ok")]
    return [Indice(f"{prefijo}Cortante", "Cortante", r, _estado(r, rc.cumple))]


def _flechas(rf, prefijo: str) -> list[Indice]:
    if rf is None:
        return []
    a, b = rf.delta_L / rf.lim_L, rf.delta_lp / rf.lim_lp
    return [Indice(f"{prefijo}Flecha por carga viva", "Flechas", a, _estado(a)),
            Indice(f"{prefijo}Flecha diferida", "Flechas", b, _estado(b))]


def indices(r: ResultadoPano) -> list[Indice]:
    """Lista de índices del paño, en el orden de la memoria."""
    if not r.calculado:
        return []
    lista: list[Indice] = []
    for x in r.flexion.values():
        if x.constructivo:
            continue
        valor = x.As_dis / x.As_col if x.As_req is not None else 9.99
        lista.append(Indice(f"{x.nombre} ({x.armado})", "Flexión", valor, _estado(valor, x.cumple)))
    lista += _cortante(r.cortante, "")
    lista += _flechas(r.flechas, "")
    for c in r.checks:
        if c.nombre.startswith("Altura") and isinstance(c.valor, (int, float)) and c.valor:
            v = c.limite / c.valor
            lista.append(Indice("Altura mínima / altura", "Altura", v, _estado(v, c.cumple)))
    for rv in r.volados:
        pre = f"Volado {rv.volado.borde}: "
        lista += _cortante(rv.cortante, pre)
        lista += _flechas(rv.flechas, pre)
        for c in rv.checks:
            if c.nombre.startswith("Altura"):
                v = c.limite / c.valor
                lista.append(Indice(pre + "altura mínima / altura", "Altura", v, _estado(v, c.cumple)))
    return lista


def maximos(r: ResultadoPano) -> dict[str, float]:
    """Mayor índice de cada grupo. El cortante resuelto con macizado no cuenta como fallo."""
    out: dict[str, float] = {}
    for i in indices(r):
        if i.estado == "aviso":
            continue
        out[i.grupo] = max(out.get(i.grupo, 0.0), i.valor)
    return out
