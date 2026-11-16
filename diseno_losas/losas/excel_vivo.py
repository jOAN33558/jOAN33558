"""Excel con fórmulas vivas y gráficos nativos (losa nervada en dos direcciones).

A diferencia de ``salida_excel`` (valores fijos e imágenes), este libro calcula con
fórmulas de Excel: al cambiar un dato amarillo se recalculan los momentos, el armado,
las verificaciones y los gráficos. Cubre pisos de paños en cuadrícula completa con
losa nervada en dos direcciones (Tabla 9.7).
"""
from __future__ import annotations

from math import pi
from pathlib import Path

from openpyxl import Workbook
from openpyxl.chart import BarChart, LineChart, Reference, ScatterChart, Series
from openpyxl.chart.series import SeriesLabel, StrRef
from openpyxl.formatting.rule import FormulaRule
from openpyxl.styles import Alignment, Border, Font, PatternFill, Side
from openpyxl.utils import get_column_letter
from openpyxl.worksheet.datavalidation import DataValidation

from . import geometria, tablas
from .geometria import deducir_tipo
from .modelos import BORDES, ErrorEntrada, Piso

FUENTE = "Arial"
F = Font(name=FUENTE, size=10)
FN = Font(name=FUENTE, size=10, bold=True)
FT = Font(name=FUENTE, size=14, bold=True)
FB = Font(name=FUENTE, size=10, bold=True, color="FFFFFF")
FI = Font(name=FUENTE, size=9, italic=True, color="595959")
AZUL = PatternFill("solid", fgColor="1F3864")
CELESTE = PatternFill("solid", fgColor="D9E1F2")
AMARILLO = PatternFill("solid", fgColor="FFF2CC")
GRIS = PatternFill("solid", fgColor="F2F2F2")
L = Side(style="thin", color="A6A6A6")
B = Border(left=L, right=L, top=L, bottom=L)
AJ = Alignment(wrap_text=True, vertical="top")
CEN = Alignment(horizontal="center", vertical="center", wrap_text=True)
DIAM = [12, 14, 16, 18, 20]
AREA = {d: pi * (d / 10) ** 2 / 4 for d in DIAM}
CONTINUO = {"norte": "sur", "sur": "norte", "este": "oeste", "oeste": "este"}


def _estado_cf(ws, rango: str) -> None:
    """Colorea en vivo las celdas de estado."""
    c0 = rango.split(":")[0].replace("$", "")
    reglas = [(f'ISNUMBER(SEARCH("NO ",{c0}))', "FFC7CE", "9C0006"),
              (f'ISNUMBER(SEARCH("FUERA",{c0}))', "FFEB9C", "7F6000"),
              (f'ISNUMBER(SEARCH("macizado",{c0}))', "FFEB9C", "7F6000"),
              (f'LEFT({c0},6)="CUMPLE"', "C6EFCE", "006100")]
    for f, fondo, letra in reglas:
        ws.conditional_formatting.add(rango, FormulaRule(
            formula=[f], stopIfTrue=True, fill=PatternFill("solid", fgColor=fondo, bgColor=fondo),
            font=Font(name=FUENTE, bold=True, color=letra)))


def _celda(ws, ref, valor, fuente=F, relleno=None, al=AJ, borde=True, fmt=None):
    c = ws[ref]
    c.value = valor
    c.font, c.alignment = fuente, al
    if relleno:
        c.fill = relleno
    if borde:
        c.border = B
    if fmt:
        c.number_format = fmt
    return c


def _banda(ws, fila, texto, ncol=7):
    ws.merge_cells(start_row=fila, start_column=1, end_row=fila, end_column=ncol)
    c = ws.cell(fila, 1, texto)
    c.font, c.fill = FB, AZUL


class Hoja:
    """Escribe pasos de memoria y recuerda en qué celda quedó cada resultado."""

    def __init__(self, ws, nombres_globales: dict, col_res="D", fila=1):
        self.ws, self.g, self.col, self.fila = ws, nombres_globales, col_res, fila
        self.n: dict[str, str] = {}

    def ref(self, nombre: str) -> str:
        if nombre in self.n:
            return self.n[nombre]
        return self.g[nombre]

    def x(self, expr: str) -> str:
        """Sustituye {nombre} por la referencia de su celda."""
        out, i = "", 0
        while i < len(expr):
            if expr[i] == "{":
                j = expr.index("}", i)
                out += self.ref(expr[i + 1:j])
                i = j + 1
            else:
                out += expr[i]
                i += 1
        return out

    def seccion(self, t):
        _banda(self.ws, self.fila, t)
        self.fila += 1

    def nota(self, t):
        self.ws.merge_cells(start_row=self.fila, start_column=1, end_row=self.fila, end_column=7)
        c = self.ws.cell(self.fila, 1, t)
        c.font, c.alignment = FI, AJ
        self.ws.row_dimensions[self.fila].height = 26
        self.fila += 1

    def paso(self, nombre, concepto, formula="", sust=None, res="", unidad="", verif=None, ref="",
             fmt="0.00", entrada=False):
        r = self.fila
        ws = self.ws
        if nombre:
            self.n[nombre] = f"$D${r}"
        vals = [concepto, formula, ("=" + self.x(sust)) if sust else "", None, unidad,
                ("=" + self.x(verif)) if verif else "", ref]
        for k, v in enumerate(vals, start=1):
            _celda(ws, f"{get_column_letter(k)}{r}", v)
        c = ws[f"D{r}"]
        if isinstance(res, str) and not entrada:
            c.value = "=" + self.x(res)
        else:
            c.value = res
        c.font = FN
        c.alignment = Alignment(horizontal="right", vertical="top")
        c.number_format = fmt
        if entrada:
            c.fill = AMARILLO
        if nombre:
            self.n[nombre] = f"$D${r}"
        _estado_cf(ws, f"F{r}")
        self.fila += 1
        return f"$D${r}"


def _fx(n, nd=2):
    return f'FIXED({{{n}}},{nd})'


