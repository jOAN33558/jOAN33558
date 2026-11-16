"""Excel con fórmulas vivas y gráficos nativos."""
import shutil
import subprocess
from pathlib import Path

import openpyxl
import pytest

from losas import disenar_piso, leer
from losas.excel_vivo import escribir_vivo
from losas.modelos import ErrorEntrada

EJ = Path(__file__).resolve().parents[1] / "ejemplos" / "ejercicio"


def test_libro_con_formulas_y_graficos(tmp_path):
    ruta = escribir_vivo(leer(EJ / "oficinas_h30.yaml"), tmp_path / "vivo.xlsx")
    wb = openpyxl.load_workbook(ruta)
    assert wb.sheetnames[:2] == ["RESUMEN", "DATOS"]
    for pid in ("P1", "P2", "P3", "P4", "P5", "P6"):
        ws = wb[pid]
        assert len(ws._charts) == 5
        formulas = [c.value for fila in ws.iter_rows() for c in fila
                    if isinstance(c.value, str) and c.value.startswith("=")]
        assert len(formulas) > 300
    assert len(wb["RESUMEN"]._charts) == 1
    assert wb.calculation.fullCalcOnLoad


def test_rechaza_lo_que_no_cubre(tmp_path):
    with pytest.raises(ErrorEntrada):
        escribir_vivo(leer(Path(__file__).resolve().parents[1] / "ejemplos" / "piso_ejemplo.yaml"),
                      tmp_path / "x.xlsx")


@pytest.mark.skipif(not shutil.which("soffice"), reason="requiere LibreOffice para recalcular")
@pytest.mark.parametrize("nombre", ["oficinas", "oficinas_h30"])
def test_formulas_coinciden_con_python(tmp_path, nombre):
    ruta = escribir_vivo(leer(EJ / f"{nombre}.yaml"), tmp_path / "vivo.xlsx")
    subprocess.run(["soffice", "--headless", "--convert-to", "xlsx:Calc MS Excel 2007 XML",
                    "--outdir", str(tmp_path / "calc"), str(ruta)], check=True, capture_output=True,
                   timeout=240)
    ws = openpyxl.load_workbook(tmp_path / "calc" / "vivo.xlsx", data_only=True)["RESUMEN"]
    rp = disenar_piso(leer(EJ / f"{nombre}.yaml"))
    for fila in ws.iter_rows(min_row=5, max_row=10, values_only=True):
        r = rp.panos[fila[0]]
        assert fila[1] == r.tipo
        assert fila[5] == r.flexion["pos_corta"].armado
        negs = [r.flexion["neg_" + b].armado + (" (mín.)" if r.flexion["neg_" + b].constructivo else "")
                for b in ("norte", "sur", "este", "oeste")]
        assert list(fila[7:11]) == negs
        assert fila[12] == r.cortante.estado
        assert fila[15] == r.resultado
