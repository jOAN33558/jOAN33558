"""Lectura y validación del archivo de entrada (YAML)."""
from __future__ import annotations

from pathlib import Path

import yaml

from .modelos import (BORDES, Cargas, ErrorEntrada, Losa, Materiales, Opciones, Pano, Piso,
                      Viga, Volado)

MOTIVOS = {
    "abertura": "Abertura grande en el paño.",
    "carga_puntual": "Carga puntual dentro del paño.",
    "carga_lineal": "Carga lineal dentro del paño.",
    "no_rectangular": "Paño no rectangular.",
    "sin_vigas": "Losa plana sin vigas (requiere revisión de punzonamiento).",
}
ALIAS_MOTIVO = {"aberturas": "abertura", "abertura_grande": "abertura",
                "cargas_puntuales": "carga_puntual", "cargas_lineales": "carga_lineal"}
DIAMETROS_DEFECTO = {"nervada": [12, 14, 16, 18, 20], "maciza": [10, 12, 14, 16]}


def leer(ruta: str | Path) -> Piso:
    ruta = Path(ruta)
    if not ruta.exists():
        raise ErrorEntrada(f"No existe el archivo de entrada: {ruta}")
    with open(ruta, encoding="utf-8") as f:
        try:
            datos = yaml.safe_load(f)
        except yaml.YAMLError as e:
            raise ErrorEntrada(f"El archivo {ruta.name} no es un YAML válido: {e}") from e
    return piso_desde_dict(datos)


def _num(d: dict, clave: str, donde: str, defecto=None, minimo=None) -> float:
    if clave not in d or d[clave] is None:
        if defecto is None:
            raise ErrorEntrada(f"Falta el dato '{clave}' en '{donde}'.")
        return defecto
    try:
        v = float(d[clave])
    except (TypeError, ValueError):
        raise ErrorEntrada(f"'{donde}.{clave}' debe ser un número; se leyó {d[clave]!r}.") from None
    if minimo is not None and v < minimo:
        raise ErrorEntrada(f"'{donde}.{clave}' = {v} no puede ser menor que {minimo}.")
    return v


def _seccion(datos: dict, nombre: str, obligatoria=True) -> dict:
    s = datos.get(nombre)
    if s is None:
        if obligatoria:
            raise ErrorEntrada(f"Falta la sección '{nombre}' en el archivo de entrada.")
        return {}
    if not isinstance(s, dict):
        raise ErrorEntrada(f"La sección '{nombre}' debe ser un bloque de datos (clave: valor).")
    return s


def _materiales(d: dict) -> Materiales:
    ec = d.get("Ec")
    return Materiales(
        fc=_num(d, "fc", "materiales", minimo=1), fy=_num(d, "fy", "materiales", minimo=1),
        peso_hormigon=_num(d, "peso_hormigon", "materiales", 2400.0, 1),
        recubrimiento=_num(d, "recubrimiento", "materiales", 2.5, 0),
        Es=_num(d, "Es", "materiales", 2.0e6, 1), Ec=float(ec) if ec else None)


def _losa(d: dict) -> Losa:
    tipo = str(d.get("tipo", "")).strip().lower()
    if tipo not in ("nervada", "maciza"):
        raise ErrorEntrada("'losa.tipo' debe ser 'nervada' o 'maciza'.")
    losa = Losa(tipo=tipo, altura=_num(d, "altura", "losa", minimo=1),
                diametros=sorted(int(x) for x in d.get("diametros") or DIAMETROS_DEFECTO[tipo]),
                max_varillas_nervio=int(d.get("max_varillas_nervio", 2)),
                macizado=_num(d, "macizado", "losa", 0.425, 0),
                diametro_malla=_num(d, "diametro_malla", "losa", 4.0, 1))
    if tipo == "nervada":
        losa.loseta = _num(d, "loseta", "losa", minimo=0.1)
        losa.ancho_nervio = _num(d, "ancho_nervio", "losa", minimo=0.1)
        losa.separacion_nervios = _num(d, "separacion_nervios", "losa", minimo=0.1)
        losa.peso_bloques = _num(d, "peso_bloques", "losa", 0.0, 0)
        if losa.loseta >= losa.altura:
            raise ErrorEntrada("'losa.loseta' debe ser menor que 'losa.altura'.")
        if losa.ancho_nervio >= losa.separacion_nervios:
            raise ErrorEntrada("'losa.ancho_nervio' debe ser menor que 'losa.separacion_nervios' "
                               "(la separación se mide de eje a eje de nervios).")
    return losa


