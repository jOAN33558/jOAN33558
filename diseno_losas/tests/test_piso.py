"""Piso de 3 x 3 paños, compatibilidad, cortante que no cumple y casos fuera de alcance."""
import pytest

from conftest import armar, calcular, un_pano
from losas import disenar_piso, piso_desde_dict
from losas.modelos import FUERA_DE_ALCANCE, OPUESTO, ErrorEntrada


def piso_3x3(**cambios):
    panos = [{"id": f"P{f}{c}", "ejes_x": [chr(65 + c), chr(66 + c)],
              "ejes_y": [str(f + 1), str(f + 2)]} for f in range(3) for c in range(3)]
    return calcular(panos, [4.0, 4.0, 4.0], [5.0, 5.0, 5.0], **cambios)


def test_piso_3x3_tipos_deducidos():
    res = piso_3x3()
    tipos = {i: r.tipo for i, r in res.panos.items()}
    # Lx = 4 m en X: los bordes largos son este/oeste
    assert tipos == {"P00": 6, "P01": 3, "P02": 6,
                     "P10": 2, "P11": 1, "P12": 2,
                     "P20": 6, "P21": 3, "P22": 6}
    assert all(r.calculado for r in res.panos.values())


def test_piso_3x3_compatibilidad():
    res = piso_3x3()
    assert len(res.bordes_comunes) == 12
    for c in res.bordes_comunes:
        a, b = res.panos[c.pano_a], res.panos[c.pano_b]
        assert c.borde_b == OPUESTO[c.borde_a]
        assert c.M_dis == pytest.approx(max(c.M_a, c.M_b))
        # ambos paños diseñan el borde común con el mayor de los dos momentos
        assert a.M_dis[c.borde_a] == pytest.approx(c.M_dis)
        assert b.M_dis[c.borde_b] == pytest.approx(c.M_dis)
        assert a.flexion[f"neg_{c.borde_a}"].Mu == pytest.approx(c.M_dis)
        assert c.armado not in ("", "-")
    # el paño de esquina (tipo 6) tiene mayor My(-) que el central (tipo 1)
    centro, borde = res.panos["P11"], res.panos["P10"]
    assert borde.M_borde["este"] > centro.M_borde["oeste"]
    assert centro.M_dis["oeste"] == pytest.approx(borde.M_borde["este"])
    assert centro.origen["oeste"] == "vecino P10"


def test_bordes_perimetrales_sin_momento():
    res = piso_3x3()
    esquina = res.panos["P00"]
    assert esquina.pano.cond == {"norte": "continuo", "sur": "discontinuo",
                                 "este": "continuo", "oeste": "discontinuo"}
    assert esquina.M_dis["sur"] == 0 and esquina.flexion["neg_sur"].constructivo


def test_caso_que_no_cumple_cortante():
    r = un_pano(6.0, 7.0, {"norte": "continuo", "este": "continuo"}, cargas={"viva": 1000})
    assert r.cortante.estado == "NO CUMPLE"
    assert r.cortante.vu > r.cortante.vc and r.cortante.vu_mac > r.cortante.vc
    assert r.resultado == "NO CUMPLE"
    assert any(c.nombre.startswith("Cortante") and not c.cumple for c in r.checks)


def test_cortante_cumple_con_macizado():
    r = un_pano(4.5, 4.5, {b: "continuo" for b in ("norte", "sur", "este", "oeste")},
                cargas={"viva": 600}, losa={"altura": 25}, vigas={"h": 50})
    assert r.cortante.estado == "CUMPLE con macizado"
    assert r.cortante.vu > r.cortante.vc >= r.cortante.vu_mac
    assert r.cortante.cumple


def test_opcion_cortante_aci_318_19_es_mas_exigente(referencia):
    r = un_pano(4.0, 5.0, {"norte": "continuo", "este": "continuo"},
                opciones={"cortante": "aci318_19"})
    assert r.cortante.vc < referencia.cortante.vc
    assert r.cortante.vu == pytest.approx(referencia.cortante.vu)


