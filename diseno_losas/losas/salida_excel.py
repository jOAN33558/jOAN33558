"""Memoria en Excel: hoja RESUMEN, hoja DATOS y una hoja de memoria por paño."""
from __future__ import annotations

import re
from pathlib import Path

from openpyxl import Workbook
from openpyxl.drawing.image import Image as ImagenExcel
from openpyxl.styles import Alignment, Border, Font, PatternFill, Side
from openpyxl.utils import get_column_letter

from . import tablas
from .memoria import Memoria
from .modelos import BORDES, MENSAJE_MEF, ResultadoPano, ResultadoPiso

FUENTE = "Arial"
BASE = Font(name=FUENTE, size=10)
NEGRITA = Font(name=FUENTE, size=10, bold=True)
TITULO = Font(name=FUENTE, size=14, bold=True)
BLANCA = Font(name=FUENTE, size=10, bold=True, color="FFFFFF")
CURSIVA = Font(name=FUENTE, size=10, italic=True)
AZUL = PatternFill("solid", fgColor="1F3864")
CELESTE = PatternFill("solid", fgColor="D9E1F2")
GRIS = PatternFill("solid", fgColor="F2F2F2")
ESTADOS = {
    "CUMPLE": (PatternFill("solid", fgColor="C6EFCE"), "006100"),
    "NO": (PatternFill("solid", fgColor="FFC7CE"), "9C0006"),
    "AVISO": (PatternFill("solid", fgColor="FFEB9C"), "7F6000"),
}
LINEA = Side(style="thin", color="A6A6A6")
BORDE = Border(left=LINEA, right=LINEA, top=LINEA, bottom=LINEA)
AJUSTE = Alignment(wrap_text=True, vertical="top")
CENTRO = Alignment(horizontal="center", vertical="center", wrap_text=True)
LIBRE = Alignment(vertical="center", wrap_text=False)
FORMATOS = {0: "0", 1: "0.0", 2: "0.00", 3: "0.000", 4: "0.0000"}
ANCHO_FIGURA = 1640      # px, ancho de las láminas dentro de las hojas de memoria


def _estilo_estado(celda, texto: str) -> None:
    t = str(texto).upper()
    if t.startswith("NO CUMPLE") or t.startswith("NO CALCULADO"):
        clave = "NO"
    elif t.startswith("CUMPLE CON") or t.startswith("FUERA"):
        clave = "AVISO"
    elif t.startswith("CUMPLE"):
        clave = "CUMPLE"
    else:
        return
    relleno, color = ESTADOS[clave]
    celda.fill = relleno
    celda.font = Font(name=FUENTE, size=10, bold=True, color=color)


def _celda(ws, fila, col, valor, fuente=BASE, relleno=None, alineacion=AJUSTE, borde=True, nd=None):
    c = ws.cell(row=fila, column=col, value=valor)
    c.font, c.alignment = fuente, alineacion
    if relleno:
        c.fill = relleno
    if borde:
        c.border = BORDE
    if isinstance(valor, float) and nd is not None:
        c.number_format = FORMATOS.get(nd, "0.00")
    return c


def _anchos(ws, anchos: list[float]) -> None:
    for i, a in enumerate(anchos, start=1):
        ws.column_dimensions[get_column_letter(i)].width = a


def _banda(ws, fila: int, texto: str, ncol: int, fuente=BLANCA, relleno=AZUL) -> None:
    ws.merge_cells(start_row=fila, start_column=1, end_row=fila, end_column=ncol)
    c = ws.cell(row=fila, column=1, value=texto)
    c.font, c.fill = fuente, relleno
    c.alignment = Alignment(vertical="center", wrap_text=True)


def _pagina(ws, horizontal=True) -> None:
    ws.page_setup.orientation = "landscape" if horizontal else "portrait"
    ws.page_setup.paperSize = ws.PAPERSIZE_A4
    ws.page_setup.fitToWidth, ws.page_setup.fitToHeight = 1, 0
    ws.sheet_properties.pageSetUpPr.fitToPage = True
    ws.sheet_view.showGridLines = False


