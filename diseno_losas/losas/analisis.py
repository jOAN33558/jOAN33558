"""Análisis de cada paño: alcance, clasificación, cargas y momentos propios."""
from __future__ import annotations

from . import tablas, unidireccional
from .cargas import cargas_pano, pano_cargas
from .geometria import deducir_tipo, orientar
from .memoria import fmt
from .modelos import BORDES, FUERA_DE_ALCANCE, MENSAJE_MEF, Pano, Piso, ResultadoPano
from .seccion import Seccion
from .verificaciones import ALFA_MIN_TABLAS, alfa_borde, ancho_viga

EJES_DIR = {"X": ("oeste", "este"), "Y": ("sur", "norte")}
SIMBOLO = {"delta": "δ", "my_neg": "my−", "my_pos": "my+", "mx_neg": "mx−", "mx_pos": "mx+",
           "myb_neg": "myb−", "myb_pos": "myb+", "mxb_neg": "mxb−", "mxb_pos": "mxb+"}


def _datos(piso: Piso, p: Pano, res: ResultadoPano) -> None:
    mem = res.memoria
    mem.seccion("1. DATOS DEL PAÑO")
    mem.dato(f"Luz en X (ejes {p.ejes_x[0]}-{p.ejes_x[1]}), centro a centro", p.ancho_x, "m")
    mem.dato(f"Luz en Y (ejes {p.ejes_y[0]}-{p.ejes_y[1]}), centro a centro", p.ancho_y, "m")
    for b in BORDES:
        viga = piso.viga_en(p.eje_de(b))
        vecinos = ", ".join(q for q, _ in p.vecinos[b]) or "ninguno"
        extra = "; con volado" if p.volado_en(b) else ""
        txt_viga = f"viga {fmt(viga.b, 0)}x{fmt(viga.h, 0)} cm" if viga else "sin viga"
        mem.paso(f"Borde {b} (eje {p.eje_de(b)})", "", f"vecino: {vecinos}{extra}; {txt_viga}",
                 p.cond[b].upper(), "",
                 "declarado" if p.bordes.get(b, "auto") != "auto" else "deducido")


def _clasificar(piso: Piso, p: Pano, res: ResultadoPano) -> list[str]:
    """Fija orientación, clasificación y tipo. Devuelve los motivos de exclusión."""
    motivos = list(p.fuera_de_alcance)
    Lx, Ly, dir_c, largos, cortos = orientar(p)
    libres = [b for b in BORDES if p.cond[b] == "libre"]
    for b in BORDES:
        v = piso.viga_en(p.eje_de(b))
        if p.cond[b] != "libre" and (v is None or v.b <= 0 or v.h <= 0):
            motivos.append(f"El borde {b} (eje {p.eje_de(b)}) no tiene viga: losa plana sin "
                           "vigas (requiere revisión de punzonamiento).")
    res.Lx, res.Ly, res.dir_corta, res.largos, res.cortos = Lx, Ly, dir_c, largos, cortos
    res.beta = Lx / Ly
    cl, cc = [p.cond[b] for b in largos], [p.cond[b] for b in cortos]
    if len(libres) >= 3:
        motivos.append("El paño tiene tres o más bordes libres: es un voladizo, no un paño "
                       "sustentado perimetralmente.")
    elif cl == ["libre", "libre"]:
        # apoyado solo en los bordes cortos: trabaja en la dirección larga
        res.Lx, res.Ly = Ly, Lx
        res.dir_corta = "Y" if dir_c == "X" else "X"
        res.largos, res.cortos = cortos, largos
        res.clasificacion = "Unidireccional"
        res.metodo = "apoyado en dos bordes opuestos"
    elif cc == ["libre", "libre"]:
        res.clasificacion = "Unidireccional"
        res.metodo = "apoyado en dos bordes opuestos"
    elif res.beta < 0.5:
        if "libre" in cl:
            motivos.append("Lx/Ly < 0,5 con un borde largo libre: la franja corta trabaja como "
                           "volado y no está cubierta; modele ese borde como volado de un paño "
                           "vecino o use un modelo general.")
        res.clasificacion = "Unidireccional"
    else:
        res.clasificacion = "Bidireccional"
        res.tipo = deducir_tipo(tuple(cl), tuple(cc))
        if res.tipo is None:
            motivos.append("La combinación de bordes (largos: " + ", ".join(cl) + "; cortos: "
                           + ", ".join(cc) + ") no está en las tablas de coeficientes.")
    return motivos