# ------------------------------------------------------------------------------- DATOS
def _hoja_datos(wb, piso: Piso, X: list[float], Y: list[float]) -> dict:
    ws = wb.active
    ws.title = "DATOS"
    _anchos(ws, [44, 12, 14, 12, 52])
    _celda(ws, "A1", "DATOS DEL PISO (cambie las celdas amarillas; todo se recalcula)", FT, borde=False,
           al=Alignment(vertical="center"))
    _celda(ws, "A2", f"{piso.proyecto.get('nombre', '')}   {piso.proyecto.get('piso', '')}", F, borde=False,
           al=Alignment(vertical="center"))
    g: dict[str, str] = {}
    fila = [4]

    def enc(t):
        _banda(ws, fila[0], t, 5)
        fila[0] += 1

    def dato(nombre, concepto, simbolo, valor, unidad, nota="", fmt="0.00", entrada=False):
        r = fila[0]
        _celda(ws, f"A{r}", concepto)
        _celda(ws, f"B{r}", simbolo, al=CEN)
        c = _celda(ws, f"C{r}", valor, FN, AMARILLO if entrada else None,
                   Alignment(horizontal="right"), fmt=fmt)
        if isinstance(valor, str) and valor.startswith("="):
            c.value = "=" + _sub(valor[1:], g)
        _celda(ws, f"D{r}", unidad)
        _celda(ws, f"E{r}", nota, FI if not entrada else F)
        g[nombre] = f"DATOS!$C${r}"
        fila[0] += 1

    m, losa, c = piso.materiales, piso.losa, piso.cargas
    enc("MATERIALES")
    dato("fc", "Resistencia del hormigón", "f'c", m.fc, "kg/cm²", "Dato", "0", True)
    dato("fy", "Fluencia del acero", "fy", m.fy, "kg/cm²", "Dato", "0", True)
    dato("gam", "Peso específico del hormigón", "γh", m.peso_hormigon, "kg/m³", "Dato", "0", True)
    dato("rec", "Recubrimiento al borde de la varilla", "r", m.recubrimiento, "cm", "Dato", "0.0", True)
    dato("E", "Módulo de elasticidad del hormigón", "Ec", "=15000*SQRT({fc})", "kg/cm²", "15000·√f'c", "0")
    dato("Es", "Módulo de elasticidad del acero", "Es", m.Es, "kg/cm²", "Dato", "0", True)
    dato("nmod", "Relación modular", "n", "={Es}/{E}", "", "Es/Ec")
    dato("b1", "β1 del bloque de compresión", "β1", "=MAX(0.65,MIN(0.85,0.85-0.05*({fc}-280)/70))", "",
         "ACI 318-19, 22.2.2.4.3", "0.000")
    enc("LOSA NERVADA")
    dato("h", "Altura total de la losa", "h", losa.altura, "cm", "Dato", "0.0", True)
    dato("el", "Espesor de la loseta", "el", losa.loseta, "cm", "Dato", "0.0", True)
    dato("bw", "Ancho de nervio", "bw", losa.ancho_nervio, "cm", "Dato", "0.0", True)
    dato("s", "Separación de nervios, eje a eje", "s", losa.separacion_nervios, "cm", "Dato", "0.0", True)
    dato("pb", "Peso de bloques", "pb", losa.peso_bloques, "kg/m²", "Dato: corrija si cambia la altura del bloque", "0.0", True)
    dato("mac", "Ancho de macizado junto a la viga", "xm", losa.macizado, "m", "Dato", "0.000", True)
    dato("hn", "Altura del nervio bajo la loseta", "hn", "={h}-{el}", "cm", "h − el", "0.0")
    dato("A", "Área de la sección T (un nervio)", "A", "={s}*{el}+{bw}*{hn}", "cm²", "s·el + bw·hn")
    dato("yg", "Centro de gravedad desde abajo", "yg", "=({bw}*{hn}*{hn}/2+{s}*{el}*({hn}+{el}/2))/{A}", "cm",
         "[bw·hn²/2 + s·el·(hn + el/2)] / A")
    dato("Ig", "Inercia de la sección T", "Ig",
         "={bw}*{hn}^3/12+{bw}*{hn}*({yg}-{hn}/2)^2+{s}*{el}^3/12+{s}*{el}*({hn}+{el}/2-{yg})^2", "cm4",
         "bw·hn³/12 + bw·hn·(yg − hn/2)² + s·el³/12 + s·el·(hn + el/2 − yg)²", "0")
    dato("he", "Altura maciza equivalente", "he", "=(12*{Ig}/{s})^(1/3)", "cm", "(12·I/s)^(1/3)")
    dato("bwm", "Ancho de nervios por metro de losa", "bw·100/s", "={bw}*100/{s}", "cm/m", "Ancho comprimido en M−")
    enc("CARGAS")
    dato("ploseta", "Peso de la loseta", "", "={el}/100*{gam}", "kg/m²", "el·γh")
    dato("pnerv", "Peso de nervios (dos direcciones, sin duplicar cruces)", "",
         "=(2*(100/{s})*{bw}*{hn}/10000-(100/{s})^2*({bw}/100)^2*{hn}/100)*{gam}", "kg/m²",
         "[2·n·bw·hn − n²·bw²·hn]·γh, n = 100/s")
    dato("pp", "Peso propio de la losa", "pp", "={ploseta}+{pnerv}+{pb}", "kg/m²", "loseta + nervios + bloques")
    dato("sc", "Sobrecarga permanente (mampostería, masillado, piso, cielo raso)", "SC", c.acabados + c.paredes + c.otras,
         "kg/m²", "Dato", "0.0", True)
    dato("viva", "Carga viva", "L", c.viva, "kg/m²", "Dato (NEC-SE-CG)", "0.0", True)
    dato("D", "Carga permanente", "D", "={pp}+{sc}", "kg/m²", "pp + SC")
    dato("qu1", "Combinación 1,4D", "", "=1.4*{D}", "kg/m²", "NEC-SE-CG")
    dato("qu2", "Combinación 1,2D + 1,6L", "", "=1.2*{D}+1.6*{viva}", "kg/m²", "NEC-SE-CG")
    dato("qu", "Carga última de diseño", "qu", "=MAX({qu1},{qu2})", "kg/m²", "máx(1,4D ; 1,2D + 1,6L)")
    dato("lam", "Factor de flecha diferida", "λΔ", c.lambda_diferida, "", "ξ = 2 para 5 años o más (ACI 24.2.4)", "0.0", True)
    dato("mamp", "¿La losa soporta mampostería? (SI / NO)", "", "SI" if c.soporta_mamposteria else "NO", "",
         "SI: límite L/480 ; NO: L/240", "@", True)
    dato("den", "Denominador del límite de flecha diferida", "", '=IF(UPPER({mamp})="SI",480,240)', "",
         "ACI 318-19, Tabla 24.2.2", "0")
    enc("VIGAS Y EJES")
    viga = piso.viga
    dato("vb", "Ancho de vigas", "b", viga.b, "cm", "Dato", "0.0", True)
    dato("vh", "Altura de vigas", "h", viga.h, "cm", "Dato", "0.0", True)
    dato("Iv", "Inercia de la viga", "Iv", "={vb}*{vh}^3/12", "cm4", "b·h³/12", "0")
    for i, d in enumerate(X):
        dato(f"dx{i}", f"Distancia en X entre los ejes {chr(65 + i)} y {chr(66 + i)}", f"X{i + 1}", d, "m", "Dato",
             "0.00", True)
    for j, d in enumerate(Y):
        dato(f"dy{j}", f"Distancia en Y entre los ejes {j + 1} y {j + 2}", f"Y{j + 1}", d, "m", "Dato", "0.00", True)
    enc("CORTANTE Y LÍMITES DE NERVIOS (ACI 318-19, 9.8.1)")
    dato("geo1", "Ancho de nervio bw >= 10 cm", "", '=IF({bw}>=10,"CUMPLE","NO CUMPLE")', "", "9.8.1.2", "@")
    dato("geo2", "Altura h <= 3,5·bw", "", '=IF({h}<=3.5*{bw},"CUMPLE","NO CUMPLE")', "", "9.8.1.3", "@")
    dato("geo3", "Separación libre <= 75 cm", "", '=IF({s}-{bw}<=75,"CUMPLE","NO CUMPLE")', "", "9.8.1.4", "@")
    dato("geo4", "Loseta >= máx(5 ; libre/12)", "", '=IF({el}>=MAX(5,({s}-{bw})/12),"CUMPLE","NO CUMPLE")', "",
         "9.8.2 y 9.8.3", "@")
    dato("fac", "Factor de aumento de Vc en nervios", "", '=IF(AND({bw}>=10,{h}<=3.5*{bw},{s}-{bw}<=75),1.1,1)', "",
         "1,1 si cumple la geometría (9.8.1.5)", "0.0")
    dato("vc0", "Esfuerzo de corte del hormigón", "", "=0.53*SQRT({fc})", "kg/cm²", "0,53·√f'c (NEC-SE-HM)")
    dato("vc", "Esfuerzo resistente en nervios", "vc", "={fac}*{vc0}", "kg/cm²", "factor·0,53·√f'c")
    dato("geo", "Geometría de nervios", "", '=IF(COUNTIF(C{0}:C{1},"NO*")=0,"CUMPLE","NO CUMPLE")'.format(
        int(g["geo1"].split("$")[-1]), int(g["geo4"].split("$")[-1])), "", "", "@")
    for k in ("geo1", "geo2", "geo3", "geo4", "geo"):
        _estado_cf(ws, g[k].split("!")[1])
    dv = DataValidation(type="list", formula1='"SI,NO"', allow_blank=False)
    ws.add_data_validation(dv)
    dv.add(g["mamp"].split("!")[1])
    ws.freeze_panes = "A4"
    _pagina(ws, horizontal=False)
    return g


def _sub(expr: str, g: dict) -> str:
    out, i = "", 0
    while i < len(expr):
        if expr[i] == "{":
            j = expr.index("}", i)
            out += g[expr[i + 1:j]]
            i = j + 1
        else:
            out += expr[i]
            i += 1
    return out


def _pagina(ws, area=None, horizontal=True):
    ws.page_setup.orientation = "landscape" if horizontal else "portrait"
    ws.page_setup.paperSize = ws.PAPERSIZE_A4
    ws.page_setup.fitToWidth, ws.page_setup.fitToHeight = 1, 0
    ws.sheet_properties.pageSetUpPr.fitToPage = True
    if area:
        ws.print_area = area


def _anchos(ws, anchos):
    for i, a in enumerate(anchos, start=1):
        ws.column_dimensions[get_column_letter(i)].width = a