@pytest.mark.parametrize("motivo, texto", [
    ("abertura", "Abertura"), ("carga_puntual", "puntual"), ("carga_lineal", "lineal"),
    ("no_rectangular", "rectangular"), ("sin_vigas", "punzonamiento"),
])
def test_fuera_de_alcance_declarado(motivo, texto):
    r = un_pano(4.0, 5.0, pano={"fuera_de_alcance": {motivo: True}})
    assert r.resultado == FUERA_DE_ALCANCE and not r.calculado and not r.cumple
    assert texto in " ".join(r.motivos)
    assert not r.flexion and r.cortante is None           # no se calcula nada
    assert any("elementos finitos" in p.concepto for p in r.memoria.pasos)


def test_losa_sin_vigas_se_detecta():
    res = calcular([{"id": "P1", "ejes_x": ["A", "B"], "ejes_y": ["1", "2"]}], [5.0], [5.0],
                   vigas={"b": 0, "h": 0})
    r = res.panos["P1"]
    assert not r.calculado and "punzonamiento" in " ".join(r.motivos)
    assert res.resultado.startswith("INCOMPLETO")
    assert any("elementos finitos" in a for a in res.avisos)


def test_vigas_banda_fuera_de_alcance():
    r = un_pano(5.0, 5.0, vigas={"b": 25, "h": 15})       # viga más delgada que la losa
    assert not r.calculado and "αm" in " ".join(r.motivos)


def test_combinacion_de_bordes_no_tabulada():
    bordes = {"este": "libre", "oeste": "discontinuo", "norte": "continuo", "sur": "continuo"}
    r = un_pano(4.0, 5.0, bordes)
    assert not r.calculado and "no está en las tablas" in " ".join(r.motivos)


def test_vecino_fuera_de_alcance_se_avisa():
    panos = [{"id": "P1", "ejes_x": ["A", "B"], "ejes_y": ["1", "2"]},
             {"id": "P2", "ejes_x": ["B", "C"], "ejes_y": ["1", "2"],
              "fuera_de_alcance": ["abertura"]}]
    res = calcular(panos, [4.0, 4.0], [5.0])
    assert res.panos["P1"].calculado and not res.panos["P2"].calculado
    assert any("P2" in a and "fuera de alcance" in a for a in res.panos["P1"].avisos)


@pytest.mark.parametrize("cambio, texto", [
    ({"losa": {"tipo": "aligerada"}}, "losa.tipo"),
    ({"materiales": {"fc": None}}, "fc"),
    ({"panos": [{"id": "P1", "ejes_x": ["A", "Z"], "ejes_y": ["1", "2"]}]}, "no existe"),
    ({"panos": [{"id": "P1", "ejes_x": ["A", "B"], "ejes_y": ["1", "2"]},
                {"id": "P2", "ejes_x": ["A", "B"], "ejes_y": ["1", "2"]}]}, "superponen"),
    ({"panos": [{"id": "P1", "ejes_x": ["A", "B"], "ejes_y": ["1", "2"],
                 "bordes": {"norte": "empotrado"}}]}, "no válido"),
    ({"panos": [{"id": "P1", "ejes_x": ["A", "B"], "ejes_y": ["1", "2"],
                 "bordes": {"sur": "libre"}, "volado": {"borde": "sur", "longitud": 1}}]},
     "libre"),
])
def test_errores_de_entrada_con_mensaje_claro(cambio, texto):
    cambio = dict(cambio)
    panos = cambio.pop("panos", [{"id": "P1", "ejes_x": ["A", "B"], "ejes_y": ["1", "2"]}])
    d = armar(panos, [4.0], [5.0], **cambio)
    with pytest.raises(ErrorEntrada, match=texto):
        disenar_piso(piso_desde_dict(d))