def _imagen(ws, ruta, fila: int, ancho_px: int) -> int:
    """Inserta una imagen en la columna A y devuelve la primera fila libre debajo."""
    img = ImagenExcel(str(ruta))
    escala = min(1.0, ancho_px / img.width)
    img.width, img.height = int(img.width * escala), int(img.height * escala)
    ws.add_image(img, f"A{fila}")
    return fila + int(img.height / 20) + 2          # filas de 15 puntos = 20 px


# ---------------------------------------------------------------- memoria
COLUMNAS = ["Concepto", "Fórmula", "Sustitución", "Resultado", "Unidad", "Verificación",
            "Referencia"]


def _altura(textos: list, anchos: list[float]) -> float:
    lineas = max((len(str(t)) / max(a * 1.05, 1)) for t, a in zip(textos, anchos) if t not in (None, ""))
    return 14.0 * max(1, int(lineas) + 1)


def _escribir_memoria(ws, mem: Memoria, fila: int, congelar: bool = True) -> int:
    anchos = [48, 42, 50, 24, 10, 34, 36]
    _anchos(ws, anchos)
    for j, t in enumerate(COLUMNAS, start=1):
        _celda(ws, fila, j, t, NEGRITA, CELESTE, CENTRO)
    if congelar:
        ws.freeze_panes = ws.cell(row=fila + 1, column=1)
    fila += 1
    for p in mem.pasos:
        if p.clase == "seccion":
            _banda(ws, fila, p.concepto, 7)
            ws.row_dimensions[fila].height = 18
        elif p.clase == "nota":
            _banda(ws, fila, p.concepto, 7, CURSIVA, GRIS)
            ws.row_dimensions[fila].height = 14.0 * max(1, int(len(p.concepto) / 215) + 1)
        else:
            res = p.resultado
            valores = [p.concepto, p.formula, p.sustitucion, res, p.unidad, p.verificacion,
                       p.referencia]
            largo = (isinstance(res, str) and len(res) > 26
                     and not (p.unidad or p.verificacion or p.referencia))
            for j, v in enumerate(valores, start=1):
                c = _celda(ws, fila, j, v, nd=p.nd if j == 4 else None)
                if j == 4:
                    c.font = NEGRITA
                    c.alignment = Alignment(horizontal="right", vertical="top", wrap_text=True)
                    if isinstance(v, str):
                        _estilo_estado(c, v)
                if j == 6:
                    _estilo_estado(c, v)
            if largo:
                ws.merge_cells(start_row=fila, start_column=4, end_row=fila, end_column=7)
                ws.cell(row=fila, column=4).alignment = AJUSTE
            ws.row_dimensions[fila].height = _altura(
                [str(v) if not isinstance(v, float) else "0" for v in valores],
                anchos[:3] + [sum(anchos[3:])] + anchos[4:] if largo else anchos)
        fila += 1
    return fila


def _hoja_pano(wb: Workbook, rp: ResultadoPiso, r: ResultadoPano, nombre: str,
               figura=None) -> None:
    ws = wb.create_sheet(nombre)
    p = r.pano
    _celda(ws, 1, 1, f"MEMORIA DE CÁLCULO - PAÑO {p.id}", TITULO, alineacion=LIBRE, borde=False)
    proyecto = rp.piso.proyecto
    _celda(ws, 2, 1, f"{proyecto.get('nombre', '')}   {proyecto.get('piso', '')}".strip(),
           BASE, alineacion=LIBRE, borde=False)
    _celda(ws, 3, 1, f"Ejes {p.ejes_x[0]}-{p.ejes_x[1]} / {p.ejes_y[0]}-{p.ejes_y[1]}.  "
           f"Losa {rp.piso.losa.tipo}, h = {rp.piso.losa.altura:g} cm.  Unidades: kg, cm, m.",
           BASE, alineacion=LIBRE, borde=False)
    c = _celda(ws, 4, 1, "RESULTADO: " + r.resultado, NEGRITA, alineacion=LIBRE)
    _estilo_estado(c, r.resultado)
    if not r.calculado:
        _celda(ws, 4, 2, MENSAJE_MEF, NEGRITA, alineacion=LIBRE, borde=False)
    fila = 6
    if figura:
        fila = _imagen(ws, figura, 6, ANCHO_FIGURA)
    _escribir_memoria(ws, r.memoria, fila, congelar=not figura)
    _pagina(ws)