# ------------------------------------------------------------------------------- TABLAS
def _hoja_tablas(wb) -> None:
    ws = wb.create_sheet("TABLAS")
    _celda(ws, "A1", "Tabla 9.7 (losas nervadas) y tipo de paño según los bordes", FN, borde=False,
           al=Alignment(vertical="center"))
    enc = ["Tipo", "Lx/Ly", "δ", "my−", "my+", "mx−", "mx+", "myb−", "myb+", "mxb−", "mxb+"]
    for k, t in enumerate(enc, start=1):
        _celda(ws, f"{get_column_letter(k)}2", t, FN, CELESTE, CEN)
    r = 3
    for tipo, filas in tablas.cargar("nervada").items():
        for f in sorted(filas, key=lambda x: -x["beta"]):
            vals = [tipo, f["beta"]] + [f[k] for k in tablas.COEFICIENTES]
            for k, v in enumerate(vals, start=1):
                ws.cell(r, k, v).font = F
            r += 1
    _celda(ws, "M2", "Clave de bordes", FN, CELESTE, CEN)
    _celda(ws, "N2", "Tipo", FN, CELESTE, CEN)
    letras = {"c": "continuo", "d": "discontinuo", "l": "libre"}
    r = 3
    for a in "cdl":
        for b in "cdl":
            for c in "cdl":
                for d in "cdl":
                    t = deducir_tipo((letras[a], letras[b]), (letras[c], letras[d])) or 0
                    ws.cell(r, 13, a + b + c + d).font = F
                    ws.cell(r, 14, t).font = F
                    r += 1
    _celda(ws, "M86", "Clave: bordes largos (2) y cortos (2); c = continuo, d = discontinuo, l = libre.",
           FI, borde=False)
    _anchos(ws, [7, 7] + [8] * 9 + [3, 16, 7])
    _pagina(ws, horizontal=False)


# ------------------------------------------------------------------------------- PAÑO
def _seleccion(need: str) -> tuple[str, str]:
    """Fórmulas de diámetro y número de varillas por nervio para un área requerida."""
    phi = "20"
    for d in reversed(DIAM):
        phi = f"IF({need}<={2 * AREA[d] + 1e-6:.6f},{d},{phi})"
    for d in reversed(DIAM):
        phi = f"IF({need}<={AREA[d] + 1e-6:.6f},{d},{phi})"
    n = f"IF({need}<={AREA[20] + 1e-6:.6f},1,2)"
    return phi, n


def _area(phi: str) -> str:
    return f"PI()*({phi}/10)^2/4"


