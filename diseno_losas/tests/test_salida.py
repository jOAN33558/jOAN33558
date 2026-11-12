"""Salidas: memoria en Excel y plano PNG del ejemplo."""
import re
from pathlib import Path

import openpyxl
import pytest

from losas.__main__ import ejecutar, main

EJEMPLO = Path(__file__).resolve().parents[1] / "ejemplos" / "piso_ejemplo.yaml"
EMOJI = re.compile("[\U0001F000-\U0001FAFF☀-➿⬀-⯿️]")


@pytest.fixture(scope="module")
def salida(tmp_path_factory):
    carpeta = tmp_path_factory.mktemp("salida")
    res, excel, plano = ejecutar(EJEMPLO, carpeta)
    return res, excel, plano


def test_archivos_generados(salida):
    _, excel, plano = salida
    assert excel.exists() and excel.suffix == ".xlsx"
    assert plano.exists() and plano.stat().st_size > 20_000
    assert plano.read_bytes()[:8] == b"\x89PNG\r\n\x1a\n"


def test_hojas_del_excel(salida):
    res, excel, _ = salida
    wb = openpyxl.load_workbook(excel)
    assert wb.sheetnames[0] == "RESUMEN"
    for id_ in res.panos:
        assert id_ in wb.sheetnames
    assert {"DATOS", "TABLA", "PLANO"} <= set(wb.sheetnames)
    filas = [[c.value for c in f] for f in wb["P1"].iter_rows()]
    assert ["Concepto", "Fórmula", "Sustitución", "Resultado", "Unidad", "Verificación",
            "Referencia"] in filas


def test_resumen_lista_todos_los_panos(salida):
    res, excel, _ = salida
    ws = openpyxl.load_workbook(excel)["RESUMEN"]
    textos = [str(c.value) for fila in ws.iter_rows() for c in fila if c.value is not None]
    for id_, r in res.panos.items():
        assert id_ in textos
        assert r.resultado in textos
    assert any("FUERA DE ALCANCE" in t for t in textos)
    assert any("elementos finitos" in t for t in textos)


def test_fuente_arial_y_sin_emojis(salida):
    _, excel, _ = salida
    wb = openpyxl.load_workbook(excel)
    for ws in wb:
        for fila in ws.iter_rows():
            for c in fila:
                if c.value is None:
                    continue
                assert c.font.name == "Arial", (ws.title, c.coordinate)
                assert not EMOJI.search(str(c.value)), (ws.title, c.coordinate, c.value)


def test_memoria_tiene_formula_sustitucion_y_verificacion(salida):
    _, excel, _ = salida
    ws = openpyxl.load_workbook(excel)["P1"]
    filas = [[c.value for c in f] for f in ws.iter_rows(min_row=6)]
    acero = next(f for f in filas if f[0] and "Acero requerido" in f[0])
    assert "As =" in acero[1] and "√" in acero[2] and isinstance(acero[3], float)
    assert any(f[5] and str(f[5]).startswith("CUMPLE") for f in filas)
    secciones = [f[0] for f in filas if f[0] and re.match(r"\d+\. ", str(f[0]))]
    assert len(secciones) >= 10


def test_linea_de_comandos(tmp_path, capsys):
    assert main([str(EJEMPLO), "--salida", str(tmp_path)]) == 0
    salida_texto = capsys.readouterr().out
    assert "P6" in salida_texto and "FUERA DE ALCANCE" in salida_texto
    assert main([str(tmp_path / "no_existe.yaml")]) == 2
    assert "ERROR EN LA ENTRADA" in capsys.readouterr().err


def test_figuras_por_pano_incrustadas(salida):
    """Cada hoja de paño lleva su lámina de figuras, generada con sus propios datos."""
    res, excel, _ = salida
    carpeta = excel.parent / "piso_ejemplo_figuras"
    wb = openpyxl.load_workbook(excel)
    contenidos = set()
    for id_ in res.panos:
        png = carpeta / f"pano_{id_}.png"
        assert png.exists() and png.read_bytes()[:8] == b"\x89PNG\r\n\x1a\n"
        assert len(wb[id_]._images) == 1
        contenidos.add(png.read_bytes())
    assert len(contenidos) == len(res.panos)            # ninguna figura se repite
    assert (carpeta / "general.png").exists() and len(wb["DATOS"]._images) == 1
    assert (carpeta / "aprovechamiento.png").exists() and len(wb["RESUMEN"]._images) == 1
    assert len(wb["PLANO"]._images) == 1


def test_las_figuras_cambian_con_los_datos(tmp_path):
    """La misma planta con otra carga viva produce una lámina distinta."""
    import copy

    from conftest import armar
    from losas import disenar_piso, piso_desde_dict
    from losas.figuras import figura_pano

    base = armar([{"id": "P1", "ejes_x": ["A", "B"], "ejes_y": ["1", "2"],
                   "bordes": {"norte": "continuo", "este": "continuo"}}], [4.0], [5.0])
    otra = copy.deepcopy(base)
    otra["cargas"]["viva"] = 500
    imagenes = []
    for i, datos in enumerate((base, otra, base)):
        rp = disenar_piso(piso_desde_dict(datos))
        imagenes.append(figura_pano(rp, rp.panos["P1"], tmp_path / f"p{i}.png").read_bytes())
    assert imagenes[0] != imagenes[1]
    assert imagenes[0] == imagenes[2]                   # mismos datos, misma figura


def test_indices_de_aprovechamiento():
    from conftest import un_pano
    from losas.indices import indices, maximos

    r = un_pano(6.0, 7.0, {"norte": "continuo", "este": "continuo"}, cargas={"viva": 1000})
    lista = indices(r)
    cortante = next(i for i in lista if i.grupo == "Cortante")
    assert cortante.valor == pytest.approx(r.cortante.vu / r.cortante.vc) and cortante.estado == "no"
    assert maximos(r)["Cortante"] > 1
    assert all(i.valor > 0 for i in lista)
    fuera = un_pano(4.0, 5.0, pano={"fuera_de_alcance": ["abertura"]})
    assert indices(fuera) == [] and maximos(fuera) == {}