# ---------------------------------------------------------------- resumen
def _armado(r: ResultadoPano, clave: str) -> str:
    x = r.flexion.get(clave)
    if x is None:
        return "-"
    return x.armado + (" (mín.)" if x.constructivo else "")


def _inferior(r: ResultadoPano, direccion: str) -> str:
    return _armado(r, "pos_corta" if r.dir_corta == direccion else "pos_larga")


def _estado_de(r: ResultadoPano, prefijo: str) -> str:
    cs = [c for c in r.checks if c.nombre.startswith(prefijo)]
    if not cs:
        return "-"
    malos = [c for c in cs if not c.cumple]
    return malos[0].estado if malos else max((c.estado for c in cs), key=len)


def _observaciones(r: ResultadoPano) -> str:
    if not r.calculado:
        return " ".join(r.motivos) + " " + MENSAJE_MEF
    obs = ["No cumple: " + c.nombre for c in r.checks if not c.cumple]
    if r.cortante and r.cortante.estado == "CUMPLE con macizado":
        obs.append("Macizar junto a las vigas.")
    obs += list(dict.fromkeys(r.avisos))
    return " | ".join(obs)


def _tabla(ws, fila: int, titulo: str, encabezados: list[str], filas: list[list],
           estados: tuple[int, ...] = (), tramos: list[int] | None = None) -> int:
    """Escribe una tabla. ``tramos`` indica cuántas columnas de la hoja ocupa cada columna
    de la tabla (celdas combinadas), para tablas más angostas que la principal."""
    tramos = tramos or [1] * len(encabezados)
    inicio = [1 + sum(tramos[:j]) for j in range(len(tramos))]

    def poner(j, valor, **kw):
        if tramos[j] > 1:
            for k in range(inicio[j], inicio[j] + tramos[j]):
                ws.cell(row=fila, column=k).border = BORDE
            ws.merge_cells(start_row=fila, start_column=inicio[j], end_row=fila,
                           end_column=inicio[j] + tramos[j] - 1)
        return _celda(ws, fila, inicio[j], valor, **kw)

    _banda(ws, fila, titulo, sum(tramos))
    fila += 1
    for j, t in enumerate(encabezados):
        poner(j, t, fuente=NEGRITA, relleno=CELESTE, alineacion=CENTRO)
    ws.row_dimensions[fila].height = 30
    fila += 1
    for datos in filas:
        ultimo = len(datos) - 1
        for j, v in enumerate(datos):
            c = poner(j, v, alineacion=AJUSTE if j == ultimo and tramos[j] == 1 and
                      len(encabezados) > 10 else CENTRO, nd=2 if isinstance(v, float) else None)
            if j in estados:
                _estilo_estado(c, v)
        largo = len(str(datos[ultimo])) if len(encabezados) > 10 else 0
        ws.row_dimensions[fila].height = 15.0 * max(1, int(largo / 55) + 1)
        fila += 1
    return fila + 1