def _bidireccional(piso: Piso, p: Pano, res: ResultadoPano, sec: Seccion) -> None:
    mem, q, Lx = res.memoria, res.cargas.qu, res.Lx
    tabla = piso.losa.tipo
    c = tablas.coeficientes(tabla, res.tipo, res.beta)
    res.coef = c
    k = 0.0001 * q * Lx**2
    mem.seccion("4. MOMENTOS (losa en dos direcciones)")
    mem.paso("Coeficientes interpolados en Lx/Ly", tablas.NOMBRE_TABLA[tabla],
             f"paño tipo {res.tipo}, Lx/Ly = {fmt(res.beta, 3)}",
             "; ".join(f"{SIMBOLO[n]} = {fmt(v, 1)}" for n, v in c.items() if v), "")
    nombres = {"my_neg": "My(−)", "myb_neg": "Myb(−) borde libre", "my_pos": "My(+)",
               "myb_pos": "Myb(+) borde libre", "mx_neg": "Mx(−)",
               "mxb_neg": "Mxb(−) borde libre", "mx_pos": "Mx(+)", "mxb_pos": "Mxb(+) borde libre"}
    M = {}
    for clave, nombre in nombres.items():
        M[clave] = k * c[clave]
        if c[clave]:
            mem.paso(nombre, "M = 0,0001·qu·m·Lx²",
                     f"0,0001·{fmt(q)}·{fmt(c[clave], 1)}·{fmt(Lx)}²", M[clave], "kg·m/m",
                     referencia=tablas.NOMBRE_TABLA[tabla])
    neg_c, neg_l = max(M["my_neg"], M["myb_neg"]), max(M["mx_neg"], M["mxb_neg"])
    res.M_pos = {"corta": max(M["my_pos"], M["myb_pos"]), "larga": max(M["mx_pos"], M["mxb_pos"])}
    for b in BORDES:
        if p.cond[b] == "continuo":
            res.M_borde[b] = neg_c if b in res.largos else neg_l
        else:
            res.M_borde[b] = 0.0
    mem.nota(f"Dirección corta = {res.dir_corta} global. My actúa en la dirección corta (acero "
             f"paralelo a {res.dir_corta}); Mx en la larga. Se toma la envolvente con los "
             "momentos de borde libre.")
    mem.paso("Momento positivo, dirección corta", "máx(My+ ; Myb+)", "", res.M_pos["corta"], "kg·m/m")
    mem.paso("Momento positivo, dirección larga", "máx(Mx+ ; Mxb+)", "", res.M_pos["larga"], "kg·m/m")
    mem.paso(f"Momento negativo en bordes continuos largos ({', '.join(res.largos)})",
             "máx(My− ; Myb−)", "", neg_c, "kg·m/m")
    mem.paso(f"Momento negativo en bordes continuos cortos ({', '.join(res.cortos)})",
             "máx(Mx− ; Mxb−)", "", neg_l, "kg·m/m")
    # Cortante en la cara de la viga (franja corta), como la hoja de referencia
    bv = min((ancho_viga(piso, p, b) for b in res.largos if p.cond[b] != "libre"), default=0.0)
    un_apoyo = any(p.cond[b] == "libre" for b in res.largos)
    res.V_cara = {"general": q * ((Lx if un_apoyo else Lx / 2) - bv / 200)}
    res.servicio = {"bv": bv, "un_apoyo": un_apoyo,
                    "m_pos": max(c["my_pos"], c["myb_pos"]), "m_neg": max(c["my_neg"], c["myb_neg"])}


def construir_franja(piso: Piso, p: Pano, direccion: str, pp: float):
    """Cadena de paños continuos en la dirección de trabajo. Devuelve (franja, índice)."""
    ini, fin = EJES_DIR[direccion]
    cadena = [p]
    for borde, al_inicio in ((ini, True), (fin, False)):
        actual = p
        while actual.cond[borde] == "continuo" and actual.vecinos[borde]:
            q = piso.pano(max(actual.vecinos[borde], key=lambda t: t[1])[0])
            if q in cadena:
                break
            cadena.insert(0, q) if al_inicio else cadena.append(q)
            actual = q
    cargas = [cargas_pano(piso, q.cargas, pp) for q in cadena]

    def voladizo(q: Pano, borde: str):
        v = q.volado_en(borde)
        if not v:
            return None
        c = cargas_pano(piso, {**q.cargas, **v.cargas}, pp)
        L_eje = v.longitud if v.medida == "eje" else v.longitud + ancho_viga(piso, q, borde) / 200
        return unidireccional.Voladizo(L_eje, c.D, c.L, v.carga_borde, v.carga_borde_viva)

    fr = unidireccional.Franja(
        ids=[q.id for q in cadena], luces=[q.luz_perpendicular(ini) for q in cadena],
        D=[c.D for c in cargas], L=[c.L for c in cargas],
        bv=[ancho_viga(piso, cadena[0], ini)] + [ancho_viga(piso, q, fin) for q in cadena],
        vol_izq=voladizo(cadena[0], ini), vol_der=voladizo(cadena[-1], fin))
    return fr, cadena.index(p)


