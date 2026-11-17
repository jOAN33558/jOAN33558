"""Geometría del piso: coordenadas, vecinos, condición de bordes y tipo de paño (1 a 18)."""
from __future__ import annotations

from .modelos import BORDES, OPUESTO, ErrorEntrada, Pano, Piso

TOL = 1e-6

# (bordes largos, bordes cortos) -> tipo, para paños sin borde libre.
# c = continuo, d = discontinuo; el par va ordenado.
SIN_LIBRE = {
    ("cc", "cc"): 1, ("cd", "cc"): 2, ("cc", "cd"): 3,
    ("dd", "cc"): 4, ("cc", "dd"): 5, ("cd", "cd"): 6,
    ("cd", "dd"): 7, ("dd", "cd"): 8, ("dd", "dd"): 9,
}
# Un borde LARGO libre: (opuesto, adyacentes cortos) -> tipo
LIBRE_LARGO = {("c", "cc"): 10, ("c", "cd"): 12, ("c", "dd"): 14, ("d", "dd"): 16}
# Un borde CORTO libre: (opuesto, adyacentes largos) -> tipo
LIBRE_CORTO = {("c", "cc"): 11, ("c", "cd"): 13, ("c", "dd"): 15, ("d", "dd"): 17}


def _par(a: str, b: str) -> str:
    return "".join(sorted(a[0] + b[0]))


def deducir_tipo(largos: tuple[str, str], cortos: tuple[str, str]) -> int | None:
    """Tipo de paño de las Tablas 9.5 / 9.7 a partir de la condición de sus bordes.

    ``largos`` son los dos bordes de longitud Ly (opuestos entre sí) y ``cortos``
    los dos de longitud Lx. Devuelve None si la combinación no está tabulada.
    """
    libres_l = [c for c in largos if c == "libre"]
    libres_c = [c for c in cortos if c == "libre"]
    if not libres_l and not libres_c:
        return SIN_LIBRE[(_par(*largos), _par(*cortos))]
    if len(libres_l) == 1 and not libres_c:
        opuesto = next(c for c in largos if c != "libre")
        return LIBRE_LARGO.get((opuesto[0], _par(*cortos)))
    if len(libres_c) == 1 and not libres_l:
        opuesto = next(c for c in cortos if c != "libre")
        return LIBRE_CORTO.get((opuesto[0], _par(*largos)))
    if len(libres_l) == 1 and len(libres_c) == 1:
        otros = [c for c in largos + cortos if c != "libre"]
        return 18 if otros == ["continuo", "continuo"] else None
    return None


def orientar(pano: Pano) -> tuple[float, float, str, tuple[str, str], tuple[str, str]]:
    """Devuelve (Lx, Ly, dirección corta, bordes largos, bordes cortos)."""
    if pano.ancho_x <= pano.ancho_y + TOL:
        return pano.ancho_x, pano.ancho_y, "X", ("oeste", "este"), ("sur", "norte")
    return pano.ancho_y, pano.ancho_x, "Y", ("sur", "norte"), ("oeste", "este")


def _solape(a0: float, a1: float, b0: float, b1: float) -> float:
    return max(0.0, min(a1, b1) - max(a0, b0))


def _vecinos(p: Pano, panos: list[Pano]) -> dict[str, list[tuple[str, float]]]:
    v: dict[str, list[tuple[str, float]]] = {b: [] for b in BORDES}
    for q in panos:
        if q is p:
            continue
        sx, sy = _solape(p.x0, p.x1, q.x0, q.x1), _solape(p.y0, p.y1, q.y0, q.y1)
        if sx > TOL and abs(q.y0 - p.y1) < TOL:
            v["norte"].append((q.id, sx))
        if sx > TOL and abs(q.y1 - p.y0) < TOL:
            v["sur"].append((q.id, sx))
        if sy > TOL and abs(q.x0 - p.x1) < TOL:
            v["este"].append((q.id, sy))
        if sy > TOL and abs(q.x1 - p.x0) < TOL:
            v["oeste"].append((q.id, sy))
    return v


def _condicion(piso: Piso, p: Pano, borde: str) -> str:
    declarada = p.bordes.get(borde, "auto")
    solape = sum(s for _, s in p.vecinos[borde])
    frac = solape / p.longitud_borde(borde)
    if p.volado_en(borde) and p.vecinos[borde]:
        raise ErrorEntrada(f"Paño {p.id}: el borde {borde} tiene volado y también un paño "
                           "vecino; revise la lista de paños.")
    if declarada == "libre":
        if p.volado_en(borde):
            raise ErrorEntrada(f"Paño {p.id}: el borde {borde} no puede ser libre y tener "
                               "volado (el volado necesita una viga de apoyo).")
        if p.vecinos[borde]:
            piso.avisos.append(f"Paño {p.id}: el borde {borde} se declaró libre pero tiene un "
                               "paño vecino; se respeta lo declarado.")
        return "libre"
    if declarada == "continuo":
        if not p.vecinos[borde] and not p.volado_en(borde):
            piso.avisos.append(f"Paño {p.id}: el borde {borde} se declaró continuo sin paño "
                               "vecino en la lista; la continuidad queda bajo responsabilidad "
                               "del usuario.")
        return "continuo"
    if declarada == "discontinuo":
        return "discontinuo"
    # automático
    if p.volado_en(borde):
        return "discontinuo"     # conservador para M+; el M- lo da el volado
    if frac >= 1 - 1e-3:
        return "continuo"
    if frac > 1e-3:
        cond = "continuo" if frac >= 0.5 else "discontinuo"
        piso.avisos.append(f"Paño {p.id}: el borde {borde} tiene vecino solo en el "
                           f"{frac * 100:.0f} % de su longitud; se toma como {cond}.")
        return cond
    return "discontinuo"


def preparar(piso: Piso) -> None:
    """Resuelve coordenadas, detecta traslapes, vecinos y condición de cada borde."""
    for p in piso.panos:
        p.x0, p.x1 = piso.ejes_x[p.ejes_x[0]], piso.ejes_x[p.ejes_x[1]]
        p.y0, p.y1 = piso.ejes_y[p.ejes_y[0]], piso.ejes_y[p.ejes_y[1]]
    for i, p in enumerate(piso.panos):
        for q in piso.panos[i + 1:]:
            if (_solape(p.x0, p.x1, q.x0, q.x1) > TOL
                    and _solape(p.y0, p.y1, q.y0, q.y1) > TOL):
                raise ErrorEntrada(f"Los paños {p.id} y {q.id} se superponen; revise sus ejes.")
    for p in piso.panos:
        p.vecinos = _vecinos(p, piso.panos)
    for p in piso.panos:
        p.cond = {b: _condicion(piso, p, b) for b in BORDES}
    for p in piso.panos:
        for b in BORDES:
            for qid, _ in p.vecinos[b]:
                q = piso.pano(qid)
                if (p.cond[b] == "libre") != (q.cond[OPUESTO[b]] == "libre"):
                    piso.avisos.append(
                        f"Borde común {p.id}-{q.id}: uno de los paños lo declara libre y el "
                        "otro no; revise la entrada.")
        esquinas = [("norte", "este"), ("norte", "oeste"), ("sur", "este"), ("sur", "oeste")]
        for a, b in esquinas:
            if p.volado_en(a) and p.volado_en(b):
                piso.avisos.append(f"Paño {p.id}: volados en los bordes {a} y {b}. La esquina "
                                   "del volado no está cubierta por este cálculo.")
