"""Orquestador: analiza, compatibiliza y dimensiona todos los paños del piso."""
from __future__ import annotations

from . import analisis, compatibilidad, cortante, flechas, flexion, geometria, volado
from .cargas import peso_propio
from .memoria import Memoria, estado, fmt
from .modelos import (BORDES, Pano, Piso, ResultadoPano, ResultadoPiso, Verificacion)
from .seccion import Seccion, propiedades
from .verificaciones import (hmin_bidireccional, hmin_unidireccional, limites_nervios,
                             retraccion_temperatura)

NOMBRE_FLEX = {"pos_corta": "M(+) dirección corta", "pos_larga": "M(+) dirección larga"}


def _momentos(p: Pano, res: ResultadoPano) -> dict[str, tuple[float, str, str]]:
    m = {"pos_corta": (res.M_pos["corta"], "+", "corta"),
         "pos_larga": (res.M_pos["larga"], "+", "larga")}
    for b in BORDES:
        if p.cond[b] != "libre":
            m[f"neg_{b}"] = (res.M_dis.get(b, 0.0), "-", res.direccion_de(b))
    return m


def _flexion(piso: Piso, p: Pano, res: ResultadoPano) -> None:
    mat, losa, mem = piso.materiales, piso.losa, res.memoria
    h, r = losa.altura, mat.recubrimiento
    momentos = _momentos(p, res)
    bidir = res.clasificacion == "Bidireccional"
    s_max = min((2 if bidir else 3) * h, 45.0)
    phi = {"corta": losa.diametros[0], "larga": losa.diametros[0]}

    def alturas():
        return {"corta": h - r - phi["corta"] / 20,
                "larga": h - r - phi["corta"] / 10 - phi["larga"] / 20}

    def nombre(k):
        return NOMBRE_FLEX.get(k) or f"M(−) borde {k[4:]}"

    for _ in range(12):      # el peralte depende del diámetro elegido en cada capa
        d = alturas()
        dis = {k: flexion.disenar(nombre(k), M, s, d[dr], mat, losa, s_max)
               for k, (M, s, dr) in momentos.items()}
        nuevo = {dr: max([x.diametro for k, x in dis.items() if momentos[k][2] == dr]
                         + [phi[dr]]) for dr in phi}
        if nuevo == phi:
            break
        phi = nuevo
    d = alturas()
    res.d = d
    mem.seccion("7. DISEÑO A FLEXIÓN")
    mem.paso("Peralte efectivo, dirección corta (capa exterior)", "d = h − r − Ø/2",
             f"{fmt(h)} − {fmt(r)} − {fmt(phi['corta'] / 20)}", d["corta"], "cm")
    mem.paso("Peralte efectivo, dirección larga (capa interior)", "d = h − r − Øcorta − Ø/2",
             f"{fmt(h)} − {fmt(r)} − {fmt(phi['corta'] / 10)} − {fmt(phi['larga'] / 20)}",
             d["larga"], "cm")
    for k, (M, s, dr) in momentos.items():
        res.flexion[k] = flexion.disenar(nombre(k), M, s, d[dr], mat, losa, s_max, mem)
    ok = all(x.cumple for x in res.flexion.values())
    res.checks.append(Verificacion("Flexión (todos los momentos de diseño)", "", "", estado(ok),
                                   "ACI 318-19, 9.5 y 21.2"))


def _cortante(piso: Piso, p: Pano, res: ResultadoPano) -> None:
    mat, losa, mem = piso.materiales, piso.losa, res.memoria
    metodo = piso.opciones.cortante
    d = res.d["corta"]
    mem.seccion("8. CORTANTE")
    if res.clasificacion == "Bidireccional":
        sv = res.servicio
        negs = [res.flexion[f"neg_{b}"].As_col for b in res.largos if f"neg_{b}" in res.flexion]
        As = max(negs + [res.flexion["pos_corta"].As_col])
        Lx, q = res.Lx, res.cargas.qu
        mem.paso("Cortante en la cara de la viga (franja corta)",
                 "V,cara = qu·(Lx − b,viga/2)" if sv["un_apoyo"] else "V,cara = qu·(Lx/2 − b,viga/2)",
                 f"{fmt(q)}·({fmt(Lx if sv['un_apoyo'] else Lx / 2)} − {fmt(sv['bv'] / 200, 3)})",
                 res.V_cara["general"], "kg/m",
                 "Conservador: un borde largo libre, toda la carga va al apoyo opuesto"
                 if sv["un_apoyo"] else "", "Criterio de la hoja de referencia")
        res.cortante = cortante.verificar(res.V_cara["general"], q, d, mat, losa, metodo, As,
                                          "", mem)
    else:
        orden = {"CUMPLE": 0, "CUMPLE con macizado": 1, "NO CUMPLE": 2}
        peor = None
        for b, V in res.V_cara.items():
            As = res.flexion[f"neg_{b}"].As_col if f"neg_{b}" in res.flexion else None
            rc = cortante.verificar(V, res.servicio["wu"], d, mat, losa, metodo, As,
                                    f"el apoyo {b}", mem)
            if peor is None or (orden[rc.estado], rc.vu) > (orden[peor.estado], peor.vu):
                peor = rc
        res.cortante = peor
    res.checks.append(Verificacion("Cortante (vu <= vc)", res.cortante.vu, res.cortante.vc,
                                   res.cortante.estado, "ACI 318-19, 22.5 y 9.8.1.5"))