def _cargas(d: dict) -> Cargas:
    return Cargas(acabados=_num(d, "acabados", "cargas", 0.0, 0),
                  paredes=_num(d, "paredes", "cargas", 0.0, 0),
                  otras=_num(d, "otras", "cargas", 0.0, 0),
                  viva=_num(d, "viva", "cargas", minimo=0),
                  uso=str(d.get("uso", "")),
                  soporta_mamposteria=bool(d.get("soporta_mamposteria", True)),
                  fraccion_viva_sostenida=_num(d, "fraccion_viva_sostenida", "cargas", 0.0, 0),
                  lambda_diferida=_num(d, "lambda_diferida", "cargas", 2.0, 0))


def _ejes(d: dict, nombre: str) -> dict[str, float]:
    e = d.get(nombre)
    if not isinstance(e, dict) or "nombres" not in e or "distancias" not in e:
        raise ErrorEntrada(f"'ejes.{nombre}' debe tener 'nombres' y 'distancias'.")
    nombres = [str(n) for n in e["nombres"]]
    dist = [float(x) for x in e["distancias"]]
    if len(nombres) < 2 or len(dist) != len(nombres) - 1:
        raise ErrorEntrada(f"'ejes.{nombre}': con {len(nombres)} ejes deben darse "
                           f"{max(len(nombres) - 1, 1)} distancias; se dieron {len(dist)}.")
    if len(set(nombres)) != len(nombres):
        raise ErrorEntrada(f"'ejes.{nombre}': hay nombres de eje repetidos.")
    if any(x <= 0 for x in dist):
        raise ErrorEntrada(f"'ejes.{nombre}': las distancias deben ser positivas.")
    coords, x = {}, 0.0
    for i, n in enumerate(nombres):
        coords[n] = round(x, 6)
        if i < len(dist):
            x += dist[i]
    return coords


def _vigas(d: dict) -> tuple[Viga | None, dict[str, Viga]]:
    if not d:
        return None, {}
    b, h = float(d.get("b") or 0), float(d.get("h") or 0)
    general = Viga(b, h) if b > 0 and h > 0 else None
    por_eje = {}
    for eje, v in (d.get("por_eje") or {}).items():
        por_eje[str(eje)] = Viga(_num(v, "b", f"vigas.por_eje.{eje}", minimo=0),
                                 _num(v, "h", f"vigas.por_eje.{eje}", minimo=0))
    return general, por_eje


def _motivos(p: dict, donde: str) -> list[str]:
    claves: list[str] = []
    fa = p.get("fuera_de_alcance")
    if isinstance(fa, dict):
        claves += [k for k, v in fa.items() if v]
    elif isinstance(fa, (list, tuple)):
        claves += [str(k) for k in fa]
    elif fa:
        claves.append(str(fa))
    claves += [k for k in ("aberturas", "cargas_puntuales", "cargas_lineales") if p.get(k)]
    if str(p.get("forma", "rectangular")).lower() not in ("rectangular", ""):
        claves.append("no_rectangular")
    motivos = []
    for k in claves:
        k = ALIAS_MOTIVO.get(k, k)
        if k not in MOTIVOS:
            raise ErrorEntrada(f"{donde}: motivo fuera de alcance desconocido '{k}'. "
                               f"Use uno de: {', '.join(MOTIVOS)}.")
        if MOTIVOS[k] not in motivos:
            motivos.append(MOTIVOS[k])
    return motivos