def _hoja_pano(wb, g, piso: Piso, pano, i, j, nx, ny, ids) -> dict:
    ws = wb.create_sheet(pano.id)
    _anchos(ws, [42, 36, 46, 15, 10, 30, 30])
    for k in range(20, 40):
        ws.column_dimensions[get_column_letter(k)].width = 11
    _celda(ws, "A1", f"MEMORIA DE CÁLCULO - PAÑO {pano.id}  (ejes {pano.ejes_x[0]}-{pano.ejes_x[1]} / "
           f"{pano.ejes_y[0]}-{pano.ejes_y[1]})", FT, borde=False, al=Alignment(vertical="center"))
    _celda(ws, "A2", "Fórmulas vivas: cambie los bordes (celdas amarillas) o los datos de la hoja DATOS y "
           "todo, incluidos los gráficos, se recalcula.", FI, borde=False, al=Alignment(vertical="center"))
    H = Hoja(ws, g, fila=4)
    # bordes de entrada (fila 4) y resultado
    dv = DataValidation(type="list", formula1='"continuo,discontinuo,libre"', allow_blank=False)
    ws.add_data_validation(dv)
    _celda(ws, "A4", "RESULTADO DEL PAÑO", FN)
    # Disposición de entradas: filas 5 y 6
    ent = {"norte": "B5", "sur": "D5", "este": "B6", "oeste": "D6"}
    for b, ref in ent.items():
        _celda(ws, ref.replace("B", "A").replace("D", "C"), f"Borde {b} (eje {pano.eje_de(b)})", FN)
        c = _celda(ws, ref, pano.cond[b], FN, AMARILLO, CEN)
        dv.add(ref)
        H.n["c_" + b] = "$" + ref[0] + "$" + ref[1:]
    _celda(ws, "E5", "Vecinos", FI)
    vecinos = {"norte": (i, j + 1), "sur": (i, j - 1), "este": (i + 1, j), "oeste": (i - 1, j)}
    vec = {b: (ids.get(v) if 0 <= v[0] < nx and 0 <= v[1] < ny else None) for b, v in vecinos.items()}
    _celda(ws, "F5", "; ".join(f"{b}: {v or 'ninguno'}" for b, v in vec.items()), FI)
    H.fila = 8
    # Gráficos: se dejan las filas 8-75 para ellos
    filas_graficos = 9
    H.fila = 78
    hdr = ["Concepto", "Fórmula", "Sustitución", "Resultado", "Unidad", "Verificación", "Referencia"]
    for k, t in enumerate(hdr, start=1):
        _celda(ws, f"{get_column_letter(k)}{H.fila}", t, FN, CELESTE, CEN)
    H.fila += 1

    W, Hh = f"dx{i}", f"dy{j}"
    H.seccion("1. GEOMETRÍA Y CLASIFICACIÓN")
    H.paso("W", "Luz en X (centro a centro)", "Dato (DATOS)", None, f"{{{W}}}", "m")
    H.paso("H", "Luz en Y (centro a centro)", "Dato (DATOS)", None, f"{{{Hh}}}", "m")
    H.paso("dirX", "¿La luz corta es X?", "W <= H", None, "{W}<={H}", "", None, "", "General")
    H.paso("Lx", "Luz corta", "Lx = mín(W ; H)", None, "MIN({W},{H})", "m")
    H.paso("Ly", "Luz larga", "Ly = máx(W ; H)", None, "MAX({W},{H})", "m")
    H.paso("beta", "Relación de luces", "Lx/Ly", '{Lx}&"/"&{Ly}', "{Lx}/{Ly}", "",
           'IF({beta}>=0.5,"CUMPLE: dos direcciones","NO CUMPLE: Lx/Ly < 0,5 (una dirección)")', "", "0.000")
    H.paso("bc", "β de cálculo (acotado y redondeado)", "", None, "MAX(0.5,MIN(1,ROUND({beta},6)))", "", None, "",
           "0.000")
    H.paso("clave", "Clave de bordes (largos, cortos)", "c / d / l", None,
           'IF({dirX},LEFT({c_oeste},1)&LEFT({c_este},1)&LEFT({c_sur},1)&LEFT({c_norte},1),'
           'LEFT({c_sur},1)&LEFT({c_norte},1)&LEFT({c_oeste},1)&LEFT({c_este},1))', "", None, "TABLAS", "@")
    H.paso("tipo", "Tipo de paño", "Según los bordes", None, "IFERROR(VLOOKUP({clave},TABLAS!$M$3:$N$83,2,FALSE),0)",
           "", 'IF({tipo}>0,"CUMPLE","NO CUMPLE: combinación no tabulada")', "Tabla 9.7", "0")
    H.paso("ok", "¿Dentro del alcance de la hoja?", "tipo > 0 y Lx/Ly >= 0,5", None,
           "AND({tipo}>0,{beta}>=0.5)", "",
           'IF({ok},"CUMPLE","NO CUMPLE: FUERA DE ALCANCE, use un modelo de elementos finitos o el programa")', "",
           "General")
    H.paso("pos", "Fila superior en la tabla", "", None, "MATCH({bc},TABLAS!$B$3:$B$8,-1)", "", None, "", "0")
    H.paso("pos2", "Fila inferior", "", None, "MIN({pos}+1,6)", "", None, "", "0")
    H.paso("t", "Fracción de interpolación", "", None,
           "IF({pos}={pos2},0,(INDEX(TABLAS!$B$3:$B$8,{pos})-{bc})/(INDEX(TABLAS!$B$3:$B$8,{pos})-"
           "INDEX(TABLAS!$B$3:$B$8,{pos2})))", "", None, "Interpolación lineal", "0.000")

    H.seccion("2. COEFICIENTES Y MOMENTOS (Tabla 9.7, M = 0,0001·qu·m·Lx²)")
    cols = dict(zip(tablas.COEFICIENTES, "CDEFGHIJK"))
    simb = {"delta": "δ", "my_neg": "my−", "my_pos": "my+", "mx_neg": "mx−", "mx_pos": "mx+", "myb_neg": "myb−",
            "myb_pos": "myb+", "mxb_neg": "mxb−", "mxb_pos": "mxb+"}
    for k, col in cols.items():
        rng = f"TABLAS!${col}$3:${col}$110"
        f1 = f"INDEX({rng},({{tipo}}-1)*6+{{pos}})"
        f2 = f"INDEX({rng},({{tipo}}-1)*6+{{pos2}})"
        H.paso(k, f"Coeficiente {simb[k]}", "Interpolado en Lx/Ly", None,
               f"IF({{ok}},{f1}+({f2}-{f1})*{{t}},0)", "", None, "Tabla 9.7", "0.0")
    for k in tablas.COEFICIENTES[1:]:
        H.paso("M" + k, f"Momento {simb[k].replace('m', 'M', 1)}", "0,0001·qu·m·Lx²",
               f'"0,0001·"&{_fx("qu")}&"·"&FIXED({{{k}}},1)&"·"&{_fx("Lx")}&"²"',
               f"0.0001*{{qu}}*{{{k}}}*{{Lx}}^2", "kg·m/m", None, "Tabla 9.7", "0")
    H.paso("negC", "M− en bordes largos (envolvente)", "máx(My− ; Myb−)", None, "MAX({Mmy_neg},{Mmyb_neg})", "kg·m/m",
           fmt="0")
    H.paso("negL", "M− en bordes cortos (envolvente)", "máx(Mx− ; Mxb−)", None, "MAX({Mmx_neg},{Mmxb_neg})", "kg·m/m",
           fmt="0")
    H.paso("Mpc", "M+ dirección corta", "máx(My+ ; Myb+)", None, "MAX({Mmy_pos},{Mmyb_pos})", "kg·m/m", fmt="0")
    H.paso("Mpl", "M+ dirección larga", "máx(Mx+ ; Mxb+)", None, "MAX({Mmx_pos},{Mmxb_pos})", "kg·m/m", fmt="0")

    H.seccion("3. MOMENTOS NEGATIVOS EN LOS BORDES Y COMPATIBILIDAD CON LOS VECINOS")
    largo = {"oeste": "{dirX}", "este": "{dirX}", "sur": "NOT({dirX})", "norte": "NOT({dirX})"}
    for b in BORDES:
        H.paso("lg_" + b, f"¿Borde {b} es largo?", "", None, largo[b], "", None, "", "General")
        H.paso("Mb_" + b, f"M− propio, borde {b}", "Si es continuo: M− del borde", None,
               f'IF({{c_{b}}}="continuo",IF({{lg_{b}}},{{negC}},{{negL}}),0)', "kg·m/m", fmt="0")
    filas_mb = {b: H.n["Mb_" + b] for b in BORDES}
    for b in BORDES:
        v = vec[b]
        if v:
            otro = f"'{v}'!{filas_mb[CONTINUO[b]]}"
            H.paso("Md_" + b, f"M− de diseño, borde {b} (vecino {v})", "máx(propio ; vecino)",
                   f'"máx("&FIXED({{Mb_{b}}},0)&" ; "&FIXED({otro},0)&")"',
                   f'IF({{c_{b}}}="libre",0,MAX({{Mb_{b}}},{otro}))', "kg·m/m", None, "Compatibilidad", "0")
        else:
            H.paso("Md_" + b, f"M− de diseño, borde {b} (perimetral)", "propio", None,
                   f'IF({{c_{b}}}="libre",0,{{Mb_{b}}})', "kg·m/m", None, "", "0")

    # ---------------- Flexión con selección de diámetros en tres pasadas
    H.seccion("4. FLEXIÓN (M+ con b = 100 cm; M− con el ancho de los nervios)")
    casos = [("pc", "M+ dirección corta", "{Mpc}", "+", "TRUE"), ("pl", "M+ dirección larga", "{Mpl}", "+", "FALSE")]
    for b in BORDES:
        casos.append((b[0] + "n", f"M− borde {b}", f"{{Md_{b}}}", "-", f"{{lg_{b}}}"))
    # columnas auxiliares (T..AA) en la fila de cada caso
    aux0 = H.fila

    cfil = {}
    r0 = H.fila
    # Encabezado auxiliar
    for k, t in enumerate(["Mu", "corta?", "signo b", "d1", "phi1", "d2", "phi2"], start=20):
        _celda(ws, f"{get_column_letter(k)}{r0 - 1}", t, FI, GRIS, CEN)
    for n_, (key, nom, mu, sg, esc) in enumerate(casos):
        r = r0 + n_
        cfil[key] = r
        ws[f"T{r}"] = "=" + H.x(mu)
        ws[f"U{r}"] = "=" + H.x(esc)
        ws[f"V{r}"] = "=" + H.x("{bwm}" if sg == "-" else "100")
    last = r0 + len(casos) - 1
    rng = lambda col: f"${col}${r0}:${col}${last}"  # noqa: E731

    def d_formula(dircol_row, phic, phil):
        return (f"IF($U${dircol_row},{H.x('{h}')}-{H.x('{rec}')}-{phic}/20,"
                f"{H.x('{h}')}-{H.x('{rec}')}-{phic}/10-{phil}/20)")

    def phi_de(d, mu, b):
        req = (f"IF({mu}<=0,0,IF({d}^2-2*{mu}*100/(0.9*0.85*{H.x('{fc}')}*{b})<0,99,"
               f"0.85*{H.x('{fc}')}*{b}/{H.x('{fy}')}*({d}-SQRT({d}^2-2*{mu}*100/(0.9*0.85*{H.x('{fc}')}*{b})))))")
        asmin = f"MAX(0.8*SQRT({H.x('{fc}')}),14)/{H.x('{fy}')}*{H.x('{bwm}')}*{d}"
        need = f"MAX({req},{asmin})*{H.x('{s}')}/100"
        return _seleccion(need)[0]

    for key, r in cfil.items():
        ws[f"W{r}"] = "=" + d_formula(r, "12", "12")
        ws[f"X{r}"] = "=" + phi_de(f"W{r}", f"T{r}", f"V{r}")
    pc1 = f"MAX(12,MAX(IF({rng('U')},{rng('X')},0)))"
    # evitar fórmulas matriciales: SUMPRODUCT/MAX por filas
    pc1 = "MAX(12," + ",".join(f"IF($U${r},$X${r},0)" for r in cfil.values()) + ")"
    pl1 = "MAX(12," + ",".join(f"IF($U${r},0,$X${r})" for r in cfil.values()) + ")"
    for key, r in cfil.items():
        ws[f"Y{r}"] = "=" + d_formula(r, pc1, pl1)
        ws[f"Z{r}"] = "=" + phi_de(f"Y{r}", f"T{r}", f"V{r}")
    pc2 = "MAX(" + pc1 + "," + ",".join(f"IF($U${r},$Z${r},0)" for r in cfil.values()) + ")"
    pl2 = "MAX(" + pl1 + "," + ",".join(f"IF($U${r},0,$Z${r})" for r in cfil.values()) + ")"
    H.fila = last + 2
    H.paso("phic", "Diámetro mayor de la capa corta (exterior)", "elegido en el diseño", None, pc2, "mm", fmt="0")
    H.paso("phil", "Diámetro mayor de la capa larga (interior)", "elegido en el diseño", None, pl2, "mm", fmt="0")
    H.paso("dc", "Peralte efectivo, dirección corta", "d = h − r − Øc/2",
           f'{_fx("h", 1)}&" − "&{_fx("rec", 1)}&" − "&FIXED({{phic}}/20,2)', "{h}-{rec}-{phic}/20", "cm")
    H.paso("dl", "Peralte efectivo, dirección larga", "d = h − r − Øc − Øl/2",
           f'{_fx("h", 1)}&" − "&{_fx("rec", 1)}&" − "&FIXED({{phic}}/10,2)&" − "&FIXED({{phil}}/20,2)',
           "{h}-{rec}-{phic}/10-{phil}/20", "cm")
    for key, nom, mu, sg, esc in casos:
        H.nota(f"{nom}")
        p = key + "_"
        H.paso(p + "Mu", "  Momento de diseño", "Mu", None, mu, "kg·m/m", fmt="0")
        H.paso(p + "d", "  Peralte", "d corta o larga", None, f"IF({esc},{{dc}},{{dl}})", "cm")
        H.paso(p + "b", "  Ancho comprimido", "M+: 100 ; M−: bw·100/s", None, "{bwm}" if sg == "-" else "100", "cm")
        disc = f"{{{p}d}}^2-2*{{{p}Mu}}*100/(0.9*0.85*{{fc}}*{{{p}b}})"
        H.paso(p + "req", "  Acero requerido", "As = 0,85·f'c·b/fy·[d − √(d² − 2Mu/(φ·0,85·f'c·b))]",
               f'"0,85·"&{_fx("fc", 0)}&"·"&FIXED({{{p}b}},1)&"/"&{_fx("fy", 0)}&"·["&FIXED({{{p}d}},2)&'
               f'" − √("&FIXED({{{p}d}},2)&"² − 2·"&FIXED({{{p}Mu}}*100,0)&"/(0,9·0,85·"&{_fx("fc", 0)}&"·"&'
               f'FIXED({{{p}b}},1)&"))]"',
               f"IF({{{p}Mu}}<=0,0,IF({disc}<0,-1,0.85*{{fc}}*{{{p}b}}/{{fy}}*({{{p}d}}-SQRT({disc}))))",
               "cm²/m", f'IF({{{p}req}}<0,"NO CUMPLE: la sección no alcanza","")', "ACI 318-19, 22.2", "0.000")
        H.paso(p + "min", "  Acero mínimo", "máx(0,8·√f'c ; 14)/fy · bw·d", None,
               f"MAX(0.8*SQRT({{fc}}),14)/{{fy}}*{{bwm}}*{{{p}d}}", "cm²/m", None, "ACI 318-19, 9.6.1.2", "0.000")
        H.paso(p + "dis", "  Acero de diseño", "máx(As ; As,mín)", None, f"MAX({{{p}req}},{{{p}min}})", "cm²/m",
               fmt="0.000")
        H.paso(p + "nec", "  Acero por nervio", "As·s/100", None, f"{{{p}dis}}*{{s}}/100", "cm²", fmt="0.000")
        phi, n = _seleccion(H.x(f"{{{p}nec}}"))
        H.paso(p + "phi", "  Diámetro", "menor que alcance con 1 varilla; si no, 2", None, phi, "mm", fmt="0")
        H.paso(p + "n", "  Varillas por nervio", "", None, n, "", fmt="0")
        H.paso(p + "Asu", "  Acero colocado por nervio", "n·π·Ø²/4", None, f"{{{p}n}}*{_area(H.x('{' + p + 'phi}'))}",
               "cm²", fmt="0.000")
        bcomp = "{bw}" if sg == "-" else "{s}"
        lim = "{hn}" if sg == "-" else "{el}"
        H.paso(p + "a", "  Bloque de compresión", "a = As·fy/(0,85·f'c·b)", None,
               f"{{{p}Asu}}*{{fy}}/(0.85*{{fc}}*{bcomp})", "cm",
               f'IF({{{p}a}}<={lim},"CUMPLE: a <= "&FIXED({lim},1),"NO CUMPLE: a > "&FIXED({lim},1))',
               "ACI 318-19, 22.2.2.4")
        H.paso(p + "eps", "  Deformación del acero", "εt = 0,003·(d − c)/c, c = a/β1", None,
               f"0.003*({{{p}d}}-{{{p}a}}/{{b1}})/({{{p}a}}/{{b1}})", "",
               f'IF({{{p}eps}}>=0.005,"CUMPLE: εt >= 0,005","NO CUMPLE: εt < 0,005")', "ACI 318-19, 21.2.2",
               "0.0000")
        H.paso(p + "arm", "  ARMADO POR NERVIO", "", None,
               f'IF(AND("{key[0]}"<>"p",{{c_{dict(n="norte", s="sur", e="este", o="oeste").get(key[0], "norte")}}}'
               f'="libre"),"-",{{{p}n}}&"Ø"&{{{p}phi}}&IF({{{p}Mu}}<=0," (mín.)",""))'
               if key[0] != "p" else f'{{{p}n}}&"Ø"&{{{p}phi}}&IF({{{p}Mu}}<=0," (mín.)","")',
               "",
               f'IF(AND({{{p}req}}>=0,{{{p}nec}}<={2 * AREA[20] + 1e-6:.6f},{{{p}a}}<={lim},{{{p}eps}}>=0.005),'
               f'"CUMPLE","NO CUMPLE")', "", "@")
        H.paso(p + "uso", "  Aprovechamiento", "As diseño / As colocado", None,
               f"{{{p}dis}}/({{{p}Asu}}*100/{{s}})", "", None, "", "0%")
    flex_estados = [H.n[k + "_arm"].replace("$D$", "$F$") for k, *_ in casos]

    # ---------------- Cortante
    H.seccion("5. CORTANTE (solo los nervios)")
    H.paso("unap", "¿Borde largo libre?", "", None,
           'IF({dirX},OR({c_oeste}="libre",{c_este}="libre"),OR({c_sur}="libre",{c_norte}="libre"))', "", fmt="General")
    H.paso("Vc", "Cortante en la cara de la viga", "qu·(Lx/2 − b/2)",
           f'{_fx("qu")}&"·("&FIXED(IF({{unap}},{{Lx}},{{Lx}}/2),2)&" − "&FIXED({{vb}}/200,3)&")"',
           "{qu}*(IF({unap},{Lx},{Lx}/2)-{vb}/200)", "kg/m", None, "Criterio de la hoja de referencia", "0")
    H.paso("Vu", "Cortante a la distancia d", "Vu = V,cara − qu·d",
           f'FIXED({{Vc}},0)&" − "&{_fx("qu")}&"·"&FIXED({{dc}}/100,3)', "MAX(0,{Vc}-{qu}*{dc}/100)", "kg/m",
           fmt="0")
    H.paso("vu", "Esfuerzo actuante en nervios", "vu = Vu/(0,75·bw·100/s·d)",
           f'FIXED({{Vu}},0)&"/(0,75·"&FIXED({{bwm}},1)&"·"&FIXED({{dc}},2)&")"', "{Vu}/(0.75*{bwm}*{dc})",
           "kg/cm²")
    H.paso("vcp", "Esfuerzo resistente", "factor·0,53·√f'c", None, "{vc}", "kg/cm²", None, "ACI 9.8.1.5")
    H.paso("Vum", "Cortante en el borde del macizado", "V,cara − qu·xm", None, "MAX(0,{Vc}-{qu}*{mac})", "kg/m",
           fmt="0")
    H.paso("vum", "Esfuerzo en nervios al borde del macizado", "Vu,mac/(0,75·b·d)", None,
           "{Vum}/(0.75*{bwm}*{dc})", "kg/cm²")
    H.paso("vus", "Esfuerzo en la zona maciza (b = 100)", "Vu/(0,75·100·d)", None, "{Vu}/(0.75*100*{dc})",
           "kg/cm²")
    H.paso("cort", "RESULTADO DE CORTANTE", "", None,
           'IF({vu}<={vcp},"CUMPLE",IF(AND({vum}<={vcp},{vus}<={vc0},{mac}*100>{dc}),"CUMPLE con macizado",'
           '"NO CUMPLE"))', "", '{cort}', "ACI 318-19, 22.5", "@")

    # ---------------- Flechas
    H.seccion("6. FLECHAS CON CARGAS DE SERVICIO E INERCIA EFECTIVA")
    H.paso("mp", "Coeficiente de momento positivo usado", "máx(my+ ; myb+)", None, "MAX({my_pos},{myb_pos})", "",
           fmt="0.0")
    H.paso("kd", "Flecha elástica por unidad de carga", "0,0001·δ·Lx⁴/(E·he³)", None,
           "0.0001*{delta}*({Lx}*100)^4/({E}*{he}^3)/10000", "cm/(kg/m²)", fmt="0.000000")
    H.paso("kM", "Momento de servicio por unidad de carga (un nervio)", "0,0001·m·Lx²·100·s/100", None,
           "0.0001*{mp}*{Lx}^2*100*{s}/100", "kg·cm/(kg/m²)", fmt="0.000")
    H.paso("nAs", "Área transformada del acero inferior", "n·As", None, "{nmod}*{pc_Asu}", "cm²", fmt="0.000")
    c1 = "(-{nAs}+SQRT({nAs}^2+2*{s}*{nAs}*{pc_d}))/{s}"
    Bq = "(({s}-{bw})*{el}+{nAs})"
    Cq = "(-(({s}-{bw})*{el}^2/2+{nAs}*{pc_d}))"
    c2 = f"(-{Bq}+SQRT({Bq}^2-4*({{bw}}/2)*{Cq}))/(2*({{bw}}/2))"
    H.paso("cf", "Eje neutro de la sección fisurada", "b·c²/2 = n·As·(d − c)", None,
           f"IF({c1}<={{el}},{c1},{c2})", "cm")
    H.paso("Icr", "Inercia fisurada", "b·c³/3 + n·As·(d − c)² (alma si c > el)", None,
           "MIN({Ig},{s}*{cf}^3/3+{nAs}*({pc_d}-{cf})^2-IF({cf}>{el},({s}-{bw})*({cf}-{el})^3/3,0))", "cm4", fmt="0")
    H.paso("Mcr", "Momento de fisuración", "2·√f'c·Ig/yg", None, "2*SQRT({fc})*{Ig}/{yg}", "kg·cm", fmt="0")
    for nom, q in (("D", "{D}"), ("DL", "({D}+{viva})")):
        H.paso("Ma" + nom, f"Momento de servicio con {nom}", "kM·q", None, f"{{kM}}*{q}", "kg·cm", fmt="0")
        H.paso("Ie" + nom, f"Inercia efectiva con {nom}", "Icr/[1 − ((2/3)Mcr/Ma)²(1 − Icr/Ig)]", None,
               f"IF({{Ma{nom}}}<=2/3*{{Mcr}},{{Ig}},{{Icr}}/(1-((2/3)*{{Mcr}}/{{Ma{nom}}})^2*(1-{{Icr}}/{{Ig}})))",
               "cm4", None, "ACI 318-19, Tabla 24.2.3.5", "0")
        H.paso("f" + nom, f"Flecha inmediata con {nom}", "kd·q·Ig/Ie", None, f"{{kd}}*{q}*{{Ig}}/{{Ie{nom}}}", "cm",
               fmt="0.000")
    H.paso("fL", "Flecha por carga viva", "Δ(D+L) − Δ(D)", None, "ABS({fDL}-{fD})", "cm",
           'IF({fL}<={Lx}*100/360,"CUMPLE: <= "&FIXED({Lx}*100/360,3),"NO CUMPLE: > "&FIXED({Lx}*100/360,3))',
           "ACI 318-19, Tabla 24.2.2", "0.000")
    H.paso("flp", "Flecha diferida más viva", "λ·Δ(D) + ΔL",
           f'FIXED({{lam}},1)&"·"&FIXED({{fD}},3)&" + "&FIXED({{fL}},3)', "{lam}*ABS({fD})+{fL}", "cm",
           'IF({flp}<={Lx}*100/{den},"CUMPLE: <= L/"&{den}&" = "&FIXED({Lx}*100/{den},3),'
           '"NO CUMPLE: > L/"&{den}&" = "&FIXED({Lx}*100/{den},3))', "ACI 318-19, 24.2.4", "0.000")

    # ---------------- Altura mínima
    H.seccion("7. ALTURA MÍNIMA (ACI 318-19, 8.3.1.2)")
    for b in BORDES:
        propio = "{H}" if b in ("norte", "sur") else "{W}"
        v = vecinos[b]
        if vec[b]:
            otra = f"{{dy{v[1]}}}" if b in ("norte", "sur") else f"{{dx{v[0]}}}"
            ancho = f"({propio}*100+{otra}*100)/2"
        else:
            ancho = f"({propio}*100+{{vb}})/2"
        H.paso("al_" + b, f"α borde {b}", "Iviga/Ilosa", None,
               f'IF({{c_{b}}}="libre",0,{{Iv}}/({{Ig}}*{ancho}/{{s}}))', "", fmt="0.000")
    H.paso("am", "αm", "promedio", None, "AVERAGE({al_norte},{al_sur},{al_este},{al_oeste})", "", fmt="0.000")
    H.paso("lnl", "Luz libre larga", "Ly − b", None, "{Ly}*100-{vb}", "cm", fmt="0.0")
    H.paso("lnc", "Luz libre corta", "Lx − b", None, "{Lx}*100-{vb}", "cm", fmt="0.0")
    H.paso("bt", "β = ln larga / ln corta", "", None, "{lnl}/{lnc}", "", fmt="0.000")
    H.paso("h0", "Espesor mínimo", "ln·(0,8 + fy/14000)/(36 + …)", None,
           "IF({am}>2,MAX(9,{lnl}*(0.8+{fy}/14000)/(36+9*{bt})),"
           "MAX(12.5,{lnl}*(0.8+{fy}/14000)/(36+5*{bt}*({am}-0.2))))", "cm")
    deb = ",".join(f'AND({{c_{b}}}<>"continuo",{{al_{b}}}<0.8)' for b in BORDES)
    H.paso("hmin", "Espesor mínimo con aumento por bordes débiles", "×1,10 si hay borde discontinuo con α < 0,8",
           None, f"{{h0}}*IF(OR({deb}),1.1,1)", "cm")
    H.paso("hok", "Altura equivalente he", "he >= hmín", None, "{he}", "cm",
           'IF({he}>={hmin},"CUMPLE: he >= "&FIXED({hmin},2),"NO CUMPLE: he < "&FIXED({hmin},2))',
           "ACI 318-19, 8.3.1.2")

    # ---------------- Resultado
    H.seccion("8. RESULTADO DEL PAÑO")
    est = ",".join(f'LEFT({e},2)<>"NO"' for e in flex_estados)
    H.paso("flex", "Flexión", "", None, f'IF(AND({est}),"CUMPLE","NO CUMPLE")', "", "{flex}", "", "@")
    H.paso("flech", "Flechas", "", None,
           'IF(AND({fL}<={Lx}*100/360,{flp}<={Lx}*100/{den}),"CUMPLE","NO CUMPLE")', "", "{flech}", "", "@")
    H.paso("alt", "Altura mínima", "", None, 'IF({he}>={hmin},"CUMPLE","NO CUMPLE")', "", "{alt}", "", "@")
    H.paso("res", "RESULTADO GLOBAL", "", None,
           'IF(NOT({ok}),"FUERA DE ALCANCE",IF(AND({flex}="CUMPLE",LEFT({cort},6)="CUMPLE",{flech}="CUMPLE",'
           '{alt}="CUMPLE",{geo}="CUMPLE"),IF({cort}="CUMPLE","CUMPLE","CUMPLE con macizado"),"NO CUMPLE"))',
           "", "{res}", "", "@")
    c = ws["B4"]
    c.value = "=" + H.x("{res}")
    c.font = FN
    c.border = B
    _estado_cf(ws, "B4")
    _estado_cf(ws, f"F{aux0}:F{H.fila}")
    _graficos(ws, H, filas_graficos)
    ws.freeze_panes = "A7"
    ws.sheet_view.zoomScale = 90
    _pagina(ws, f"A1:G{H.fila}")
    return H.n


