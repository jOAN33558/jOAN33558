"""Excel del edificio con fórmulas vivas: varios pisos, cuadrícula ampliable y volados.

Hojas:
- DATOS: materiales, losa nervada, vigas y distancias entre ejes (hasta 8 ejes por dirección).
- PISOS: hasta 6 niveles con sus cargas (por ejemplo, oficinas y una terraza inaccesible).
- PLANTA: por paño, si existe, cambios de borde y volados (longitud y carga de borde).
- CALCULO: una fila por piso y paño con todo el diseño en fórmulas.
- RESUMEN: planta de cada piso con el tipo y el resultado de cada paño.
- MEMORIA: se elige piso y paño; muestra el cálculo paso a paso y los gráficos.
- TABLAS: Tabla 9.7 y tipos de paño.
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

NX = NY = 7               # vanos máximos por dirección (8 ejes)
NP = 6                    # pisos máximos
NC = NX * NY              # celdas por piso
FILA0 = 6                 # primera fila de datos en CALCULO
DIAM = [12, 14, 16, 18, 20]
AREA = {d: pi * (d / 10) ** 2 / 4 for d in DIAM}
OP = {"norte": "sur", "sur": "norte", "este": "oeste", "oeste": "este"}
LET = {"norte": "N", "sur": "S", "este": "E", "oeste": "O"}

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
LN = Side(style="thin", color="A6A6A6")
BRD = Border(left=LN, right=LN, top=LN, bottom=LN)
AJ = Alignment(wrap_text=True, vertical="top")
CEN = Alignment(horizontal="center", vertical="center", wrap_text=True)
LIB = Alignment(vertical="center")


def _cf(ws, rango):
    c0 = rango.split(":")[0].replace("$", "")
    for f, fondo, letra in ((f'ISNUMBER(SEARCH("NO CUMPLE",{c0}))', "FFC7CE", "9C0006"),
                            (f'ISNUMBER(SEARCH("FUERA",{c0}))', "FFEB9C", "7F6000"),
                            (f'ISNUMBER(SEARCH("macizado",{c0}))', "FFEB9C", "7F6000"),
                            (f'ISNUMBER(SEARCH("CUMPLE",{c0}))', "C6EFCE", "006100")):
        ws.conditional_formatting.add(rango, FormulaRule(
            formula=[f], stopIfTrue=True, fill=PatternFill("solid", fgColor=fondo, bgColor=fondo),
            font=Font(name=FUENTE, bold=True, color=letra)))


def _c(ws, ref, valor, fuente=F, relleno=None, al=AJ, borde=True, fmt=None):
    c = ws[ref]
    c.value = valor
    c.font, c.alignment = fuente, al
    if relleno:
        c.fill = relleno
    if borde:
        c.border = BRD
    if fmt:
        c.number_format = fmt
    return c


def _banda(ws, fila, texto, ncol):
    ws.merge_cells(start_row=fila, start_column=1, end_row=fila, end_column=ncol)
    c = ws.cell(fila, 1, texto)
    c.font, c.fill = FB, AZUL


def _anchos(ws, anchos, desde=1):
    for k, a in enumerate(anchos, start=desde):
        ws.column_dimensions[get_column_letter(k)].width = a


def _pagina(ws, area=None, horizontal=True):
    ws.page_setup.orientation = "landscape" if horizontal else "portrait"
    ws.page_setup.paperSize = ws.PAPERSIZE_A4
    ws.page_setup.fitToWidth, ws.page_setup.fitToHeight = 1, 0
    ws.sheet_properties.pageSetUpPr.fitToPage = True
    if area:
        ws.print_area = area


def _sel(need: str) -> tuple[str, str]:
    phi = "20"
    for d in reversed(DIAM):
        phi = f"IF({need}<={2 * AREA[d] + 1e-6:.6f},{d},{phi})"
    for d in reversed(DIAM):
        phi = f"IF({need}<={AREA[d] + 1e-6:.6f},{d},{phi})"
    return phi, f"IF({need}<={AREA[20] + 1e-6:.6f},1,2)"


# ===================================================================================== DATOS
def _datos(wb, piso: Piso, dx, dy) -> dict:
    ws = wb.create_sheet("DATOS")
    _anchos(ws, [46, 10, 14, 10, 50])
    _c(ws, "A1", "DATOS GENERALES (cambie las celdas amarillas)", FT, borde=False, al=LIB)
    _c(ws, "A2", "Materiales, losa, vigas y ejes son comunes a todos los pisos. Las cargas de cada piso van "
       "en la hoja PISOS.", FI, borde=False, al=LIB)
    g: dict[str, str] = {}
    fila = [4]

    def enc(t):
        _banda(ws, fila[0], t, 5)
        fila[0] += 1

    def sub(e):
        out, i = "", 0
        while i < len(e):
            if e[i] == "{":
                j = e.index("}", i)
                out += g[e[i + 1:j]]
                i = j + 1
            else:
                out += e[i]
                i += 1
        return out

    def d(nombre, concepto, valor, unidad, nota="", fmt="0.00", ent=False):
        r = fila[0]
        _c(ws, f"A{r}", concepto)
        _c(ws, f"B{r}", unidad, al=CEN)
        v = ("=" + sub(valor[1:])) if isinstance(valor, str) and valor.startswith("=") else valor
        _c(ws, f"C{r}", v, FN, AMARILLO if ent else None, Alignment(horizontal="right"), fmt=fmt)
        _c(ws, f"D{r}", "Dato" if ent else "", FI)
        _c(ws, f"E{r}", nota, FI)
        g[nombre] = f"DATOS!$C${r}"
        fila[0] += 1
        return r

    m, losa = piso.materiales, piso.losa
    enc("MATERIALES")
    d("fc", "Resistencia del hormigón f'c", m.fc, "kg/cm²", "", "0", True)
    d("fy", "Fluencia del acero fy", m.fy, "kg/cm²", "", "0", True)
    d("gam", "Peso específico del hormigón", m.peso_hormigon, "kg/m³", "", "0", True)
    d("rec", "Recubrimiento al borde de la varilla", m.recubrimiento, "cm", "", "0.0", True)
    d("Es", "Módulo de elasticidad del acero", m.Es, "kg/cm²", "", "0", True)
    d("E", "Módulo de elasticidad del hormigón", "=15000*SQRT({fc})", "kg/cm²", "15000·√f'c", "0")
    d("nmod", "Relación modular n", "={Es}/{E}", "", "Es/Ec")
    d("b1", "β1 del bloque de compresión", "=MAX(0.65,MIN(0.85,0.85-0.05*({fc}-280)/70))", "",
      "ACI 318-19, 22.2.2.4.3", "0.000")
    d("lam", "Factor de flecha diferida λΔ", piso.cargas.lambda_diferida, "", "ξ = 2 (5 años o más)", "0.0", True)
    enc("LOSA NERVADA (común a todos los pisos)")
    d("h", "Altura total h", losa.altura, "cm", "", "0.0", True)
    d("el", "Loseta el", losa.loseta, "cm", "", "0.0", True)
    d("bw", "Ancho de nervio bw", losa.ancho_nervio, "cm", "", "0.0", True)
    d("s", "Separación de nervios (eje a eje)", losa.separacion_nervios, "cm", "", "0.0", True)
    d("pb", "Peso de bloques", losa.peso_bloques, "kg/m²", "Corríjalo si cambia la altura del bloque", "0.0", True)
    d("mac", "Ancho de macizado junto a la viga", losa.macizado, "m", "", "0.000", True)
    d("hn", "Altura del nervio hn", "={h}-{el}", "cm", "h − el", "0.0")
    d("A", "Área de la sección T", "={s}*{el}+{bw}*{hn}", "cm²", "s·el + bw·hn")
    d("yg", "Centro de gravedad desde abajo", "=({bw}*{hn}*{hn}/2+{s}*{el}*({hn}+{el}/2))/{A}", "cm")
    d("Ig", "Inercia de la sección T", "={bw}*{hn}^3/12+{bw}*{hn}*({yg}-{hn}/2)^2+{s}*{el}^3/12+{s}*{el}*"
      "({hn}+{el}/2-{yg})^2", "cm4", "", "0")
    d("he", "Altura maciza equivalente he", "=(12*{Ig}/{s})^(1/3)", "cm", "(12·I/s)^(1/3)")
    d("bwm", "Ancho de nervios por metro", "={bw}*100/{s}", "cm/m", "ancho comprimido en M−")
    d("ploseta", "Peso de la loseta", "={el}/100*{gam}", "kg/m²")
    d("pnerv", "Peso de nervios (dos direcciones)", "=(2*(100/{s})*{bw}*{hn}/10000-(100/{s})^2*({bw}/100)^2*"
      "{hn}/100)*{gam}", "kg/m²")
    d("pp", "Peso propio de la losa", "={ploseta}+{pnerv}+{pb}", "kg/m²", "loseta + nervios + bloques")
    d("fac", "Factor de Vc en nervios", "=IF(AND({bw}>=10,{h}<=3.5*{bw},{s}-{bw}<=75),1.1,1)", "",
      "ACI 9.8.1.5", "0.0")
    d("vc0", "0,53·√f'c", "=0.53*SQRT({fc})", "kg/cm²")
    d("vc", "Esfuerzo resistente en nervios", "={fac}*{vc0}", "kg/cm²")
    r1 = d("geo1", "Nervios: bw >= 10 cm", '=IF({bw}>=10,"CUMPLE","NO CUMPLE")', "", "9.8.1.2", "@")
    d("geo2", "Nervios: h <= 3,5·bw", '=IF({h}<=3.5*{bw},"CUMPLE","NO CUMPLE")', "", "9.8.1.3", "@")
    d("geo3", "Nervios: separación libre <= 75 cm", '=IF({s}-{bw}<=75,"CUMPLE","NO CUMPLE")', "", "9.8.1.4", "@")
    r4 = d("geo4", "Loseta >= máx(5 ; libre/12)", '=IF({el}>=MAX(5,({s}-{bw})/12),"CUMPLE","NO CUMPLE")', "",
           "9.8.2", "@")
    d("geo", "Geometría de nervios", f'=IF(COUNTIF(C{r1}:C{r4},"NO*")=0,"CUMPLE","NO CUMPLE")', "", "", "@")
    _cf(ws, f"C{r1}:C{r4 + 1}")
    enc("VIGAS")
    d("vb", "Ancho de vigas b", piso.viga.b, "cm", "", "0.0", True)
    d("vh", "Altura de vigas h", piso.viga.h, "cm", "", "0.0", True)
    d("Iv", "Inercia de la viga", "={vb}*{vh}^3/12", "cm4", "b·h³/12", "0")
    enc("EJES: distancias en m (deje en blanco los que no use; sin huecos intermedios)")
    xs = []
    for k in range(NX):
        xs.append(d(f"dx{k}", f"X: eje {chr(65 + k)} a eje {chr(66 + k)}", dx[k] if k < len(dx) else None,
                    "m", "", "0.00", True))
    ys = []
    for k in range(NY):
        ys.append(d(f"dy{k}", f"Y: eje {k + 1} a eje {k + 2}", dy[k] if k < len(dy) else None, "m", "", "0.00", True))
    d("nx", "Vanos en X", f'=COUNTIF(C{xs[0]}:C{xs[-1]},">0")', "", "", "0")
    d("ny", "Vanos en Y", f'=COUNTIF(C{ys[0]}:C{ys[-1]},">0")', "", "", "0")
    ws.freeze_panes = "A4"
    _pagina(ws, horizontal=False)
    return g


# ===================================================================================== PISOS
def _pisos(wb, pisos: list[dict], g: dict) -> dict:
    ws = wb.create_sheet("PISOS")
    _anchos(ws, [6, 30, 10, 16, 14, 16, 12, 12, 12, 14, 10])
    _c(ws, "A1", "PISOS Y CARGAS (hasta 6 niveles)", FT, borde=False, al=LIB)
    _c(ws, "A2", "Active con SI los pisos que quiere calcular. La terraza inaccesible es un piso más con sus "
       "propias cargas.", FI, borde=False, al=LIB)
    enc = ["N.º", "Nombre del piso", "¿Calcular?", "Sobrecarga permanente (kg/m²)", "Carga viva (kg/m²)",
           "¿Soporta mampostería?", "D (kg/m²)", "1,4D", "1,2D+1,6L", "qu (kg/m²)", "L/... flecha"]
    for k, t in enumerate(enc, start=1):
        _c(ws, f"{get_column_letter(k)}4", t, FN, CELESTE, CEN)
    dv1 = DataValidation(type="list", formula1='"SI,NO"')
    ws.add_data_validation(dv1)
    f: dict[str, list[str]] = {k: [] for k in ("nom", "act", "sc", "viva", "mamp", "D", "qu", "den")}
    for p in range(NP):
        r = 5 + p
        dat = pisos[p] if p < len(pisos) else None
        _c(ws, f"A{r}", p + 1, al=CEN)
        _c(ws, f"B{r}", dat["nombre"] if dat else f"Piso {p + 1}", F, AMARILLO)
        _c(ws, f"C{r}", "SI" if dat else "NO", FN, AMARILLO, CEN)
        _c(ws, f"D{r}", dat["sc"] if dat else 0, F, AMARILLO, CEN, fmt="0.0")
        _c(ws, f"E{r}", dat["viva"] if dat else 0, F, AMARILLO, CEN, fmt="0.0")
        _c(ws, f"F{r}", ("SI" if dat["mamp"] else "NO") if dat else "SI", F, AMARILLO, CEN)
        _c(ws, f"G{r}", f"={g['pp']}+D{r}", al=CEN, fmt="0.0")
        _c(ws, f"H{r}", f"=1.4*G{r}", al=CEN, fmt="0.0")
        _c(ws, f"I{r}", f"=1.2*G{r}+1.6*E{r}", al=CEN, fmt="0.0")
        _c(ws, f"J{r}", f"=MAX(H{r},I{r})", FN, al=CEN, fmt="0.0")
        _c(ws, f"K{r}", f'=IF(UPPER(F{r})="SI",480,240)', al=CEN, fmt="0")
        dv1.add(f"C{r}")
        dv1.add(f"F{r}")
        for k, col in (("nom", "B"), ("act", "C"), ("sc", "D"), ("viva", "E"), ("mamp", "F"), ("D", "G"),
                       ("qu", "J"), ("den", "K")):
            f[k].append(f"PISOS!${col}${r}")
    _pagina(ws)
    return f


# ===================================================================================== PLANTA
def _planta(wb, piso: Piso, cel: dict) -> dict:
    """cel[(i, j)] = paño de la entrada o None."""
    ws = wb.create_sheet("PLANTA")
    _c(ws, "A1", "PLANTA: paños, bordes y volados (común a todos los pisos)", FT, borde=False, al=LIB)
    _c(ws, "A2", "Existe = NO para huecos o ductos. Borde 'auto' = continuo si hay paño vecino, discontinuo si "
       "no. Volado: longitud desde el eje de la viga (m) y carga de borde permanente (kg/m), p. ej. antepecho.",
       FI, borde=False, al=LIB)
    enc = ["Paño", "¿Existe?"] + [f"Borde {b}" for b in BORDES] + [f"Volado {b} (m)" for b in BORDES] + \
          [f"Carga borde {b} (kg/m)" for b in BORDES]
    for k, t in enumerate(enc, start=1):
        _c(ws, f"{get_column_letter(k)}4", t, FN, CELESTE, CEN)
    ws.row_dimensions[4].height = 30
    dv1 = DataValidation(type="list", formula1='"SI,NO"')
    dv2 = DataValidation(type="list", formula1='"auto,continuo,discontinuo,libre"')
    ws.add_data_validation(dv1)
    ws.add_data_validation(dv2)
    ref: dict = {}
    for j in range(NY):
        for i in range(NX):
            r = 5 + j * NX + i
            p = cel.get((i, j))
            _c(ws, f"A{r}", nombre(i, j), FN, al=CEN)
            existe = p is not None or (i, j) not in cel
            _c(ws, f"B{r}", "SI" if existe else "NO", F, AMARILLO, CEN)
            dv1.add(f"B{r}")
            for k, b in enumerate(BORDES):
                dec = p.bordes.get(b, "auto") if p else "auto"
                _c(ws, f"{get_column_letter(3 + k)}{r}", dec, F, AMARILLO, CEN)
                dv2.add(f"{get_column_letter(3 + k)}{r}")
                v = p.volado_en(b) if p else None
                lon = (v.longitud if v.medida == "eje" else v.longitud + piso.viga.b / 200) if v else None
                _c(ws, f"{get_column_letter(7 + k)}{r}", lon, F, AMARILLO, CEN, fmt="0.00")
                _c(ws, f"{get_column_letter(11 + k)}{r}", v.carga_borde if v else None, F, AMARILLO, CEN,
                   fmt="0")
            ref[(i, j)] = r
    _anchos(ws, [12, 9] + [12] * 4 + [11] * 8)
    ws.freeze_panes = "C5"
    _pagina(ws)
    return ref


def nombre(i, j):
    return f"{chr(65 + i)}-{chr(66 + i)}/{j + 1}-{j + 2}"


# ===================================================================================== TABLAS
def _tablas(wb):
    ws = wb.create_sheet("TABLAS")
    _c(ws, "A1", "Tabla 9.7 (losas nervadas) y tipo de paño según los bordes", FN, borde=False, al=LIB)
    for k, t in enumerate(["Tipo", "Lx/Ly", "δ", "my−", "my+", "mx−", "mx+", "myb−", "myb+", "mxb−", "mxb+"],
                          start=1):
        _c(ws, f"{get_column_letter(k)}2", t, FN, CELESTE, CEN)
    r = 3
    for tipo, filas in tablas.cargar("nervada").items():
        for f in sorted(filas, key=lambda x: -x["beta"]):
            for k, v in enumerate([tipo, f["beta"]] + [f[c] for c in tablas.COEFICIENTES], start=1):
                ws.cell(r, k, v).font = F
            r += 1
    _c(ws, "M2", "Clave", FN, CELESTE, CEN)
    _c(ws, "N2", "Tipo", FN, CELESTE, CEN)
    let = {"c": "continuo", "d": "discontinuo", "l": "libre"}
    r = 3
    for a in "cdl":
        for b in "cdl":
            for c in "cdl":
                for d in "cdl":
                    ws.cell(r, 13, a + b + c + d).font = F
                    ws.cell(r, 14, deducir_tipo((let[a], let[b]), (let[c], let[d])) or 0).font = F
                    r += 1
    _anchos(ws, [7, 7] + [8] * 9 + [3, 10, 7])


# ===================================================================================== CALCULO
class Fila:
    """Formulas de una fila de CALCULO, con referencias a la misma fila, a DATOS, al piso,
    a la planta y a los paños vecinos."""

    def __init__(self, cols, r, g, fp, pl, vec_rows):
        self.cols, self.r, self.g, self.fp, self.pl, self.vec = cols, r, g, fp, pl, vec_rows

    def x(self, e: str) -> str:
        out, i = "", 0
        while i < len(e):
            if e[i] != "{":
                out += e[i]
                i += 1
                continue
            j = e.index("}", i)
            tok = e[i + 1:j]
            i = j + 1
            if ":" in tok:
                k, n = tok.split(":", 1)
                if k == "D":
                    out += self.g[n]
                elif k == "F":
                    out += self.fp[n]
                elif k == "PL":
                    out += self.pl[n]
                else:                               # vecino: N, S, E, O
                    n, _, defecto = n.partition("|")
                    rr = self.vec.get(k)
                    out += f"${self.cols[n]}{rr}" if rr else (defecto or "0")
            else:
                out += f"${self.cols[tok]}{self.r}"
        return out


def _columnas():
    """Lista de (nombre, encabezado, fórmula, formato). Las fórmulas usan {nombre} de la misma
    fila, {D:x} de DATOS, {F:x} del piso, {PL:x} de PLANTA y {N:x|def} del vecino."""
    C = []

    def a(n, t, f, fmt="0.00"):
        C.append((n, t, f, fmt))

    # --------------------------------------------------- resumen visible (primeras columnas)
    a("piso", "Piso", "{F:nom}", "@")
    a("pano", "Paño", "{PL:nom}", "@")
    a("res", "RESULTADO", "", "@")
    a("tipo", "Tipo", "IF({ok},{tipo0},0)", "0")
    a("Lx", "Lx (m)", "MIN({W},{H})")
    a("Ly", "Ly (m)", "MAX({W},{H})")
    a("beta", "Lx/Ly", "IF({act},{Lx}/{Ly},0)", "0.000")
    for k, t in (("pc", "Inf. corta"), ("pl", "Inf. larga"), ("nn", "Sup. norte"), ("sn", "Sup. sur"),
                 ("en", "Sup. este"), ("on", "Sup. oeste")):
        a(k + "_arm", t, "", "@")
    a("flex", "Flexión", "", "@")
    a("cort", "Cortante", "", "@")
    a("flech", "Flechas", "", "@")
    a("alt", "Altura", "", "@")
    a("vols", "Volados", "", "@")
    a("aviso", "Avisos", "", "@")
    a("u_flex", "Máx. flexión", "", "0%")
    a("u_cort", "Máx. cortante", "", "0%")
    a("u_flech", "Máx. flechas", "", "0%")
    a("u_alt", "Altura mín./he", "IF({ok},{hmin}/{D:he},0)", "0%")
    # --------------------------------------------------- geometría y clasificación
    a("act", "Activo", "", "General")
    a("W", "W (m)", "", "0.00")
    a("H", "H (m)", "", "0.00")
    a("dirX", "Corta en X", "{W}<={H}", "General")
    for b in BORDES:
        L = LET[b]
        a(f"vec{L}", f"Vecino {b}", "", "General")
        a(f"vL{L}", f"Volado {b} (m)", f"IF({{act}},N({{PL:v{L}}}),0)", "0.00")
        a(f"vP{L}", f"Carga borde {b}", f"N({{PL:p{L}}})", "0")
        a(f"c{L}", f"Borde {b}", f'IF({{PL:o{L}}}<>"auto",{{PL:o{L}}},IF({{vL{L}}}>0,"discontinuo",'
                                 f'IF({{vec{L}}},"continuo","discontinuo")))', "@")
    a("clave", "Clave", 'IF({dirX},LEFT({cO},1)&LEFT({cE},1)&LEFT({cS},1)&LEFT({cN},1),'
                        'LEFT({cS},1)&LEFT({cN},1)&LEFT({cO},1)&LEFT({cE},1))', "@")
    a("tipo0", "Tipo tabla", "IFERROR(VLOOKUP({clave},TABLAS!$M$3:$N$83,2,FALSE),0)", "0")
    a("ok", "Calculado", "AND({act},{tipo0}>0,{beta}>=0.5)", "General")
    a("bc", "β cálculo", "MAX(0.5,MIN(1,ROUND({beta},6)))", "0.000")
    a("pos", "fila", "MATCH({bc},TABLAS!$B$3:$B$8,-1)", "0")
    a("pos2", "fila2", "MIN({pos}+1,6)", "0")
    a("t", "interp.", "IF({pos}={pos2},0,(INDEX(TABLAS!$B$3:$B$8,{pos})-{bc})/(INDEX(TABLAS!$B$3:$B$8,{pos})-"
                      "INDEX(TABLAS!$B$3:$B$8,{pos2})))", "0.000")
    for k, col in zip(tablas.COEFICIENTES, "CDEFGHIJK"):
        rg = f"TABLAS!${col}$3:${col}$110"
        f1 = f"INDEX({rg},({{tipo0}}-1)*6+{{pos}})"
        f2 = f"INDEX({rg},({{tipo0}}-1)*6+{{pos2}})"
        a(k, k, f"IF({{ok}},{f1}+({f2}-{f1})*{{t}},0)", "0.0")
    a("k", "0,0001·qu·Lx²", "0.0001*{F:qu}*{Lx}^2", "0.000")
    a("negC", "M− largo", "{k}*MAX({my_neg},{myb_neg})", "0")
    a("negL", "M− corto", "{k}*MAX({mx_neg},{mxb_neg})", "0")
    a("Mpc", "M+ corta", "{k}*MAX({my_pos},{myb_pos})", "0")
    a("Mpl", "M+ larga", "{k}*MAX({mx_pos},{mxb_pos})", "0")
    # --------------------------------------------------- volados (4 bordes)
    for b in BORDES:
        L = LET[b]
        a(f"Lc{L}", f"Volado {b}: L a la cara", f"IF({{vL{L}}}>0,{{vL{L}}}-{{D:vb}}/200,0)", "0.000")
        md = f"({{F:D}}*{{Lc{L}}}^2/2+{{vP{L}}}*{{Lc{L}}})"
        ml = f"({{F:viva}}*{{Lc{L}}}^2/2)"
        a(f"MuV{L}", f"Volado {b}: Mu", f"IF({{Lc{L}}}>0,MAX(1.4*{md},1.2*{md}+1.6*{ml}),0)", "0")
        vd = f"({{F:D}}*{{Lc{L}}}+{{vP{L}}})"
        a(f"VuV{L}", f"Volado {b}: Vu", f"IF({{Lc{L}}}>0,MAX(1.4*{vd},1.2*{vd}+1.6*{{F:viva}}*{{Lc{L}}}),0)", "0")
        a(f"quV{L}", f"Volado {b}: qu", f"IF(1.4*{md}>=1.2*{md}+1.6*{ml},1.4*{{F:D}},1.2*{{F:D}}+1.6*{{F:viva}})",
          "0.0")
    # --------------------------------------------------- momentos de borde y compatibilidad
    for b in BORDES:
        L = LET[b]
        lg = "{dirX}" if b in ("este", "oeste") else "NOT({dirX})"
        a(f"lg{L}", f"Borde {b} largo", lg, "General")
        a(f"Mb{L}", f"M− propio {b}", f'IF(AND({{ok}},{{c{L}}}="continuo"),IF({{lg{L}}},{{negC}},{{negL}}),0)', "0")
    for b in BORDES:
        L, O = LET[b], LET[OP[b]]
        a(f"Md{L}", f"M− diseño {b}", f'IF(OR(NOT({{ok}}),{{c{L}}}="libre"),0,MAX({{Mb{L}}},{{{L}:Mb{O}|0}},'
                                       f'{{MuV{L}}}))', "0")
    # --------------------------------------------------- flexión (tres pasadas de diámetros)
    casos = [("pc", "{Mpc}", "+", "TRUE"), ("pl", "{Mpl}", "+", "FALSE")]
    for b in BORDES:
        casos.append((b[0] + "n", f"{{Md{LET[b]}}}", "-", f"{{lg{LET[b]}}}"))

    def need(mu, d, bb):
        disc = f"({d}^2-2*{mu}*100/(0.9*0.85*{{D:fc}}*{bb}))"
        req = f"IF({mu}<=0,0,IF({disc}<0,99,0.85*{{D:fc}}*{bb}/{{D:fy}}*({d}-SQRT({disc}))))"
        mn = f"MAX(0.8*SQRT({{D:fc}}),14)/{{D:fy}}*{{D:bwm}}*{d}"
        return f"MAX({req},{mn})*{{D:s}}/100"

    for p, mu, sg, esc in casos:
        bb = "{D:bwm}" if sg == "-" else "100"
        a(p + "_d1", p + " d1", f"IF({esc},{{D:h}}-{{D:rec}}-0.6,{{D:h}}-{{D:rec}}-1.2-0.6)")
        a(p + "_f1", p + " Ø1", _sel(need(mu, "{" + p + "_d1}", bb))[0], "0")
    pc1 = "MAX(12," + ",".join(f"IF({esc},{{{p}_f1}},0)" for p, _, _, esc in casos) + ")"
    pl1 = "MAX(12," + ",".join(f"IF({esc},0,{{{p}_f1}})" for p, _, _, esc in casos) + ")"
    a("phic1", "Øc1", pc1, "0")
    a("phil1", "Øl1", pl1, "0")
    for p, mu, sg, esc in casos:
        bb = "{D:bwm}" if sg == "-" else "100"
        a(p + "_d2", p + " d2", f"IF({esc},{{D:h}}-{{D:rec}}-{{phic1}}/20,{{D:h}}-{{D:rec}}-{{phic1}}/10-{{phil1}}/20)")
        a(p + "_f2", p + " Ø2", _sel(need(mu, "{" + p + "_d2}", bb))[0], "0")
    a("phic", "Ø capa corta", "MAX({phic1}," + ",".join(f"IF({esc},{{{p}_f2}},0)" for p, _, _, esc in casos) + ")",
      "0")
    a("phil", "Ø capa larga", "MAX({phil1}," + ",".join(f"IF({esc},0,{{{p}_f2}})" for p, _, _, esc in casos) + ")",
      "0")
    a("dc", "d corta", "{D:h}-{D:rec}-{phic}/20")
    a("dl", "d larga", "{D:h}-{D:rec}-{phic}/10-{phil}/20")
    for p, mu, sg, esc in casos:
        bb = "{D:bwm}" if sg == "-" else "100"
        bcomp = "{D:bw}" if sg == "-" else "{D:s}"
        lim = "{D:hn}" if sg == "-" else "{D:el}"
        a(p + "_Mu", p + " Mu", mu, "0")
        a(p + "_d", p + " d", f"IF({esc},{{dc}},{{dl}})")
        disc = f"({{{p}_d}}^2-2*{{{p}_Mu}}*100/(0.9*0.85*{{D:fc}}*{bb}))"
        a(p + "_req", p + " As req", f"IF({{{p}_Mu}}<=0,0,IF({disc}<0,-1,0.85*{{D:fc}}*{bb}/{{D:fy}}*({{{p}_d}}-"
                                     f"SQRT({disc}))))", "0.000")
        a(p + "_min", p + " As mín", f"MAX(0.8*SQRT({{D:fc}}),14)/{{D:fy}}*{{D:bwm}}*{{{p}_d}}", "0.000")
        a(p + "_dis", p + " As diseño", f"MAX({{{p}_req}},{{{p}_min}})", "0.000")
        a(p + "_nec", p + " As nervio", f"{{{p}_dis}}*{{D:s}}/100", "0.000")
        phi, n = _sel("{" + p + "_nec}")
        a(p + "_phi", p + " Ø", phi, "0")
        a(p + "_n", p + " n", n, "0")
        a(p + "_Asu", p + " As col.", f"{{{p}_n}}*PI()*({{{p}_phi}}/10)^2/4", "0.000")
        a(p + "_a", p + " a", f"{{{p}_Asu}}*{{D:fy}}/(0.85*{{D:fc}}*{bcomp})")
        a(p + "_eps", p + " εt", f"0.003*({{{p}_d}}-{{{p}_a}}/{{D:b1}})/({{{p}_a}}/{{D:b1}})", "0.0000")
        a(p + "_lim", p + " a lím", lim)
        ok = (f"AND({{{p}_req}}>=0,{{{p}_nec}}<={2 * AREA[20] + 1e-6:.6f},{{{p}_a}}<={lim},"
              f"{{{p}_eps}}>=0.005)")
        a(p + "_est", p + " estado", f'IF(NOT({{ok}}),"-",IF({ok},"CUMPLE","NO CUMPLE"))', "@")
        a(p + "_uso", p + " uso", f"IF({{ok}},{{{p}_dis}}/({{{p}_Asu}}*100/{{D:s}}),0)", "0%")
        if p in ("pc", "pl"):
            arm = f'IF({{ok}},{{{p}_n}}&"Ø"&{{{p}_phi}}&IF({{{p}_Mu}}<=0," (mín.)",""),"-")'
        else:
            L = LET[{"n": "norte", "s": "sur", "e": "este", "o": "oeste"}[p[0]]]
            arm = (f'IF(OR(NOT({{ok}}),{{c{L}}}="libre"),"-",{{{p}_n}}&"Ø"&{{{p}_phi}}&'
                   f'IF({{{p}_Mu}}<=0," (mín.)",""))')
        C[[c[0] for c in C].index(p + "_arm")] = (p + "_arm", C[[c[0] for c in C].index(p + "_arm")][1], arm,
                                                   "@")
    # --------------------------------------------------- cortante
    a("unap", "Borde largo libre", 'IF({dirX},OR({cO}="libre",{cE}="libre"),OR({cS}="libre",{cN}="libre"))',
      "General")
    a("Vc", "V cara", "{F:qu}*(IF({unap},{Lx},{Lx}/2)-{D:vb}/200)", "0")
    a("Vu", "Vu a d", "MAX(0,{Vc}-{F:qu}*{dc}/100)", "0")
    a("vu", "vu", "{Vu}/(0.75*{D:bwm}*{dc})")
    a("Vum", "Vu macizado", "MAX(0,{Vc}-{F:qu}*{D:mac})", "0")
    a("vum", "vu macizado", "{Vum}/(0.75*{D:bwm}*{dc})")
    a("vus", "vu zona maciza", "{Vu}/(0.75*100*{dc})")
    a("cortP", "Cortante paño", 'IF({vu}<={D:vc},"CUMPLE",IF(AND({vum}<={D:vc},{vus}<={D:vc0},{D:mac}*100>{dc}),'
                                '"CUMPLE con macizado","NO CUMPLE"))', "@")
    # --------------------------------------------------- flechas del paño
    a("mp", "m+", "MAX({my_pos},{myb_pos})", "0.0")
    a("kd", "kd", "0.0001*{delta}*({Lx}*100)^4/({D:E}*{D:he}^3)/10000", "0.0000000")
    a("kM", "kM", "0.0001*{mp}*{Lx}^2*{D:s}", "0.000")
    a("nAs", "n·As", "{D:nmod}*{pc_Asu}", "0.000")
    c1 = "(-{nAs}+SQRT({nAs}^2+2*{D:s}*{nAs}*{pc_d}))/{D:s}"
    Bq = "(({D:s}-{D:bw})*{D:el}+{nAs})"
    Cq = "(-(({D:s}-{D:bw})*{D:el}^2/2+{nAs}*{pc_d}))"
    c2 = f"(-{Bq}+SQRT({Bq}^2-4*({{D:bw}}/2)*{Cq}))/(2*({{D:bw}}/2))"
    a("cf", "c fisurado", f"IF({c1}<={{D:el}},{c1},{c2})")
    a("Icr", "Icr", "MIN({D:Ig},{D:s}*{cf}^3/3+{nAs}*({pc_d}-{cf})^2-IF({cf}>{D:el},({D:s}-{D:bw})*({cf}-{D:el})^3/3,"
                    "0))", "0")
    a("Mcr", "Mcr", "2*SQRT({D:fc})*{D:Ig}/{D:yg}", "0")
    for nom, q in (("D", "{F:D}"), ("DL", "({F:D}+{F:viva})")):
        a("Ma" + nom, "Ma " + nom, f"{{kM}}*{q}", "0")
        a("Ie" + nom, "Ie " + nom, f"IF({{Ma{nom}}}<=2/3*{{Mcr}},{{D:Ig}},{{Icr}}/(1-((2/3)*{{Mcr}}/{{Ma{nom}}})^2*"
                                   f"(1-{{Icr}}/{{D:Ig}})))", "0")
        a("f" + nom, "Δ " + nom, f"{{kd}}*{q}*{{D:Ig}}/{{Ie{nom}}}", "0.000")
    a("fL", "Δ viva", "ABS({fDL}-{fD})", "0.000")
    a("flp", "Δ diferida", "{D:lam}*ABS({fD})+{fL}", "0.000")
    a("limL", "Lx/360", "{Lx}*100/360", "0.000")
    a("limP", "Lx/den", "{Lx}*100/{F:den}", "0.000")
    # --------------------------------------------------- altura mínima
    for b in BORDES:
        L = LET[b]
        propio = "{H}" if b in ("norte", "sur") else "{W}"
        otro = f"{{{L}:{'H' if b in ('norte', 'sur') else 'W'}|0}}"
        ancho = (f"IF({{vL{L}}}>0,{propio}*100/2+{{vL{L}}}*100,IF({{vec{L}}},({propio}*100+{otro}*100)/2,"
                 f"({propio}*100+{{D:vb}})/2))")
        a(f"al{L}", f"α {b}", f'IF({{c{L}}}="libre",0,{{D:Iv}}/({{D:Ig}}*{ancho}/{{D:s}}))', "0.000")
    a("am", "αm", "AVERAGE({alN},{alS},{alE},{alO})", "0.000")
    a("bt", "β luces libres", "({Ly}*100-{D:vb})/({Lx}*100-{D:vb})", "0.000")
    a("h0", "hmín base", "IF({am}>2,MAX(9,({Ly}*100-{D:vb})*(0.8+{D:fy}/14000)/(36+9*{bt})),MAX(12.5,({Ly}*100-"
                         "{D:vb})*(0.8+{D:fy}/14000)/(36+5*{bt}*({am}-0.2))))")
    deb = ",".join(f'AND({{c{LET[b]}}}<>"continuo",{{al{LET[b]}}}<0.8)' for b in BORDES)
    a("hmin", "hmín", f"{{h0}}*IF(OR({deb}),1.1,1)")
    # --------------------------------------------------- verificaciones de volados
    for b in BORDES:
        L, p = LET[b], b[0] + "n"
        a(f"hV{L}", f"Volado {b}: hmín", f"{{Lc{L}}}*100/8*(0.4+{{D:fy}}/7000)")
        a(f"VdV{L}", f"Volado {b}: Vu a d", f"MAX(0,{{VuV{L}}}-{{quV{L}}}*{{{p}_d}}/100)", "0")
        a(f"vV{L}", f"Volado {b}: vu", f"{{VdV{L}}}/(0.75*{{D:bwm}}*{{{p}_d}})")
        a(f"vmV{L}", f"Volado {b}: vu mac", f"MAX(0,{{VuV{L}}}-{{quV{L}}}*{{D:mac}})/(0.75*{{D:bwm}}*{{{p}_d}})")
        a(f"ctV{L}", f"Volado {b}: cortante",
          f'IF({{vV{L}}}<={{D:vc}},"CUMPLE",IF(AND({{vmV{L}}}<={{D:vc}},{{VdV{L}}}/(0.75*100*{{{p}_d}})<={{D:vc0}},'
          f'{{D:mac}}*100>{{{p}_d}}),"CUMPLE con macizado","NO CUMPLE"))', "@")
        # flecha en la punta, sección fisurada a momento negativo
        nas = f"({{D:nmod}}*{{{p}_Asu}})"
        cneg = f"(-{nas}+SQRT({nas}^2+2*{{D:bw}}*{nas}*{{{p}_d}}))/{{D:bw}}"
        a(f"IcV{L}", f"Volado {b}: Icr", f"MIN({{D:Ig}},{{D:bw}}*({cneg})^3/3+{nas}*({{{p}_d}}-({cneg}))^2)", "0")
        a(f"McV{L}", f"Volado {b}: Mcr", "2*SQRT({D:fc})*{D:Ig}/({D:h}-{D:yg})", "0")
        EI = "({D:E}*{D:Ig}*100/{D:s})"
        Lcm = f"({{Lc{L}}}*100)"
        for nom, q in (("D", "{F:D}"), ("DL", "({F:D}+{F:viva})")):
            a(f"MaV{L}{nom}", f"Volado {b}: Ma {nom}", f"({q}*{{Lc{L}}}^2/2+{{vP{L}}}*{{Lc{L}}})*{{D:s}}", "0")
            a(f"IeV{L}{nom}", f"Volado {b}: Ie {nom}",
              f"IF({{MaV{L}{nom}}}<=2/3*{{McV{L}}},{{D:Ig}},{{IcV{L}}}/(1-((2/3)*{{McV{L}}}/{{MaV{L}{nom}}})^2*"
              f"(1-{{IcV{L}}}/{{D:Ig}})))", "0")
            a(f"fV{L}{nom}", f"Volado {b}: Δ {nom}",
              f"IF({{Lc{L}}}>0,(({q}/100)*{Lcm}^4/(8*{EI})+{{vP{L}}}*{Lcm}^3/(3*{EI}))*{{D:Ig}}/{{IeV{L}{nom}}},0)",
              "0.0000")
        a(f"fLV{L}", f"Volado {b}: Δ viva", f"ABS({{fV{L}DL}}-{{fV{L}D}})", "0.0000")
        a(f"fpV{L}", f"Volado {b}: Δ diferida", f"{{D:lam}}*ABS({{fV{L}D}})+{{fLV{L}}}", "0.0000")
        a(f"flV{L}", f"Volado {b}: flechas",
          f'IF(AND({{fLV{L}}}<={Lcm}/360,{{fpV{L}}}<={Lcm}/{{F:den}}),"CUMPLE","NO CUMPLE")', "@")
        Lb = "{H}" if b in ("norte", "sur") else "{W}"
        Lo = "{W}" if b in ("norte", "sur") else "{H}"
        a(f"x0V{L}", f"Volado {b}: punto de inflexión",
          f"IF({{Lc{L}}}>0,MIN(2*{{MuV{L}}}/(0.9*{{F:D}}*{Lo}^4/({Lb}^4+{Lo}^4)*{Lb}),{Lb}),0)", "0.000")
        a(f"ldV{L}", f"Volado {b}: ld (cm)",
          f"MAX({{D:fy}}/(IF({{{p}_phi}}<=19,6.6,5.3)*SQRT({{D:fc}}))*{{{p}_phi}}/10,30)", "0.0")
        a(f"prV{L}", f"Volado {b}: prolongación (m)",
          f"IF({{Lc{L}}}>0,MIN(MAX({{x0V{L}}}+MAX({{{p}_d}}/100,12*{{{p}_phi}}/1000,({Lb}-{{D:vb}}/100)/16),"
          f"{{ldV{L}}}/100),{Lb}),0)", "0.00")
        a(f"stV{L}", f"Volado {b}: estado",
          f'IF({{Lc{L}}}<=0,"",IF(AND({{D:h}}>={{hV{L}}},LEFT({{ctV{L}}},6)="CUMPLE",{{flV{L}}}="CUMPLE",'
          f'{{{p}_est}}="CUMPLE"),"CUMPLE","NO CUMPLE"))', "@")
    return C


def _rellenar_resumen(C):
    """Fórmulas de las columnas de resumen, que dependen de las demás."""
    d = {c[0]: i for i, c in enumerate(C)}

    def put(n, f):
        C[d[n]] = (n, C[d[n]][1], f, C[d[n]][3])

    casos = ["pc", "pl", "nn", "sn", "en", "on"]
    put("flex", 'IF(NOT({ok}),"-",IF(AND(' + ",".join(f'{{{p}_est}}="CUMPLE"' for p in casos) +
        '),"CUMPLE","NO CUMPLE"))')
    put("cort", 'IF(NOT({ok}),"-",{cortP})')
    put("flech", 'IF(NOT({ok}),"-",IF(AND({fL}<={limL},{flp}<={limP}),"CUMPLE","NO CUMPLE"))')
    put("alt", 'IF(NOT({ok}),"-",IF({D:he}>={hmin},"CUMPLE","NO CUMPLE"))')
    put("vols", 'IF(NOT({ok}),"-",IF(OR(' + ",".join(f'{{stV{L}}}="NO CUMPLE"' for L in "NSEO") +
        '),"NO CUMPLE",IF(OR(' + ",".join(f'{{stV{L}}}="CUMPLE"' for L in "NSEO") + '),"CUMPLE","sin volados")))')
    put("aviso", 'IF(NOT({act}),"",IF(NOT({ok}),IF({beta}<0.5,"FUERA DE ALCANCE: Lx/Ly < 0,5 (una dirección); '
        'use el programa","FUERA DE ALCANCE: combinación de bordes no tabulada"),"")&' +
        "&".join(f'IF(AND({{vL{L}}}>0,{{vec{L}}})," Volado {b} con paño vecino: revise.","")'
                 for b, L in LET.items()) + ")")
    put("u_flex", "IF({ok},MAX(" + ",".join(f"IF({{{p}_Mu}}>0,{{{p}_uso}},0)" for p in casos) + "),0)")
    put("u_cort", "IF({ok},MAX({vu}/{D:vc}," + ",".join(f"{{vV{L}}}/{{D:vc}}" for L in "NSEO") + "),0)")
    put("u_flech", "IF({ok},MAX({fL}/{limL},{flp}/{limP}," +
        ",".join(f"IF({{Lc{L}}}>0,{{fpV{L}}}/({{Lc{L}}}*100/{{F:den}}),0)" for L in "NSEO") + "),0)")
    put("res", 'IF(NOT({act}),"",IF(NOT({ok}),"FUERA DE ALCANCE",IF(AND({flex}="CUMPLE",LEFT({cort},6)="CUMPLE",'
        '{flech}="CUMPLE",{alt}="CUMPLE",{vols}<>"NO CUMPLE",{D:geo}="CUMPLE"),IF({cort}="CUMPLE","CUMPLE",'
        '"CUMPLE con macizado"),"NO CUMPLE")))')


def _calculo(wb, g, fp, pref):
    ws = wb.create_sheet("CALCULO")
    C = _columnas()
    _rellenar_resumen(C)
    cols = {n: get_column_letter(k + 1) for k, (n, *_) in enumerate(C)}
    _c(ws, "A1", "CÁLCULO DE TODOS LOS PAÑOS DE TODOS LOS PISOS (fórmulas; no editar)", FT, borde=False, al=LIB)
    _c(ws, "A2", "Las primeras columnas son el resumen de armado (varillas por nervio). Use el filtro de la fila 5 "
       "para ver un piso o solo los paños activos.", FI, borde=False, al=LIB)
    for k, (n, t, f, fmt) in enumerate(C, start=1):
        _c(ws, f"{get_column_letter(k)}5", t, FN, CELESTE, CEN)
    ws.row_dimensions[5].height = 42
    last = FILA0 + NP * NC - 1
    for p in range(NP):
        fpp = {k: v[p] for k, v in fp.items()}
        for j in range(NY):
            for i in range(NX):
                r = FILA0 + p * NC + j * NX + i
                pr = pref[(i, j)]
                pl = {"nom": f"PLANTA!$A${pr}", "ex": f"PLANTA!$B${pr}"}
                for k, b in enumerate(BORDES):
                    L = LET[b]
                    pl["o" + L] = f"PLANTA!${get_column_letter(3 + k)}${pr}"
                    pl["v" + L] = f"PLANTA!${get_column_letter(7 + k)}${pr}"
                    pl["p" + L] = f"PLANTA!${get_column_letter(11 + k)}${pr}"
                vec = {}
                if j + 1 < NY:
                    vec["N"] = r + NX
                if j > 0:
                    vec["S"] = r - NX
                if i + 1 < NX:
                    vec["E"] = r + 1
                if i > 0:
                    vec["O"] = r - 1
                fl = Fila(cols, r, g, fpp, pl, vec)
                especiales = {
                    "act": f'AND({i}<{g["nx"]},{j}<{g["ny"]},UPPER({pl["ex"]})="SI",UPPER({fpp["act"]})="SI")',
                    "W": f"N({g[f'dx{i}']})", "H": f"N({g[f'dy{j}']})",
                }
                for b in BORDES:
                    L = LET[b]
                    especiales[f"vec{L}"] = f"${cols['act']}{vec[L]}" if L in vec else "FALSE"
                for k, (n, t, f, fmt) in enumerate(C, start=1):
                    expr = especiales.get(n, f)
                    c = ws.cell(r, k, "=" + fl.x(expr) if expr else None)
                    c.number_format = fmt
                    c.font = F
    first = len([c for c in C if c[0] in ("piso", "pano", "res", "tipo", "Lx", "Ly", "beta")]) + 13
    ws.auto_filter.ref = f"A5:{get_column_letter(len(C))}{last}"
    _cf(ws, f"C{FILA0}:C{last}")
    _cf(ws, f"{cols['flex']}{FILA0}:{cols['vols']}{last}")
    ws.freeze_panes = "C6"
    _anchos(ws, [24, 12, 20, 6, 7, 7, 7] + [11] * 6 + [11, 18, 11, 11, 11, 40] + [9] * 4)
    for k in range(first + 6, len(C) + 1):
        ws.column_dimensions[get_column_letter(k)].outlineLevel = 1
        ws.column_dimensions[get_column_letter(k)].width = 10
    _pagina(ws, f"A1:{cols['u_alt']}{last}")
    return cols


# ===================================================================================== RESUMEN
def _resumen(wb, g, fp, cols):
    ws = wb.create_sheet("RESUMEN", 0)
    _c(ws, "A1", "RESUMEN DEL EDIFICIO (todo se recalcula solo)", FT, borde=False, al=LIB)
    _c(ws, "A2", "Planta de cada piso: cada celda es un paño (norte arriba). Cambie datos en DATOS, PISOS o PLANTA; "
       "para ver un paño en detalle use la hoja MEMORIA.", FI, borde=False, al=LIB)
    fila = 4
    for p in range(NP):
        ws.merge_cells(start_row=fila, start_column=1, end_row=fila, end_column=NX + 2)
        c = ws.cell(fila, 1)
        rng = lambda col: f"CALCULO!${col}${FILA0 + p * NC}:${col}${FILA0 + p * NC + NC - 1}"  # noqa: E731
        c.value = (f'=IF(UPPER({fp["act"][p]})="SI","PISO "&{p + 1}&": "&{fp["nom"][p]}&"   -   qu = "&'
                   f'FIXED({fp["qu"][p]},0)&" kg/m²   -   cumplen "&COUNTIF({rng(cols["res"])},"CUMPLE*")&" de "&'
                   f'COUNTIF({rng(cols["res"])},"?*")&" paños","PISO "&{p + 1}&": no se calcula (actívelo en PISOS)")')
        c.font, c.fill = FB, AZUL
        fila += 1
        for jj in range(NY):
            j = NY - 1 - jj
            r = fila + jj
            ws.cell(r, 1, f'=IF({j}<{g["ny"]},"eje {j + 1}-{j + 2}","")').font = FI
            for i in range(NX):
                cr = FILA0 + p * NC + j * NX + i
                q = lambda n: f"CALCULO!${cols[n]}${cr}"  # noqa: E731
                cel = ws.cell(r, 2 + i)
                cel.value = (f'=IF({q("act")},{q("pano")}&CHAR(10)&IF({q("ok")},"Tipo "&{q("tipo")},"")&CHAR(10)&'
                             f'{q("res")},"")')
                cel.font = Font(name=FUENTE, size=8)
                cel.alignment = CEN
                cel.border = BRD
            ws.row_dimensions[r].height = 40
        _cf(ws, f"B{fila}:{get_column_letter(NX + 1)}{fila + NY - 1}")
        fila += NY + 1
    _anchos(ws, [11] + [17] * NX)
    _pagina(ws)


# ===================================================================================== MEMORIA
def _memoria(wb, g, fp, cols, nombres_pisos):
    ws = wb.create_sheet("MEMORIA", 1)
    _anchos(ws, [44, 40, 44, 15, 10, 30, 28])
    _c(ws, "A1", "MEMORIA DE UN PAÑO (elija el piso y el paño en las celdas amarillas)", FT, borde=False, al=LIB)
    _c(ws, "A3", "Piso", FN)
    _c(ws, "B3", nombres_pisos[0], FN, AMARILLO, CEN)
    _c(ws, "A4", "Paño", FN)
    _c(ws, "B4", nombre(0, 0), FN, AMARILLO, CEN)
    dv = DataValidation(type="list", formula1=f"=PISOS!$B$5:$B${4 + NP}")
    dv2 = DataValidation(type="list", formula1=f"=PLANTA!$A$5:$A${4 + NC}")
    ws.add_data_validation(dv)
    ws.add_data_validation(dv2)
    dv.add("B3")
    dv2.add("B4")
    _c(ws, "C3", "Fila en CALCULO", FI)
    ws["D3"] = f'=(MATCH(B3,PISOS!$B$5:$B${4 + NP},0)-1)*{NC}+MATCH(B4,PLANTA!$A$5:$A${4 + NC},0)'
    _c(ws, "C4", "RESULTADO", FN)
    ws.merge_cells("D4:F4")
    sel = "$D$3"
    pidx = f"(MATCH($B$3,PISOS!$B$5:$B${4 + NP},0))"

    def v(n):
        col = cols[n]
        return f"INDEX(CALCULO!${col}${FILA0}:${col}${FILA0 + NP * NC - 1},{sel})"

    def fpv(k):
        col = fp[k][0].split("$")[1]
        return f"INDEX(PISOS!${col}$5:${col}${4 + NP},{pidx})"

    _c(ws, "D4", "=" + v("res"), FN, al=CEN)
    _c(ws, "A6", "Los gráficos y la memoria cambian al elegir otro piso o paño, o al cambiar cualquier dato.",
       FI, borde=False, al=LIB)
    _cf(ws, "D4")
    fila = [62]
    hdr = ["Concepto", "Fórmula", "Sustitución", "Resultado", "Unidad", "Verificación", "Referencia"]

    def seccion(t):
        _banda(ws, fila[0], t, 7)
        fila[0] += 1

    def paso(concepto, formula, sust, res, unidad="", verif="", ref="", fmt="0.00"):
        r = fila[0]
        vals = [concepto, formula, ("=" + sust) if sust else "", ("=" + res) if res else "", unidad,
                ("=" + verif) if verif else "", ref]
        for k, x in enumerate(vals, start=1):
            cc = _c(ws, f"{get_column_letter(k)}{r}", x)
            if k == 4:
                cc.font, cc.number_format = FN, fmt
                cc.alignment = Alignment(horizontal="right", vertical="top")
        _cf(ws, f"F{r}")
        fila[0] += 1

    for k, t in enumerate(hdr, start=1):
        _c(ws, f"{get_column_letter(k)}{fila[0]}", t, FN, CELESTE, CEN)
    fila[0] += 1
    X = lambda n, nd=2: f"FIXED({v(n)},{nd})"  # noqa: E731
    seccion("1. GEOMETRÍA, CARGAS Y CLASIFICACIÓN")
    paso("Piso y carga de diseño", "qu = máx(1,4D ; 1,2D + 1,6L)",
         f'"D = "&FIXED({fpv("D")},1)&" ; L = "&FIXED({fpv("viva")},0)', fpv("qu"), "kg/m²", "", "NEC-SE-CG", "0.0")
    paso("Luces del paño", "W × H (centro a centro)", f'{X("W")}&" × "&{X("H")}', v("Lx"), "m (Lx)")
    paso("Relación de luces", "Lx/Ly", f'{X("Lx")}&"/"&{X("Ly")}', v("beta"), "",
         f'IF({v("beta")}>=0.5,"CUMPLE: dos direcciones","NO CUMPLE: una dirección")', "", "0.000")
    paso("Bordes", "N / S / E / O", f'{v("cN")}&" / "&{v("cS")}&" / "&{v("cE")}&" / "&{v("cO")}', v("tipo"),
         "tipo", f'IF({v("ok")},"CUMPLE","NO CUMPLE: fuera de alcance")', "Tabla 9.7", "0")
    seccion("2. MOMENTOS (M = 0,0001·qu·m·Lx²) Y COMPATIBILIDAD")
    for n, t in (("Mpc", "M+ dirección corta"), ("Mpl", "M+ dirección larga"), ("negC", "M− bordes largos (propio)"),
                 ("negL", "M− bordes cortos (propio)")):
        paso(t, "0,0001·qu·m·Lx²", "", v(n), "kg·m/m", "", "Tabla 9.7", "0")
    for b in BORDES:
        L = LET[b]
        paso(f"M− de diseño borde {b}", "máx(propio ; vecino ; volado)",
             f'"propio "&FIXED({v("Mb" + L)},0)&" ; volado "&FIXED({v("MuV" + L)},0)', v("Md" + L), "kg·m/m",
             "", "Compatibilidad", "0")
    seccion("3. FLEXIÓN (varillas por nervio; M+ con b = 100 cm, M− con bw·100/s)")
    for p, t in (("pc", "M+ corta"), ("pl", "M+ larga"), ("nn", "M− norte"), ("sn", "M− sur"), ("en", "M− este"),
                 ("on", "M− oeste")):
        paso(f"{t}: Mu", "As = 0,85·f'c·b/fy·[d − √(d² − 2Mu/(φ·0,85·f'c·b))]",
             f'"Mu = "&{X(p + "_Mu", 0)}&" ; d = "&{X(p + "_d")}&" ; As req = "&{X(p + "_req", 3)}&" ; As mín = "&'
             f'{X(p + "_min", 3)}', v(p + "_arm"), "",
             f'{v(p + "_est")}&" (a = "&{X(p + "_a")}&" ; εt = "&{X(p + "_eps", 4)}&")"', "ACI 318-19, 22.2", "@")
    seccion("4. CORTANTE (solo nervios)")
    paso("Cortante en la cara", "qu·(Lx/2 − b/2)", "", v("Vc"), "kg/m", "", "", "0")
    paso("Esfuerzo a la distancia d", "Vu/(0,75·bw·100/s·d)", f'"Vu = "&{X("Vu", 0)}', v("vu"), "kg/cm²",
         f'{v("cortP")}&" (vc = "&FIXED({g["vc"]},2)&")"', "ACI 9.8.1.5")
    seccion("5. FLECHAS (inercia efectiva)")
    paso("Flecha por carga viva", "Δ(D+L) − Δ(D)", f'"límite Lx/360 = "&{X("limL", 3)}', v("fL"), "cm",
         f'IF({v("fL")}<={v("limL")},"CUMPLE","NO CUMPLE")', "ACI Tabla 24.2.2", "0.000")
    paso("Flecha diferida + viva", "λ·Δ(D) + ΔL", f'"límite = "&{X("limP", 3)}', v("flp"), "cm",
         f'IF({v("flp")}<={v("limP")},"CUMPLE","NO CUMPLE")', "ACI 24.2.4", "0.000")
    seccion("6. ALTURA MÍNIMA")
    paso("he >= hmín", "ACI 8.3.1.2", f'"αm = "&{X("am", 3)}', v("hmin"), "cm",
         f'IF({g["he"]}>={v("hmin")},"CUMPLE: he = "&FIXED({g["he"]},2),"NO CUMPLE: he = "&FIXED({g["he"]},2))')
    seccion("7. VOLADOS (si el paño tiene)")
    for b in BORDES:
        L = LET[b]
        paso(f"Volado {b}: Mu y Vu", "qu·L²/2 + Pu·L ; qu·L + Pu",
             f'"L cara = "&{X("Lc" + L, 3)}&" ; Vu = "&{X("VuV" + L, 0)}', v("MuV" + L), "kg·m/m",
             f'IF({v("Lc" + L)}>0,{v("stV" + L)},"sin volado")', "Estática", "0")
        paso(f"Volado {b}: cortante, flecha y altura", "vu ; Δ diferida punta ; h >= L/8·(0,4 + fy/7000)",
             f'"vu = "&{X("vV" + L)}&" ; Δ = "&{X("fpV" + L, 4)}&" cm ; hmín = "&{X("hV" + L, 1)}',
             v("prV" + L), "m prolong.",
             f'IF({v("Lc" + L)}>0,{v("ctV" + L)}&" / "&{v("flV" + L)},"")', "ACI 25.4.2.3 (anclaje)")
    _graficos(ws, v)
    ws.freeze_panes = "A5"
    _pagina(ws, f"A1:G{fila[0]}")


def _graficos(ws, v):
    """Gráficos nativos que dependen del paño elegido."""
    col0 = 10                                   # J
    Cc = lambda k: get_column_letter(col0 + k)  # noqa: E731
    _c(ws, f"{Cc(0)}2", "Datos de los gráficos (no editar)", FI, borde=False)

    def momentos(c0, corta):
        if corta:
            M1, M2, Mp, L = (f'IF({v("dirX")},{v("MdO")},{v("MdS")})', f'IF({v("dirX")},{v("MdE")},{v("MdN")})',
                             v("Mpc"), v("Lx"))
        else:
            M1, M2, Mp, L = (f'IF({v("dirX")},{v("MdS")},{v("MdO")})', f'IF({v("dirX")},{v("MdN")},{v("MdE")})',
                             v("Mpl"), v("Ly"))
        for k, e in enumerate((M1, M2, Mp, L)):
            ws[f"{Cc(c0)}{3 + k}"] = "=" + e
        m1, m2, mp, ll = (f"${Cc(c0)}${3 + k}" for k in range(4))
        P = f"({mp}+{m1})"
        ws[f"{Cc(c0)}7"] = f"=IF({mp}<=0,0,(2*{P}-({m1}-{m2})+2*SQRT({P}*({mp}+{m2})))/4)"
        kk = f"${Cc(c0)}$7"
        ws[f"{Cc(c0)}8"] = f'="M+ = "&FIXED({mp},0)&"   M− = "&FIXED({m1},0)&" / "&FIXED({m2},0)&" kg·m/m"'
        for n in range(21):
            xi = n / 20
            ws[f"{Cc(c0)}{10 + n}"] = f"={xi}*{ll}"
            ws[f"{Cc(c0 + 1)}{10 + n}"] = f"=-{m1}*(1-{xi})-{m2}*{xi}+4*{kk}*{xi}*(1-{xi})"
            ws[f"{Cc(c0 + 2)}{10 + n}"] = 0
        ch = ScatterChart()
        ch.title = "Momentos, dirección " + ("corta" if corta else "larga") + " (positivo hacia abajo)"
        ch.style = 13
        ch.y_axis.scaling.orientation = "maxMin"
        ch.x_axis.title, ch.y_axis.title = "m", "kg·m/m"
        xs = Reference(ws, min_col=col0 + c0, min_row=10, max_row=30)
        s = Series(Reference(ws, min_col=col0 + c0 + 1, min_row=10, max_row=30), xs)
        s.tx = SeriesLabel(strRef=StrRef(f"'MEMORIA'!${Cc(c0)}$8"))
        s.graphicalProperties.line.solidFill = "C25A14"
        s.graphicalProperties.line.width = 28000
        s.marker.symbol = "none"
        s.smooth = True
        ch.series.append(s)
        s0 = Series(Reference(ws, min_col=col0 + c0 + 2, min_row=10, max_row=30), xs, title="Eje")
        s0.graphicalProperties.line.solidFill = "404040"
        s0.marker.symbol = "none"
        s0.smooth = False
        ch.series.append(s0)
        return ch

    ch1, ch2 = momentos(0, True), momentos(4, False)
    # aprovechamiento
    c0 = 8
    items = [("M+ corta", "IF({pc_Mu}>0,{pc_uso},0)"), ("M+ larga", "IF({pl_Mu}>0,{pl_uso},0)"),
             ("M− norte", "IF({nn_Mu}>0,{nn_uso},0)"), ("M− sur", "IF({sn_Mu}>0,{sn_uso},0)"),
             ("M− este", "IF({en_Mu}>0,{en_uso},0)"), ("M− oeste", "IF({on_Mu}>0,{on_uso},0)"),
             ("Cortante", "{u_cort}"), ("Flechas", "{u_flech}"), ("Altura", "{u_alt}")]
    ws[f"{Cc(c0)}9"], ws[f"{Cc(c0 + 1)}9"], ws[f"{Cc(c0 + 2)}9"] = "Verificación", "Demanda / capacidad", "100 %"
    for n, (t, e) in enumerate(items):
        r = 10 + n
        ws[f"{Cc(c0)}{r}"] = t
        out, i = "", 0
        while i < len(e):
            if e[i] == "{":
                j = e.index("}", i)
                out += v(e[i + 1:j])
                i = j + 1
            else:
                out += e[i]
                i += 1
        ws[f"{Cc(c0 + 1)}{r}"] = "=" + out
        ws[f"{Cc(c0 + 2)}{r}"] = 1
    last = 10 + len(items) - 1
    bar = BarChart()
    bar.type = "col"
    bar.title = "Aprovechamiento (cumple hasta 100 %)"
    bar.style = 10
    bar.add_data(Reference(ws, min_col=col0 + c0 + 1, min_row=9, max_row=last), titles_from_data=True)
    bar.set_categories(Reference(ws, min_col=col0 + c0, min_row=10, max_row=last))
    bar.series[0].graphicalProperties.solidFill = "3C9D5B"
    bar.y_axis.number_format = "0%"
    ln = LineChart()
    ln.add_data(Reference(ws, min_col=col0 + c0 + 2, min_row=9, max_row=last), titles_from_data=True)
    ln.series[0].graphicalProperties.line.solidFill = "C0392B"
    ln.series[0].marker.symbol = "none"
    bar += ln
    # sección
    c0 = 12
    pts = [("0", "{D:h}"), ("2*{D:s}", "{D:h}"), ("2*{D:s}", "{D:hn}"), ("1.5*{D:s}+{D:bw}/2", "{D:hn}"),
           ("1.5*{D:s}+{D:bw}/2", "0"), ("1.5*{D:s}-{D:bw}/2", "0"), ("1.5*{D:s}-{D:bw}/2", "{D:hn}"),
           ("0.5*{D:s}+{D:bw}/2", "{D:hn}"), ("0.5*{D:s}+{D:bw}/2", "0"), ("0.5*{D:s}-{D:bw}/2", "0"),
           ("0.5*{D:s}-{D:bw}/2", "{D:hn}"), ("0", "{D:hn}"), ("0", "{D:h}")]
    gref = _G

    def dd(e):
        for k, val in gref.items():
            e = e.replace("{D:" + k + "}", val)
        return e

    for n, (x, y) in enumerate(pts):
        ws[f"{Cc(c0)}{10 + n}"] = "=" + dd(x)
        ws[f"{Cc(c0 + 1)}{10 + n}"] = "=" + dd(y)
    supn = f'IF({v("dirX")},IF({v("on_Asu")}>{v("en_Asu")},{v("on_n")},{v("en_n")}),IF({v("sn_Asu")}>{v("nn_Asu")},{v("sn_n")},{v("nn_n")}))'
    supf = f'IF({v("dirX")},IF({v("on_Asu")}>{v("en_Asu")},{v("on_phi")},{v("en_phi")}),IF({v("sn_Asu")}>{v("nn_Asu")},{v("sn_phi")},{v("nn_phi")}))'
    for n, (xc, k) in enumerate((("0.5", -1), ("0.5", 1), ("1.5", -1), ("1.5", 1))):
        r = 26 + n
        ws[f"{Cc(c0)}{r}"] = f"={xc}*{gref['s']}+IF({v('pc_n')}=2,{k}*MAX({v('pc_phi')}/10+0.6,2.6)/2,0)"
        ws[f"{Cc(c0 + 1)}{r}"] = f"={gref['rec']}+{v('pc_phi')}/20"
        ws[f"{Cc(c0 + 2)}{r}"] = f"={xc}*{gref['s']}+IF({supn}=2,{k}*MAX({supf}/10+0.6,2.6)/2,0)"
        ws[f"{Cc(c0 + 3)}{r}"] = f"={gref['h']}-{gref['rec']}-{supf}/20"
    ws[f"{Cc(c0)}31"] = f'="Inferior "&{v("pc_arm")}'
    ws[f"{Cc(c0)}32"] = "=\"Superior \"&" + f'IF({v("dirX")},IF({v("on_Asu")}>{v("en_Asu")},{v("on_arm")},{v("en_arm")}),IF({v("sn_Asu")}>{v("nn_Asu")},{v("sn_arm")},{v("nn_arm")}))'
    ws[f"{Cc(c0)}33"] = f'="Sección: h = "&FIXED({gref["h"]},0)&" cm"'
    sc = ScatterChart()
    sc.title = "Sección de la losa (cm)"
    sc.style = 13
    s = Series(Reference(ws, min_col=col0 + c0 + 1, min_row=10, max_row=22),
               Reference(ws, min_col=col0 + c0, min_row=10, max_row=22))
    s.tx = SeriesLabel(strRef=StrRef(f"'MEMORIA'!${Cc(c0)}$33"))
    s.graphicalProperties.line.solidFill = "404040"
    s.marker.symbol = "none"
    s.smooth = False
    sc.series.append(s)
    for xc, yc, t, color in ((c0, c0 + 1, 31, "17804A"), (c0 + 2, c0 + 3, 32, "C25A14")):
        s = Series(Reference(ws, min_col=col0 + yc, min_row=26, max_row=29),
                   Reference(ws, min_col=col0 + xc, min_row=26, max_row=29))
        s.tx = SeriesLabel(strRef=StrRef(f"'MEMORIA'!${Cc(c0)}${t}"))
        s.marker.symbol = "circle"
        s.marker.size = 9
        s.marker.graphicalProperties.solidFill = color
        s.graphicalProperties.line.noFill = True
        s.smooth = False
        sc.series.append(s)
    sc.x_axis.scaling.min = 0
    sc.y_axis.scaling.min = 0
    # cortante
    c0 = 16
    ws[f"{Cc(c0)}3"] = f"=MAX({v('Vc')}/{_FQ},1.6*MAX({v('dc')}/100,{gref['mac']}))"
    ws[f"{Cc(c0)}4"] = f"=0.75*{gref['vc']}*{gref['bwm']}*{v('dc')}"
    ws[f"{Cc(c0)}5"] = f'="φ·Vc nervios = "&FIXED(${Cc(c0)}$4,0)'
    ws[f"{Cc(c0)}6"] = f'="Vu(x): "&{v("cortP")}'
    for n in range(11):
        r = 10 + n
        ws[f"{Cc(c0)}{r}"] = f"={n / 10}*${Cc(c0)}$3"
        ws[f"{Cc(c0 + 1)}{r}"] = f"=MAX(0,{v('Vc')}-{_FQ}*{Cc(c0)}{r})"
        ws[f"{Cc(c0 + 2)}{r}"] = f"=${Cc(c0)}$4"
    cc = ScatterChart()
    cc.title = "Cortante desde la cara de la viga (kg/m)"
    cc.style = 13
    xs = Reference(ws, min_col=col0 + c0, min_row=10, max_row=20)
    for col, t, color in ((c0 + 1, 6, "1F3864"), (c0 + 2, 5, "2E8B57")):
        s = Series(Reference(ws, min_col=col0 + col, min_row=10, max_row=20), xs)
        s.tx = SeriesLabel(strRef=StrRef(f"'MEMORIA'!${Cc(c0)}${t}"))
        s.graphicalProperties.line.solidFill = color
        s.graphicalProperties.line.width = 25000
        s.marker.symbol = "none"
        s.smooth = False
        cc.series.append(s)
    for ch in (ch1, ch2, bar, sc, cc):
        for ax in (ch.x_axis, ch.y_axis):
            ax.delete = False
        ch.legend.position = "b"
    for ch, anc, w, h in ((sc, "A8", 16, 8.5), (bar, "C8", 17, 8.5), (ch1, "A25", 16, 8), (ch2, "C25", 17, 8),
                          (cc, "A42", 16, 8.5)):
        ch.width, ch.height = w, h
        ws.add_chart(ch, anc)


_G: dict = {}
_FQ = ""


# ===================================================================================== principal
def escribir_edificio(piso: Piso, pisos: list[dict] | None, ruta: str | Path) -> Path:
    """Genera el libro. ``pisos`` es una lista de {nombre, sc, viva, mamp}; si es None se usa un
    solo piso con las cargas de la entrada."""
    global _G, _FQ
    if piso.losa.tipo != "nervada":
        raise ErrorEntrada("El Excel con fórmulas vivas cubre solo losas nervadas.")
    geometria.preparar(piso)
    X, Y = list(piso.ejes_x.values()), list(piso.ejes_y.values())
    dx = [b - a for a, b in zip(X, X[1:])]
    dy = [b - a for a, b in zip(Y, Y[1:])]
    if len(dx) > NX or len(dy) > NY:
        raise ErrorEntrada(f"El Excel admite hasta {NX + 1} ejes por dirección.")
    if piso.vigas_por_eje:
        raise ErrorEntrada("El Excel usa una sola sección de viga para todos los ejes.")
    cel: dict = {(i, j): None for i in range(len(dx)) for j in range(len(dy))}
    for p in piso.panos:
        i, j = X.index(p.x0), Y.index(p.y0)
        if X.index(p.x1) != i + 1 or Y.index(p.y1) != j + 1:
            raise ErrorEntrada(f"Paño {p.id}: en el Excel cada paño va entre ejes consecutivos.")
        if p.fuera_de_alcance:
            continue
        cel[(i, j)] = p
    cg = piso.cargas
    pisos = pisos or [{"nombre": piso.proyecto.get("piso") or "Piso", "sc": cg.acabados + cg.paredes + cg.otras,
                       "viva": cg.viva, "mamp": cg.soporta_mamposteria}]
    if len(pisos) > NP:
        raise ErrorEntrada(f"El Excel admite hasta {NP} pisos.")
    wb = Workbook()
    wb.remove(wb.active)
    g = _datos(wb, piso, dx, dy)
    _G = {k: v for k, v in g.items()}
    fp = _pisos(wb, pisos, g)
    pref = _planta(wb, piso, cel)
    _tablas(wb)
    cols = _calculo(wb, g, fp, pref)
    _FQ = f"INDEX(PISOS!$J$5:$J${4 + NP},MATCH($B$3,PISOS!$B$5:$B${4 + NP},0))"
    _memoria(wb, g, fp, cols, [p["nombre"] for p in pisos])
    _resumen(wb, g, fp, cols)
    orden = ["RESUMEN", "MEMORIA", "PISOS", "PLANTA", "DATOS", "CALCULO", "TABLAS"]
    wb._sheets = [wb[n] for n in orden]
    wb.active = 0
    wb.calculation.fullCalcOnLoad = True
    ruta = Path(ruta)
    ruta.parent.mkdir(parents=True, exist_ok=True)
    wb.save(ruta)
    return ruta


def pisos_desde_yaml(datos: dict) -> list[dict] | None:
    """Lee la sección opcional ``pisos`` del YAML."""
    lista = datos.get("pisos")
    if not lista:
        return None
    out = []
    for k, p in enumerate(lista):
        try:
            sc = float(p.get("sobrecarga", float(p.get("acabados", 0)) + float(p.get("paredes", 0))
                             + float(p.get("otras", 0))))
            out.append({"nombre": str(p.get("nombre", f"Piso {k + 1}")), "sc": sc, "viva": float(p["viva"]),
                        "mamp": bool(p.get("soporta_mamposteria", True))})
        except (KeyError, TypeError, ValueError) as e:
            raise ErrorEntrada(f"pisos[{k + 1}]: falta 'viva' o hay un dato no numérico ({e}).") from None
    return out