def _flechas(piso: Piso, res: ResultadoPano, sec: Seccion) -> None:
    mat, cg, mem = piso.materiales, piso.cargas, res.memoria
    c, sv = res.cargas, res.servicio
    psi = cg.fraccion_viva_sostenida
    mem.seccion("9. FLECHAS CON CARGAS DE SERVICIO")
    if res.clasificacion == "Bidireccional":
        positivo = sv["m_pos"] > 0
        m = sv["m_pos"] if positivo else sv["m_neg"]
        if positivo:
            dis = res.flexion["pos_corta"]
        else:
            dis = max((res.flexion[f"neg_{b}"] for b in res.largos if f"neg_{b}" in res.flexion),
                      key=lambda x: x.As_u)
        he = sec.he
        k_delta = 0.0001 * res.coef["delta"] * (res.Lx * 100) ** 4 / (mat.E * he**3) / 10000
        k_M = 0.0001 * m * res.Lx**2 * 100 / sec.por_metro
        niveles = {n: (k_delta * q, k_M * q) for n, q in
                   (("D", c.D), ("DL", c.D + c.L), ("SOST", c.D + psi * c.L))}
        mem.paso("Flecha elástica con D + L (sección bruta)", "Δ = 0,0001·q·δ·Lx⁴/(E·he³)",
                 f"0,0001·{fmt((c.D + c.L) / 10000, 4)}·{fmt(res.coef['delta'], 1)}·"
                 f"{fmt(res.Lx * 100, 0)}⁴/({fmt(mat.E, 0)}·{fmt(he)}³)", niveles["DL"][0], "cm",
                 referencia="Tabla de coeficientes; q de servicio en kg/cm²", nd=3)
        signo = "+" if positivo else "-"
    else:
        dis, signo = res.flexion["pos_corta"], "+"
        EI = mat.E * sec.Ig_m
        niveles = {n: (v[0] / EI, v[1] * 100 / sec.por_metro) for n, v in sv["niveles"].items()}
        mem.paso("Flecha elástica con D + L en el centro del vano (sección bruta)",
                 "Δ = 5·w·L⁴/(384·E·I) − (Ma + Mb)·L²/(16·E·I)", "viga continua, viva alternada",
                 niveles["DL"][0], "cm", referencia="Método de rigidez", nd=3)
    sf = flechas.seccion_fisurada(sec, mat, signo, dis.As_u, dis.d)
    den = 480 if cg.soporta_mamposteria else 240
    res.flechas = flechas.evaluar(niveles, sf, res.Lx * 100, den, cg.lambda_diferida, mem)
    res.checks.append(Verificacion("Flecha inmediata por carga viva <= Lx/360", res.flechas.delta_L,
                                   res.flechas.lim_L, estado(res.flechas.cumple_L),
                                   "ACI 318-19, Tabla 24.2.2"))
    res.checks.append(Verificacion(f"Flecha diferida más viva <= Lx/{den}", res.flechas.delta_lp,
                                   res.flechas.lim_lp, estado(res.flechas.cumple_lp),
                                   "ACI 318-19, 24.2.4 y Tabla 24.2.2"))


def _altura_minima(piso: Piso, p: Pano, res: ResultadoPano, sec: Seccion) -> None:
    mem = res.memoria
    mem.seccion("10. ALTURA MÍNIMA")
    if res.clasificacion == "Bidireccional":
        v = hmin_bidireccional(piso, p, res.largos, res.cortos, res.servicio["alfas"], sec, mem)
    else:
        continuos = sum(1 for b in res.largos if p.cond[b] == "continuo" or p.volado_en(b))
        v = hmin_unidireccional(res.Lx, continuos, piso.losa, piso.materiales.fy, mem)
    res.checks.append(v)