# ------------------------------------------------------------------------------- gráficos
def _graficos(ws, H: Hoja, fila0: int) -> None:
    x = H.x
    col0 = 30  # AD
    C = lambda k: get_column_letter(col0 + k)  # noqa: E731
    r = 4
    _celda(ws, f"{C(0)}{r - 1}", "Datos de los gráficos (fórmulas, no editar)", FI, borde=False)

    # --- momentos (dos direcciones): curva parabólica con M1, M2 y M+
    def momentos(c0, dir_corta: bool):
        if dir_corta:
            M1 = x('IF({dirX},{Md_oeste},{Md_sur})')
            M2 = x('IF({dirX},{Md_este},{Md_norte})')
            Mp, L = x("{Mpc}"), x("{Lx}")
        else:
            M1 = x('IF({dirX},{Md_sur},{Md_oeste})')
            M2 = x('IF({dirX},{Md_norte},{Md_este})')
            Mp, L = x("{Mpl}"), x("{Ly}")
        cm1, cm2, cmp_, ck = (f"${C(c0)}$4", f"${C(c0)}$5", f"${C(c0)}$6", f"${C(c0)}$7")
        ws[f"{C(c0)}4"] = "=" + M1
        ws[f"{C(c0)}5"] = "=" + M2
        ws[f"{C(c0)}6"] = "=" + Mp
        P = f"({cmp_}+{cm1})"
        ws[f"{C(c0)}7"] = f"=IF({cmp_}<=0,0,(2*{P}-({cm1}-{cm2})+2*SQRT({P}*({cmp_}+{cm2})))/4)"
        ws[f"{C(c0)}8"] = (f'="M+ = "&FIXED({cmp_},0)&"   M− izq. = "&FIXED({cm1},0)&"   M− der. = "&FIXED({cm2},0)'
                           f'&"  (kg·m/m)"')
        for n in range(21):
            rr = 10 + n
            xi = n / 20
            ws[f"{C(c0)}{rr}"] = f"={xi}*{L}"
            ws[f"{C(c0 + 1)}{rr}"] = f"=-{cm1}*(1-{xi})-{cm2}*{xi}+4*{ck}*{xi}*(1-{xi})"
            ws[f"{C(c0 + 2)}{rr}"] = 0
        ch = ScatterChart()
        ch.title = "Momentos, dirección " + ("corta" if dir_corta else "larga") + " (positivo hacia abajo)"
        ch.style = 13
        ch.x_axis.title = "Posición (m)"
        ch.y_axis.title = "M (kg·m/m)"
        ch.y_axis.scaling.orientation = "maxMin"
        xs = Reference(ws, min_col=col0 + c0, min_row=10, max_row=30)
        s = Series(Reference(ws, min_col=col0 + c0 + 1, min_row=10, max_row=30), xs)
        s.tx = SeriesLabel(strRef=StrRef(f"'{ws.title}'!${C(c0)}$8"))
        s.graphicalProperties.line.solidFill = "C25A14"
        s.graphicalProperties.line.width = 28000
        s.marker.symbol = "none"
        s.smooth = True
        s._keep = 1
        ch.series.append(s)
        s0 = Series(Reference(ws, min_col=col0 + c0 + 2, min_row=10, max_row=30), xs, title="Eje")
        s0.graphicalProperties.line.solidFill = "404040"
        s0.marker.symbol = "none"
        ch.series.append(s0)
        _ejes(ch)
        ch.legend.position = "b"
        return ch

    ch1 = momentos(0, True)
    ch2 = momentos(4, False)

    # --- cortante
    c0 = 8
    ws[f"{C(c0)}4"] = "=" + x("MAX({Vc}/{qu},1.6*MAX({dc}/100,{mac}))")
    xf = f"${C(c0)}$4"
    ws[f"{C(c0)}5"] = "=" + x("0.75*{vcp}*{bwm}*{dc}")
    ws[f"{C(c0)}6"] = "=" + x('"φ·Vc de los nervios = "&FIXED(0.75*{vcp}*{bwm}*{dc},0)&" kg/m"')
    ws[f"{C(c0)}7"] = "=" + x('"Vu(x)   |   "&{cort}')
    for n in range(11):
        rr = 10 + n
        ws[f"{C(c0)}{rr}"] = f"={n / 10}*{xf}"
        ws[f"{C(c0 + 1)}{rr}"] = "=" + x(f"MAX(0,{{Vc}}-{{qu}}*{C(c0)}{rr})")
        ws[f"{C(c0 + 2)}{rr}"] = f"=${C(c0)}$5"
    ws[f"{C(c0)}22"] = "=" + x("{dc}/100")
    ws[f"{C(c0)}23"] = "=" + x("{dc}/100")
    ws[f"{C(c0 + 1)}22"] = 0
    ws[f"{C(c0 + 1)}23"] = "=" + x("{Vu}")
    ws[f"{C(c0)}25"] = "=" + x("{mac}")
    ws[f"{C(c0)}26"] = "=" + x("{mac}")
    ws[f"{C(c0 + 1)}25"] = 0
    ws[f"{C(c0 + 1)}26"] = "=" + x("{Vum}")
    ch3 = ScatterChart()
    ch3.title = "Cortante desde la cara de la viga"
    ch3.style = 13
    ch3.x_axis.title = "Distancia (m)"
    ch3.y_axis.title = "V (kg/m)"
    xs = Reference(ws, min_col=col0 + c0, min_row=10, max_row=20)
    for col, tit, color, dash in ((c0 + 1, f"${C(c0)}$7", "1F3864", None), (c0 + 2, f"${C(c0)}$6", "2E8B57", "dash")):
        s = Series(Reference(ws, min_col=col0 + col, min_row=10, max_row=20), xs)
        s.tx = SeriesLabel(strRef=StrRef(f"'{ws.title}'!{tit}"))
        s.graphicalProperties.line.solidFill = color
        s.graphicalProperties.line.width = 25000
        if dash:
            s.graphicalProperties.line.dashStyle = dash
        s.marker.symbol = "none"
        ch3.series.append(s)
    for r1, tit, color in ((22, "d", "7F7F7F"), (25, "Borde del macizado", "B7791F")):
        s = Series(Reference(ws, min_col=col0 + c0 + 1, min_row=r1, max_row=r1 + 1),
                   Reference(ws, min_col=col0 + c0, min_row=r1, max_row=r1 + 1), title=tit)
        s.graphicalProperties.line.solidFill = color
        s.graphicalProperties.line.dashStyle = "sysDot"
        s.marker.symbol = "circle"
        s.marker.size = 6
        ch3.series.append(s)
    _ejes(ch3)
    ch3.legend.position = "b"

    # --- aprovechamiento (columnas + línea de 100 %)
    c0 = 12
    filas = [("M+ corta", "{pc_uso}"), ("M+ larga", "{pl_uso}"), ("M− norte", "{nn_uso}"), ("M− sur", "{sn_uso}"),
             ("M− este", "{en_uso}"), ("M− oeste", "{on_uso}"), ("Cortante a d", "{vu}/{vcp}"),
             ("Cortante macizado", "{vum}/{vcp}"), ("Flecha viva", "{fL}/({Lx}*100/360)"),
             ("Flecha diferida", "{flp}/({Lx}*100/{den})"), ("Altura mínima", "{hmin}/{he}")]
    ws[f"{C(c0)}9"] = "Verificación"
    ws[f"{C(c0 + 1)}9"] = "Demanda / capacidad"
    ws[f"{C(c0 + 2)}9"] = "Límite 100 %"
    for n, (t, f) in enumerate(filas):
        rr = 10 + n
        ws[f"{C(c0)}{rr}"] = t
        ws[f"{C(c0 + 1)}{rr}"] = "=" + x(f)
        ws[f"{C(c0 + 1)}{rr}"].number_format = "0%"
        ws[f"{C(c0 + 2)}{rr}"] = 1
    last = 10 + len(filas) - 1
    bar = BarChart()
    bar.type = "col"
    bar.title = "Aprovechamiento: demanda / capacidad (cumple hasta 100 %)"
    bar.style = 10
    bar.add_data(Reference(ws, min_col=col0 + c0 + 1, min_row=9, max_row=last), titles_from_data=True)
    bar.set_categories(Reference(ws, min_col=col0 + c0, min_row=10, max_row=last))
    bar.series[0].graphicalProperties.solidFill = "3C9D5B"
    bar.y_axis.number_format = "0%"
    bar.y_axis.title = "%"
    line = LineChart()
    line.add_data(Reference(ws, min_col=col0 + c0 + 2, min_row=9, max_row=last), titles_from_data=True)
    line.series[0].graphicalProperties.line.solidFill = "C0392B"
    line.series[0].graphicalProperties.line.width = 22000
    line.series[0].marker.symbol = "none"
    bar += line
    _ejes(bar)
    bar.legend.position = "b"

    # --- sección a escala (contorno T de dos nervios + varillas)
    c0 = 16
    pts = ["(0,{h})", "(2*{s},{h})", "(2*{s},{hn})", "(1.5*{s}+{bw}/2,{hn})", "(1.5*{s}+{bw}/2,0)",
           "(1.5*{s}-{bw}/2,0)", "(1.5*{s}-{bw}/2,{hn})", "(0.5*{s}+{bw}/2,{hn})", "(0.5*{s}+{bw}/2,0)",
           "(0.5*{s}-{bw}/2,0)", "(0.5*{s}-{bw}/2,{hn})", "(0,{hn})", "(0,{h})"]
    for n, p in enumerate(pts):
        a, b_ = p[1:-1].split(",", 1)
        ws[f"{C(c0)}{10 + n}"] = "=" + x(a)
        ws[f"{C(c0 + 1)}{10 + n}"] = "=" + x(b_)
    # varillas inferiores (pos corta) y superiores (el mayor M− de bordes largos)
    sel = "IF({dirX},IF({on_Asu}>{en_Asu},{on_%s},{en_%s}),IF({sn_Asu}>{nn_Asu},{sn_%s},{nn_%s}))"
    sup_n, sup_phi = sel % (("n",) * 4), sel % (("phi",) * 4)
    for n, (xc, k) in enumerate((("0.5*{s}", -1), ("0.5*{s}", 1), ("1.5*{s}", -1), ("1.5*{s}", 1))):
        rr = 26 + n
        ws[f"{C(c0)}{rr}"] = "=" + x(f"{xc}+IF({{pc_n}}=2,{k}*MAX({{pc_phi}}/10+0.6,2.6)/2,0)")
        ws[f"{C(c0 + 1)}{rr}"] = "=" + x("{rec}+{pc_phi}/20")
        ws[f"{C(c0 + 2)}{rr}"] = "=" + x(f"{xc}+IF({sup_n}=2,{k}*MAX({sup_phi}/10+0.6,2.6)/2,0)")
        ws[f"{C(c0 + 3)}{rr}"] = "=" + x(f"{{h}}-{{rec}}-{sup_phi}/20")
    ws[f"{C(c0)}31"] = "=" + x('"Inferior "&{pc_arm}&" por nervio"')
    ws[f"{C(c0)}32"] = "=" + x('"Superior "&IF({dirX},IF({on_Asu}>{en_Asu},{on_arm},{en_arm}),'
                               'IF({sn_Asu}>{nn_Asu},{sn_arm},{nn_arm}))&" por nervio"')
    ws[f"{C(c0)}33"] = "=" + x('"Sección T: h = "&FIXED({h},0)&", loseta "&FIXED({el},0)&", bw "&FIXED({bw},0)&'
                               '" @ "&FIXED({s},0)&" cm"')
    ch5 = ScatterChart()
    ch5.title = "Sección de la losa a escala (cm)"
    ch5.style = 13
    s = Series(Reference(ws, min_col=col0 + c0 + 1, min_row=10, max_row=22),
               Reference(ws, min_col=col0 + c0, min_row=10, max_row=22))
    s.tx = SeriesLabel(strRef=StrRef(f"'{ws.title}'!${C(c0)}$33"))
    s.graphicalProperties.line.solidFill = "404040"
    s.graphicalProperties.line.width = 22000
    s.marker.symbol = "none"
    ch5.series.append(s)
    for xc, yc, tit, color in ((c0, c0 + 1, 31, "17804A"), (c0 + 2, c0 + 3, 32, "C25A14")):
        s = Series(Reference(ws, min_col=col0 + yc, min_row=26, max_row=29),
                   Reference(ws, min_col=col0 + xc, min_row=26, max_row=29))
        s.tx = SeriesLabel(strRef=StrRef(f"'{ws.title}'!${C(c0)}${tit}"))
        s.marker.symbol = "circle"
        s.marker.size = 9
        s.marker.graphicalProperties.solidFill = color
        s.marker.graphicalProperties.line.solidFill = color
        s.graphicalProperties.line.noFill = True
        ch5.series.append(s)
    ch5.x_axis.scaling.min = 0
    ch5.y_axis.scaling.min = 0
    _ejes(ch5)
    ch5.legend.position = "b"

    tam = [(ch5, "A", 17, 9), (bar, "C", 17, 9), (ch1, "A", 17, 8.5), (ch2, "C", 17, 8.5), (ch3, "A", 17, 8.5)]
    filas_ancla = [fila0, fila0, fila0 + 19, fila0 + 19, fila0 + 37]
    for (ch, col, w, h), f in zip(tam, filas_ancla):
        ch.width, ch.height = w, h
        ws.add_chart(ch, f"{col}{f}")