def _hoja_resumen(wb: Workbook, rp: ResultadoPiso, figura=None) -> None:
    ws = wb.active
    ws.title = "RESUMEN"
    piso, losa, mat = rp.piso, rp.piso.losa, rp.piso.materiales
    _celda(ws, 1, 1, "DISEÑO DE LOSAS DE PISO - RESUMEN", TITULO, alineacion=LIBRE, borde=False)
    pr = piso.proyecto
    _celda(ws, 2, 1, "  |  ".join(str(pr[k]) for k in ("nombre", "piso", "autor", "fecha") if pr.get(k)),
           BASE, alineacion=LIBRE, borde=False)
    geo = (f"Losa nervada h = {losa.altura:g} cm, loseta {losa.loseta:g} cm, nervios "
           f"{losa.ancho_nervio:g} cm cada {losa.separacion_nervios:g} cm"
           if losa.nervada else f"Losa maciza h = {losa.altura:g} cm")
    _celda(ws, 3, 1, f"{geo}.  f'c = {mat.fc:g} kg/cm², fy = {mat.fy:g} kg/cm².  Normas: "
           "NEC-SE-HM, NEC-SE-CG, ACI 318-19.  Unidades: kg, cm, m.", BASE, alineacion=LIBRE,
           borde=False)
    ws.merge_cells(start_row=4, start_column=1, end_row=4, end_column=9)
    c = _celda(ws, 4, 1, "RESULTADO DEL PISO: " + rp.resultado, NEGRITA, alineacion=LIBRE)
    _estilo_estado(c, "FUERA" if rp.resultado.startswith("INCOMPLETO") else rp.resultado)
    unidad = "por nervio" if losa.nervada else "por metro"
    enc = ["Paño", "Ejes", "Lx (m)", "Ly (m)", "Lx/Ly", "Clasificación", "qu (kg/m²)",
           f"Inferior X ({unidad})", f"Inferior Y ({unidad})", "Superior borde norte",
           "Superior borde sur", "Superior borde este", "Superior borde oeste", "Flexión",
           "Cortante", "Flechas", "Altura mínima", "RESULTADO", "Observaciones"]
    filas = []
    for r in rp.panos.values():
        p = r.pano
        ejes = f"{p.ejes_x[0]}-{p.ejes_x[1]} / {p.ejes_y[0]}-{p.ejes_y[1]}"
        if not r.calculado:
            filas.append([p.id, ejes, r.Lx, r.Ly, r.beta, "No calculado"] + ["-"] * 11
                         + [r.resultado, _observaciones(r)])
            continue
        clasif = (f"Bidireccional, tipo {r.tipo}" if r.tipo else f"Unidireccional ({r.dir_corta})")
        filas.append([p.id, ejes, r.Lx, r.Ly, r.beta, clasif, r.cargas.qu,
                      _inferior(r, "X"), _inferior(r, "Y")]
                     + [_armado(r, f"neg_{b}") for b in BORDES]
                     + [_estado_de(r, "Flexión"), _estado_de(r, "Cortante"),
                        _estado_de(r, "Flecha"), _estado_de(r, "Altura"), r.resultado,
                        _observaciones(r)])
    fila = _tabla(ws, 6, "PAÑOS: ARMADO Y VERIFICACIONES", enc, filas, (13, 14, 15, 16, 17))
    if rp.checks_generales:
        fila = _tabla(ws, fila, "VERIFICACIONES GENERALES DE LA LOSA",
                      ["Verificación", "Valor", "Límite", "Estado", "Referencia"],
                      [[c.nombre, c.valor, c.limite, c.estado, c.referencia]
                       for c in rp.checks_generales], (3,), [6, 1, 1, 2, 3])
    if rp.bordes_comunes:
        fila = _tabla(ws, fila, "BORDES COMUNES: COMPATIBILIDAD DE MOMENTOS NEGATIVOS",
                      ["Eje", "Paño A", "M(−) A (kg·m/m)", "Paño B", "M(−) B (kg·m/m)",
                       "M(−) diseño (kg·m/m)", f"Acero superior ({unidad})"],
                      [[c.eje, c.pano_a, c.M_a, c.pano_b, c.M_b, c.M_dis, c.armado]
                       for c in rp.bordes_comunes], (), [1, 1, 3, 1, 2, 2, 2])
    vol = [(r, v) for r in rp.panos.values() for v in r.volados]
    if vol:
        fila = _tabla(ws, fila, "VOLADOS",
                      ["Paño", "Borde", "L diseño (m)", "Mu (kg·m/m)", "Vu (kg/m)",
                       f"Acero superior ({unidad})", "Prolongación en el paño (m)",
                       "Flecha diferida (cm)", "Estado"],
                      [[r.pano.id, v.volado.borde, v.L, v.Mu, v.Vu,
                        _armado(r, f"neg_{v.volado.borde}"), v.prolongacion,
                        v.flechas.delta_lp if v.flechas else "-",
                        "CUMPLE" if all(c.cumple for c in v.checks) else "NO CUMPLE"]
                       for r, v in vol], (8,), [1, 1, 2, 2, 2, 2, 2, 2, 2])
    _banda(ws, fila, "AVISOS", len(enc))
    fila += 1
    for a in rp.avisos or ["Sin avisos."]:
        ws.merge_cells(start_row=fila, start_column=1, end_row=fila, end_column=len(enc))
        _celda(ws, fila, 1, a, borde=False)
        ws.row_dimensions[fila].height = 14.0 * max(1, int(len(a) / 190) + 1)
        fila += 1
    if figura:
        fila += 1
        _banda(ws, fila, "MAPA DE APROVECHAMIENTO (demanda / capacidad)", len(enc))
        _imagen(ws, figura, fila + 2, 900)
    _anchos(ws, [9, 13, 8, 8, 8, 22, 11, 14, 14, 14, 14, 14, 14, 12, 13, 12, 12, 16, 60])
    ws.freeze_panes = "B8"
    _pagina(ws)