def _volados(p: dict, donde: str) -> list[Volado]:
    lista = p.get("volados") or ([p["volado"]] if p.get("volado") else [])
    volados = []
    for v in lista:
        borde = str(v.get("borde", "")).lower()
        if borde not in BORDES:
            raise ErrorEntrada(f"{donde}: 'volado.borde' debe ser norte, sur, este u oeste.")
        medida = str(v.get("medida", "eje")).lower()
        if medida not in ("eje", "cara"):
            raise ErrorEntrada(f"{donde}: 'volado.medida' debe ser 'eje' o 'cara'.")
        volados.append(Volado(
            borde=borde, longitud=_num(v, "longitud", f"{donde}.volado", minimo=0.01),
            medida=medida, carga_borde=_num(v, "carga_borde", f"{donde}.volado", 0.0, 0),
            carga_borde_viva=_num(v, "carga_borde_viva", f"{donde}.volado", 0.0, 0),
            cargas={k: float(v[k]) for k in ("viva", "paredes", "acabados", "otras") if k in v}))
    if len({v.borde for v in volados}) != len(volados):
        raise ErrorEntrada(f"{donde}: hay dos volados en el mismo borde.")
    return volados


def _pano(p: dict, i: int, ejes_x: dict, ejes_y: dict) -> Pano:
    id_ = str(p.get("id") or f"P{i + 1}")
    donde = f"paño {id_}"
    pares = []
    for clave, ejes in (("ejes_x", ejes_x), ("ejes_y", ejes_y)):
        par = p.get(clave)
        if not isinstance(par, (list, tuple)) or len(par) != 2:
            raise ErrorEntrada(f"{donde}: '{clave}' debe ser una lista de dos ejes, p. ej. [A, B].")
        par = [str(e) for e in par]
        for e in par:
            if e not in ejes:
                raise ErrorEntrada(f"{donde}: el eje '{e}' no existe en 'ejes.{clave[-1]}'.")
        if ejes[par[0]] == ejes[par[1]]:
            raise ErrorEntrada(f"{donde}: '{clave}' repite el mismo eje.")
        pares.append(tuple(sorted(par, key=lambda e: ejes[e])))
    bordes = {}
    for b, c in (p.get("bordes") or {}).items():
        b, c = str(b).lower(), str(c).lower()
        if b not in BORDES or c not in ("auto", "continuo", "discontinuo", "libre"):
            raise ErrorEntrada(f"{donde}: borde '{b}: {c}' no válido. Bordes: norte, sur, este, "
                               "oeste. Condiciones: auto, continuo, discontinuo, libre.")
        bordes[b] = c
    return Pano(id=id_, ejes_x=pares[0], ejes_y=pares[1], bordes=bordes,
                volados=_volados(p, donde),
                cargas={k: float(p[k]) for k in ("viva", "paredes", "acabados", "otras") if k in p},
                fuera_de_alcance=_motivos(p, donde))


def piso_desde_dict(datos: dict) -> Piso:
    if not isinstance(datos, dict):
        raise ErrorEntrada("El archivo de entrada está vacío o no tiene el formato esperado.")
    ejes = _seccion(datos, "ejes")
    ejes_x, ejes_y = _ejes(ejes, "x"), _ejes(ejes, "y")
    repetidos = set(ejes_x) & set(ejes_y)
    if repetidos:
        raise ErrorEntrada(f"Los ejes X e Y no pueden compartir nombres: {sorted(repetidos)}.")
    lista = datos.get("panos") or datos.get("paños")
    if not lista:
        raise ErrorEntrada("Falta la lista 'panos' o está vacía.")
    panos = [_pano(p, i, ejes_x, ejes_y) for i, p in enumerate(lista)]
    ids = [p.id for p in panos]
    if len(set(ids)) != len(ids):
        raise ErrorEntrada("Hay identificadores de paño repetidos.")
    viga, por_eje = _vigas(_seccion(datos, "vigas", obligatoria=False))
    op = _seccion(datos, "opciones", obligatoria=False)
    cortante = str(op.get("cortante", "nec")).lower()
    if cortante not in ("nec", "aci318_19"):
        raise ErrorEntrada("'opciones.cortante' debe ser 'nec' o 'aci318_19'.")
    return Piso(proyecto=_seccion(datos, "proyecto", obligatoria=False),
                materiales=_materiales(_seccion(datos, "materiales")),
                losa=_losa(_seccion(datos, "losa")), cargas=_cargas(_seccion(datos, "cargas")),
                viga=viga, vigas_por_eje=por_eje, ejes_x=ejes_x, ejes_y=ejes_y, panos=panos,
                opciones=Opciones(cortante=cortante))
