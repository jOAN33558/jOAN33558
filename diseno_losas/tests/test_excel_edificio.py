"""Excel del edificio: fórmulas vivas, varios pisos, ejes ampliables y volados."""
import copy
import shutil
import subprocess
import sys
from pathlib import Path

import openpyxl
import pytest
import yaml

from losas import disenar_piso, piso_desde_dict
from losas.excel_edificio import FILA0, NC, NX, escribir_edificio, pisos_desde_yaml

RAIZ = Path(__file__).resolve().parents[1]
EDIF = RAIZ / "ejemplos" / "edificio" / "edificio.yaml"
LO = shutil.which("soffice")


def _datos():
    return yaml.safe_load(open(EDIF, encoding="utf-8"))


def test_estructura_del_libro(tmp_path):
    d = _datos()
    ruta = escribir_edificio(piso_desde_dict(d), pisos_desde_yaml(d), tmp_path / "e.xlsx")
    wb = openpyxl.load_workbook(ruta)
    assert wb.sheetnames == ["RESUMEN", "MEMORIA", "PISOS", "PLANTA", "DATOS", "CALCULO", "TABLAS"]
    assert len(wb["MEMORIA"]._charts) == 5
    assert wb["PISOS"]["B7"].value.startswith("Nivel +7,50")
    assert wb["PLANTA"]["H5"].value == 1.2 and wb["PLANTA"]["H5"].fill.fgColor.rgb.endswith("FFF2CC")
    assert wb.calculation.fullCalcOnLoad


def _recalcular(ruta, tmp):
    subprocess.run([LO, "--headless", "--convert-to", "xlsx:Calc MS Excel 2007 XML", "--outdir", str(tmp),
                    str(ruta)], check=True, capture_output=True, timeout=400)
    return openpyxl.load_workbook(Path(tmp) / Path(ruta).name, data_only=True)["CALCULO"]


def _comparar(ws, d):
    hdr = {ws.cell(5, k).value: k for k in range(1, ws.max_column + 1)}
    n = 0
    for f, pz in enumerate(d.get("pisos") or [None]):
        dd = copy.deepcopy(d)
        if pz:
            dd["cargas"] = {"acabados": pz["sobrecarga"], "viva": pz["viva"],
                            "soporta_mamposteria": pz["soporta_mamposteria"]}
        rp = disenar_piso(piso_desde_dict(dd))
        X, Y = list(rp.piso.ejes_x.values()), list(rp.piso.ejes_y.values())
        for r in rp.panos.values():
            fila = FILA0 + f * NC + Y.index(r.pano.y0) * NX + X.index(r.pano.x0)
            g = lambda t: ws.cell(fila, hdr[t]).value  # noqa: E731
            assert g("Tipo") == r.tipo
            assert g("Inf. corta").startswith(r.flexion["pos_corta"].armado)
            for b in ("norte", "sur", "este", "oeste"):
                x = r.flexion.get("neg_" + b)
                assert g("Sup. " + b) == (x.armado + (" (mín.)" if x.constructivo else "") if x else "-")
            assert g("Cortante") == r.cortante.estado
            assert g("RESULTADO") == r.resultado
            for rv in r.volados:
                b = rv.volado.borde
                assert g(f"Volado {b}: Mu") == pytest.approx(rv.Mu)
                assert g(f"Volado {b}: prolongación (m)") == pytest.approx(rv.prolongacion)
            n += 1
    return n


@pytest.mark.skipif(not LO, reason="requiere LibreOffice para recalcular")
def test_tres_pisos_con_volados_igual_que_python(tmp_path):
    d = _datos()
    ruta = escribir_edificio(piso_desde_dict(d), pisos_desde_yaml(d), tmp_path / "e.xlsx")
    assert _comparar(_recalcular(ruta, tmp_path / "c"), d) == 18


@pytest.mark.skipif(not LO, reason="requiere LibreOffice para recalcular")
def test_agregar_ejes_en_el_excel(tmp_path):
    d = _datos()
    ruta = escribir_edificio(piso_desde_dict(d), pisos_desde_yaml(d), tmp_path / "e.xlsx")
    wb = openpyxl.load_workbook(ruta)
    for fila in wb["DATOS"].iter_rows(min_col=1, max_col=3):
        if fila[0].value == "X: eje D a eje E":
            fila[2].value = 4.0
        if fila[0].value == "Y: eje 3 a eje 4":
            fila[2].value = 3.5
    wb.save(ruta)
    d3 = copy.deepcopy(d)
    d3["ejes"] = {"x": {"nombres": list("ABCDE"), "distancias": [5, 5, 5, 4]},
                  "y": {"nombres": ["1", "2", "3", "4"], "distancias": [4, 5, 3.5]}}
    d3["panos"] = [{"id": f"{'ABCDE'[i]}{j}", "ejes_x": ["ABCDE"[i], "ABCDE"[i + 1]],
                    "ejes_y": [str(j + 1), str(j + 2)]} for i in range(4) for j in range(3)]
    for p in d3["panos"]:
        if p["id"] in ("A0", "B0"):
            p["volado"] = {"borde": "sur", "longitud": 1.2, "carga_borde": 150}
    assert _comparar(_recalcular(ruta, tmp_path / "c"), d3) == 36