def _ejes(ch):
    """Muestra los ejes (openpyxl los oculta por defecto en versiones recientes) y quita el
    suavizado de las series que no son curvas."""
    for s in getattr(ch, "series", []):
        if not getattr(s, "_keep", 0):
            s.smooth = False
    for ax in (ch.x_axis, ch.y_axis):
        try:
            ax.delete = False
        except AttributeError:
            pass


# ------------------------------------------------------------------------------- RESUMEN
def _hoja_resumen(wb, g, grid, nombres) -> None:
    ws = wb.create_sheet("RESUMEN", 0)
    _celda(ws, "A1", "RESUMEN DEL PISO (fórmulas vivas)", FT, borde=False, al=Alignment(vertical="center"))
    _celda(ws, "A2", "Cambie los datos amarillos en DATOS o los bordes en la hoja de cada paño; esta tabla y el "
           "gráfico se actualizan solos.", FI, borde=False, al=Alignment(vertical="center"))
    enc = ["Paño", "Tipo", "Lx (m)", "Ly (m)", "Lx/Ly", "Inf. corta", "Inf. larga", "Sup. norte", "Sup. sur",
           "Sup. este", "Sup. oeste", "Flexión", "Cortante", "Flechas", "Altura", "RESULTADO",
           "Máx. flexión", "Máx. cortante", "Máx. flechas", "Altura / he"]
    for k, t in enumerate(enc, start=1):
        _celda(ws, f"{get_column_letter(k)}4", t, FN, CELESTE, CEN)
    r = 5
    for pid in grid:
        n = nombres[pid]
        q = lambda k: f"='{pid}'!{n[k]}"  # noqa: E731
        vals = [pid, q("tipo"), q("Lx"), q("Ly"), q("beta"), q("pc_arm"), q("pl_arm"), q("nn_arm"), q("sn_arm"),
                q("en_arm"), q("on_arm"), q("flex"), q("cort"), q("flech"), q("alt"), q("res"),
                f"=MAX('{pid}'!{n['pc_uso']},'{pid}'!{n['pl_uso']},'{pid}'!{n['nn_uso']},'{pid}'!{n['sn_uso']},"
                f"'{pid}'!{n['en_uso']},'{pid}'!{n['on_uso']})",
                f"='{pid}'!{n['vu']}/'{pid}'!{n['vcp']}",
                f"=MAX('{pid}'!{n['fL']}/('{pid}'!{n['Lx']}*100/360),'{pid}'!{n['flp']}/('{pid}'!{n['Lx']}*100/{g['den']}))",
                f"='{pid}'!{n['hmin']}/{g['he']}"]
        for k, v in enumerate(vals, start=1):
            c = _celda(ws, f"{get_column_letter(k)}{r}", v, FN if k in (1, 16) else F, al=CEN)
            if k in (3, 4):
                c.number_format = "0.00"
            if k == 5:
                c.number_format = "0.000"
            if k >= 17:
                c.number_format = "0%"
        r += 1
    _estado_cf(ws, f"L5:P{r - 1}")
    for k, (t, ref, fmt) in enumerate((("Geometría de nervios", g["geo"], "@"), ("qu (kg/m²)", g["qu"], "0.0"),
                                        ("Peso propio (kg/m²)", g["pp"], "0.0"), ("Altura h (cm)", g["h"], "0.0"))):
        fila = r + 1 + k
        ws.merge_cells(start_row=fila, start_column=1, end_row=fila, end_column=4)
        _celda(ws, f"A{fila}", t, FN)
        _celda(ws, f"E{fila}", "=" + ref, FN, fmt=fmt, al=CEN)
    _estado_cf(ws, f"E{r + 1}")
    bar = BarChart()
    bar.type = "col"
    bar.grouping = "clustered"
    bar.title = "Aprovechamiento máximo por paño (cumple hasta 100 %)"
    bar.style = 10
    bar.add_data(Reference(ws, min_col=17, max_col=20, min_row=4, max_row=r - 1), titles_from_data=True)
    bar.set_categories(Reference(ws, min_col=1, min_row=5, max_row=r - 1))
    bar.y_axis.number_format = "0%"
    for s, color in zip(bar.series, ("1F5F8B", "B7791F", "C0392B", "3C9D5B")):
        s.graphicalProperties.solidFill = color
    ws[f"V4"] = "Límite"
    for k in range(5, r):
        ws[f"V{k}"] = 1
    line = LineChart()
    line.add_data(Reference(ws, min_col=22, min_row=4, max_row=r - 1), titles_from_data=True)
    line.series[0].graphicalProperties.line.solidFill = "000000"
    line.series[0].marker.symbol = "none"
    bar += line
    _ejes(bar)
    bar.legend.position = "b"
    bar.width, bar.height = 26, 10
    ws.add_chart(bar, f"A{r + 6}")
    _pagina(ws, f"A1:T{r + 30}")
    _anchos(ws, [8, 6, 8, 8, 8, 11, 11, 11, 11, 11, 11, 11, 18, 11, 11, 20, 11, 11, 11, 11])