def _dimensionar(piso: Piso, p: Pano, res: ResultadoPano, sec: Seccion,
                 generales: list[Verificacion]) -> None:
    _flexion(piso, p, res)
    _cortante(piso, p, res)
    _flechas(piso, res, sec)
    _altura_minima(piso, p, res, sec)
    for rv in res.volados:
        volado.verificar(piso, p, res, rv, sec, res.memoria)
        res.checks += [Verificacion(f"Volado {rv.volado.borde}: {c.nombre}", c.valor, c.limite,
                                    c.estado, c.referencia) for c in rv.checks]
    res.checks = list(generales) + res.checks
    for dis in res.flexion.values():
        res.avisos += [f"{dis.nombre}: {n}" for n in dis.notas]
    mem = res.memoria
    mem.seccion("12. RESUMEN DE VERIFICACIONES DEL PAÑO")
    for c in res.checks:
        mem.paso(c.nombre, "", "" if c.valor == "" else f"{fmt(c.valor, 3)} vs {fmt(c.limite, 3)}",
                 c.valor if c.valor != "" else None, "", c.estado, c.referencia, nd=3)
    mem.paso("RESULTADO GLOBAL DEL PAÑO", "", "", res.resultado, "", res.resultado)


def _generales(piso: Piso, sec_mem: Memoria) -> tuple[Seccion, float, list[Verificacion]]:
    mat, losa = piso.materiales, piso.losa
    sec_mem.seccion("MATERIALES")
    sec_mem.dato("Resistencia del hormigón f'c", mat.fc, "kg/cm²")
    sec_mem.dato("Fluencia del acero fy", mat.fy, "kg/cm²")
    sec_mem.dato("Peso específico del hormigón", mat.peso_hormigon, "kg/m³")
    sec_mem.dato("Recubrimiento al borde de la varilla", mat.recubrimiento, "cm")
    sec_mem.paso("Módulo de elasticidad del hormigón",
                 "Ec = 15000·√f'c" if not mat.Ec else "Dato", "", mat.E, "kg/cm²",
                 referencia="Hoja de referencia")
    sec_mem.dato("Módulo de elasticidad del acero Es", mat.Es, "kg/cm²")
    sec_mem.paso("β1 del bloque de compresión", "0,85 − 0,05·(f'c − 280)/70, entre 0,65 y 0,85",
                 "", mat.beta1, "", referencia="ACI 318-19, 22.2.2.4.3", nd=3)
    sec = propiedades(losa, sec_mem)
    sec_mem.seccion("PESO PROPIO")
    pp = peso_propio(losa, mat, sec_mem)
    checks = limites_nervios(losa, sec_mem)
    retraccion_temperatura(losa, mat, sec_mem)
    return sec, pp, checks


def disenar_piso(piso: Piso) -> ResultadoPiso:
    """Diseña todas las losas del piso y devuelve los resultados con su memoria."""
    piso.avisos.clear()
    geometria.preparar(piso)
    general = Memoria()
    sec, pp, generales = _generales(piso, general)
    resultados = {p.id: ResultadoPano(p) for p in piso.panos}
    for p in piso.panos:
        analisis.analizar(piso, p, sec, pp, resultados[p.id])
    for p in piso.panos:
        res = resultados[p.id]
        if res.calculado:
            res.volados = [volado.analizar(piso, p, v, pp, res.memoria) for v in p.volados]
        elif p.volados:
            res.avisos.append("Los volados de este paño no se calcularon porque el paño está "
                              "fuera de alcance.")
    comunes = compatibilidad.aplicar(piso, resultados)
    for p in piso.panos:
        if resultados[p.id].calculado:
            _dimensionar(piso, p, resultados[p.id], sec, generales)
    for c in comunes:
        ra, rb = resultados[c.pano_a], resultados[c.pano_b]
        dis = [r.flexion[f"neg_{b}"] for r, b in ((ra, c.borde_a), (rb, c.borde_b))
               if r.calculado and f"neg_{b}" in r.flexion]
        c.armado = max(dis, key=lambda x: x.As_col).armado if dis else "-"
    avisos = list(dict.fromkeys(piso.avisos))
    for r in resultados.values():
        avisos += [f"Paño {r.pano.id}: {a}" for a in dict.fromkeys(r.avisos)]
        if not r.calculado:
            avisos += [f"Paño {r.pano.id} FUERA DE ALCANCE: {m} Se requiere un modelo de "
                       "elementos finitos." for m in r.motivos]
    return ResultadoPiso(piso, sec, resultados, comunes, general, generales, avisos)