def _unidireccional(piso: Piso, p: Pano, res: ResultadoPano, pp: float) -> None:
    mem = res.memoria
    fr, i = construir_franja(piso, p, res.dir_corta, pp)
    r = unidireccional.analizar(fr, piso.cargas.fraccion_viva_sostenida)
    ini, fin = EJES_DIR[res.dir_corta]
    res.metodo = r.metodo
    res.M_pos = {"corta": r.M_pos[i], "larga": 0.0}
    res.M_borde = {b: 0.0 for b in BORDES}
    res.M_borde[ini], res.M_borde[fin] = r.M_apoyo[i], r.M_apoyo[i + 1]
    res.V_cara = {ini: r.V_izq[i], fin: r.V_der[i]}
    res.servicio = {"niveles": r.servicio[i], "wu": r.wu[i]}
    mem.seccion("4. MOMENTOS (losa en una dirección, franja de 1 m)")
    mem.paso("Franja continua en la dirección " + res.dir_corta, "",
             " | ".join(f"{q}: L = {fmt(L)} m" for q, L in zip(fr.ids, fr.luces)),
             f"{fr.n} vano(s)" + ("; con volado" if fr.vol_izq or fr.vol_der else ""), "")
    if r.razones:
        mem.paso("Método de análisis", r.metodo, "No aplica ACI 6.5: " + "; ".join(r.razones),
                 "Rigidez", "", referencia="Apoyos articulados en los ejes de las vigas; "
                 "carga viva alternada (ACI 318-19, 6.4.2)")
    else:
        mem.paso("Método de análisis", r.metodo, "Se cumplen las condiciones de 6.5.1 (dos o "
                 "más vanos, luces adyacentes que difieren <= 20 %, L <= 3D, cargas uniformes)",
                 "Coeficientes", "", referencia="Apoyo exterior monolítico con viga de borde; "
                 "no se usa la reducción a wu·ln²/12 para luces <= 3 m")
    mem.paso("Luz libre del vano", "ln = L − anchos de viga/2", "", fr.ln[i], "m")
    mem.paso("Carga última del vano", "wu", "", r.wu[i], "kg/m por metro")
    mem.paso("Momento positivo en el vano", "Mu(+)", "", r.M_pos[i], "kg·m/m",
             referencia="Envolvente de la franja")
    mem.paso(f"Momento negativo en el apoyo {ini} (eje {p.eje_de(ini)})", "Mu(−)", "",
             r.M_apoyo[i], "kg·m/m", referencia="Envolvente de la franja")
    mem.paso(f"Momento negativo en el apoyo {fin} (eje {p.eje_de(fin)})", "Mu(−)", "",
             r.M_apoyo[i + 1], "kg·m/m", referencia="Envolvente de la franja")
    mem.paso(f"Cortante en la cara del apoyo {ini}", "Vu", "", r.V_izq[i], "kg/m")
    mem.paso(f"Cortante en la cara del apoyo {fin}", "Vu", "", r.V_der[i], "kg/m")
    if len(fr.ids) > 1:
        mem.nota("Hipótesis: los paños vecinos de la franja se cargan con toda su carga en "
                 "esta dirección, aunque trabajen en dos direcciones.")


def analizar(piso: Piso, p: Pano, sec: Seccion, pp: float, res: ResultadoPano) -> None:
    mem = res.memoria
    _datos(piso, p, res)
    motivos = _clasificar(piso, p, res)
    alfas = {b: alfa_borde(piso, p, b, sec) for b in BORDES}
    res.coef = {}
    if res.clasificacion == "Bidireccional" and not motivos:
        am = sum(alfas.values()) / 4
        if am < ALFA_MIN_TABLAS:
            motivos.append(f"Vigas muy flexibles (αm = {fmt(am, 2)} < 0,2): la losa se comporta "
                           "como losa plana y las tablas de coeficientes no aplican "
                           "(ACI 318-19, 8.3.1.1).")
    mem.seccion("2. CLASIFICACIÓN")
    mem.paso("Luz corta", "Lx", "", res.Lx, "m")
    mem.paso("Luz larga", "Ly", "", res.Ly, "m")
    mem.paso("Relación de luces", "Lx/Ly", f"{fmt(res.Lx)}/{fmt(res.Ly)}", res.beta, "",
             res.metodo or ("Lx/Ly >= 0,5: dos direcciones" if res.beta >= 0.5
                            else "Lx/Ly < 0,5: una dirección"), nd=3)
    if motivos:
        res.estado, res.motivos = FUERA_DE_ALCANCE, motivos
        mem.paso("Resultado", "", "", FUERA_DE_ALCANCE, "", "NO CALCULADO")
        for m in motivos:
            mem.nota("Motivo: " + m)
        mem.nota(MENSAJE_MEF + " Este paño no se calculó.")
        return
    if res.clasificacion == "Bidireccional":
        mem.paso("Clasificación", "", f"bordes largos ({', '.join(res.largos)}): "
                 + ", ".join(p.cond[b] for b in res.largos) + f"; bordes cortos "
                 f"({', '.join(res.cortos)}): " + ", ".join(p.cond[b] for b in res.cortos),
                 f"Bidireccional, tipo {res.tipo}", "",
                 referencia=tablas.NOMBRE_TABLA[piso.losa.tipo])
    else:
        mem.paso("Clasificación", "", "", f"Unidireccional en dirección {res.dir_corta}", "",
                 "Lx/Ly < 0,5" if res.beta < 0.5 else "apoyada en dos bordes opuestos")
    res.cargas = pano_cargas(piso, p, pp, mem)
    if res.clasificacion == "Bidireccional":
        _bidireccional(piso, p, res, sec)
    else:
        _unidireccional(piso, p, res, pp)
    res.servicio["alfas"] = alfas