# ------------------------------------------------------------------------------- principal
def escribir_vivo(piso: Piso, ruta: str | Path) -> Path:
    if piso.losa.tipo != "nervada":
        raise ErrorEntrada("El Excel con fórmulas vivas cubre solo losas nervadas.")
    geometria.preparar(piso)
    X = list(piso.ejes_x.values())
    Y = list(piso.ejes_y.values())
    dx = [b - a for a, b in zip(X, X[1:])]
    dy = [b - a for a, b in zip(Y, Y[1:])]
    nx, ny = len(dx), len(dy)
    pos = {}
    for p in piso.panos:
        i = X.index(p.x0)
        j = Y.index(p.y0)
        if X.index(p.x1) != i + 1 or Y.index(p.y1) != j + 1:
            raise ErrorEntrada(f"Paño {p.id}: el Excel vivo requiere paños de un solo vano entre ejes vecinos.")
        pos[(i, j)] = p
    if len(pos) != nx * ny or piso.vigas_por_eje or any(p.volados for p in piso.panos):
        raise ErrorEntrada("El Excel vivo requiere una cuadrícula completa de paños, una sola sección de viga "
                           "y sin volados.")
    wb = Workbook()
    g = _hoja_datos(wb, piso, dx, dy)
    _hoja_tablas(wb)
    ids = {k: p.id for k, p in pos.items()}
    nombres = {}
    orden = [pos[(i, j)].id for j in range(ny) for i in range(nx)]
    for j in range(ny):
        for i in range(nx):
            p = pos[(i, j)]
            nombres[p.id] = _hoja_pano(wb, g, piso, p, i, j, nx, ny, ids)
    _hoja_resumen(wb, g, orden, nombres)
    wb._sheets = [wb["RESUMEN"], wb["DATOS"]] + [wb[i] for i in orden] + [wb["TABLAS"]]
    wb.active = 0
    wb.calculation.fullCalcOnLoad = True
    ruta = Path(ruta)
    ruta.parent.mkdir(parents=True, exist_ok=True)
    wb.save(ruta)
    return ruta
