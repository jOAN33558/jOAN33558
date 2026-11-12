"""Compatibilidad entre paños vecinos: en cada borde común se diseña con el mayor de
los dos momentos negativos (y con el del volado, si lo hay)."""
from __future__ import annotations

from .memoria import fmt
from .modelos import BORDES, OPUESTO, BordeComun, Piso, ResultadoPano


def aplicar(piso: Piso, resultados: dict[str, ResultadoPano]) -> list[BordeComun]:
    comunes: list[BordeComun] = []
    for p in piso.panos:
        res = resultados[p.id]
        if not res.calculado:
            continue
        mem = res.memoria
        mem.seccion("6. COMPATIBILIDAD DE MOMENTOS NEGATIVOS EN LOS BORDES")
        for b in BORDES:
            if p.cond[b] == "libre":
                continue
            propio = res.M_borde.get(b, 0.0)
            M, origen, detalle = propio, "propio", [f"propio = {fmt(propio)}"]
            for qid, _ in p.vecinos[b]:
                rq = resultados[qid]
                if not rq.calculado:
                    detalle.append(f"{qid}: fuera de alcance")
                    res.avisos.append(f"El paño vecino {qid} (borde {b}) está fuera de alcance: "
                                      "su momento no se consideró en este borde.")
                    continue
                Mq = rq.M_borde.get(OPUESTO[b], 0.0)
                detalle.append(f"{qid} = {fmt(Mq)}")
                if Mq > M:
                    M, origen = Mq, f"vecino {qid}"
                if not any({c.pano_a, c.pano_b} == {p.id, qid} for c in comunes):
                    comunes.append(BordeComun(p.eje_de(b), p.id, b, propio, qid, OPUESTO[b],
                                              Mq, max(propio, Mq)))
            for rv in res.volados:
                if rv.volado.borde == b:
                    rv.M_pano = propio
                    detalle.append(f"volado = {fmt(rv.Mu)}")
                    if rv.Mu > M:
                        M, origen = rv.Mu, "volado"
            res.M_dis[b], res.origen[b] = M, origen
            mem.paso(f"Borde {b} (eje {p.eje_de(b)}), {p.cond[b]}", "M(−) diseño = máx(momentos)",
                     "; ".join(detalle), M, "kg·m/m", f"Gobierna: {origen}" if M > 0 else
                     "Sin momento: acero constructivo")
    return comunes