def _hoja_tabla(wb: Workbook, tabla: str) -> None:
    ws = wb.create_sheet("TABLA")
    _celda(ws, 1, 1, "COEFICIENTES USADOS: " + tablas.NOMBRE_TABLA[tabla], TITULO,
           alineacion=LIBRE, borde=False)
    _celda(ws, 2, 1, "M = 0,0001·q·m·Lx²;  Δ = 0,0001·q·δ·Lx⁴/(E·h³).  Interpolación lineal en "
           "Lx/Ly." + ("  Paño 14, mx+ con Lx/Ly = 0,5: impreso 8187, se usa 916."
                       if tabla == "nervada" else ""), BASE, alineacion=LIBRE, borde=False)
    enc = ["Tipo", "Lx/Ly", "δ", "my(−)", "my(+)", "mx(−)", "mx(+)", "myb(−)", "myb(+)",
           "mxb(−)", "mxb(+)"]
    for j, t in enumerate(enc, start=1):
        _celda(ws, 4, j, t, NEGRITA, CELESTE, CENTRO)
    fila = 5
    for tipo, filas in tablas.cargar(tabla).items():
        for f in sorted(filas, key=lambda x: -x["beta"]):
            _celda(ws, fila, 1, tipo, alineacion=CENTRO)
            _celda(ws, fila, 2, f["beta"], alineacion=CENTRO, nd=1)
            for j, k in enumerate(tablas.COEFICIENTES, start=3):
                _celda(ws, fila, j, f[k], alineacion=CENTRO, nd=0)
            fila += 1
    _anchos(ws, [8] + [10] * 10)
    ws.freeze_panes = "A5"
    _pagina(ws, horizontal=False)


def nombre_hoja(id_: str, usados: set[str]) -> str:
    base = re.sub(r"[\[\]\*\?/\\:]", "_", str(id_))[:28] or "Paño"
    if base.upper() in ("RESUMEN", "DATOS", "TABLA", "PLANO"):
        base = "Paño " + base
    nombre, i = base, 2
    while nombre.upper() in usados:
        nombre, i = f"{base}_{i}", i + 1
    usados.add(nombre.upper())
    return nombre


def escribir(rp: ResultadoPiso, ruta: str | Path, ruta_plano: str | Path | None = None,
             figuras: dict | None = None) -> Path:
    """Escribe la memoria. ``figuras`` es el diccionario que devuelve ``figuras.generar``
    (láminas por paño, 'general' y 'aprovechamiento'); si no se da, la memoria va sin ellas."""
    ruta = Path(ruta)
    figuras = {k: v for k, v in (figuras or {}).items() if Path(v).exists()}
    wb = Workbook()
    _hoja_resumen(wb, rp, figuras.get("aprovechamiento"))
    ws = wb.create_sheet("DATOS")
    _celda(ws, 1, 1, "DATOS GENERALES, SECCIÓN Y CARGAS DE LA LOSA", TITULO, alineacion=LIBRE,
           borde=False)
    fila = 3
    if "general" in figuras:
        fila = _imagen(ws, figuras["general"], 3, ANCHO_FIGURA)
    _escribir_memoria(ws, rp.memoria_general, fila, congelar="general" not in figuras)
    _pagina(ws)
    usados = {"RESUMEN", "DATOS", "TABLA", "PLANO"}
    for id_, r in rp.panos.items():
        _hoja_pano(wb, rp, r, nombre_hoja(r.pano.id, usados), figuras.get(id_))
    _hoja_tabla(wb, rp.piso.losa.tipo)
    if ruta_plano and Path(ruta_plano).exists():
        ws = wb.create_sheet("PLANO")
        _celda(ws, 1, 1, "PLANO ESQUEMÁTICO DE LOSAS", TITULO, alineacion=LIBRE, borde=False)
        _imagen(ws, ruta_plano, 3, 1100)
        ws.sheet_view.showGridLines = False
    ruta.parent.mkdir(parents=True, exist_ok=True)
    wb.save(ruta)
    return ruta
