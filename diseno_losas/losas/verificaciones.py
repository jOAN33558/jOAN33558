"""Altura mínima, límites geométricos de nervios y acero de retracción y temperatura."""
from __future__ import annotations

from math import floor

from .flexion import area, cuantia_minima_maciza
from .memoria import Memoria, estado, fmt
from .modelos import Losa, Materiales, Pano, Piso, Verificacion
from .seccion import Seccion

ALFA_MIN_TABLAS = 0.2    # por debajo, la losa se comporta como losa plana (ACI 8.3.1.1)


def limites_nervios(losa: Losa, mem: Memoria | None = None) -> list[Verificacion]:
    """ACI 318-19, 9.8.1.2 a 9.8.1.4 y 9.8.2/9.8.3 (igual que la hoja de referencia)."""
    if not losa.nervada:
        return []
    bw, h, el = losa.ancho_nervio, losa.altura, losa.loseta
    libre = losa.separacion_nervios - bw
    lim_el = max(5.0, libre / 12)
    v = [
        Verificacion("Nervios: ancho bw >= 10 cm", bw, 10.0, estado(bw >= 10),
                     "ACI 318-19, 9.8.1.2"),
        Verificacion("Nervios: altura total h <= 3,5·bw", h, 3.5 * bw, estado(h <= 3.5 * bw),
                     "ACI 318-19, 9.8.1.3"),
        Verificacion("Nervios: separación libre <= 75 cm", libre, 75.0, estado(libre <= 75),
                     "ACI 318-19, 9.8.1.4"),
        Verificacion("Nervios: loseta el >= máx(5 cm ; libre/12)", el, lim_el, estado(el >= lim_el),
                     "ACI 318-19, 9.8.2 y 9.8.3"),
    ]
    if mem:
        mem.seccion("LÍMITES GEOMÉTRICOS DE LOS NERVIOS")
        for x in v:
            mem.paso(x.nombre, "", f"{fmt(x.valor)} vs {fmt(x.limite)}", x.valor, "cm", x.estado,
                     x.referencia)
    return v


def retraccion_temperatura(losa: Losa, mat: Materiales, mem: Memoria | None = None) -> str:
    """Devuelve el texto del armado de retracción y temperatura."""
    if losa.nervada:
        As = 0.0018 * 100 * losa.loseta
        e1 = min(5 * losa.loseta, 45.0)
        e2 = area(losa.diametro_malla) / As * 100
        e = floor(min(e1, e2))
        texto = (f"Malla electrosoldada Ø{fmt(losa.diametro_malla, 0)} mm @ {e} cm en ambos "
                 f"sentidos (As >= {fmt(As)} cm²/m)")
        if mem:
            mem.seccion("ACERO DE RETRACCIÓN Y TEMPERATURA (loseta)")
            mem.paso("Acero requerido", "As = 0,0018·100·el", f"0,0018·100·{fmt(losa.loseta)}", As,
                     "cm²/m", referencia="ACI 318-19, 24.4.3.2")
            mem.paso("Separación máxima", "mín(5·el ; 45 cm)", f"mín({fmt(5 * losa.loseta)} ; 45)",
                     e1, "cm", referencia="ACI 318-19, 24.4.3.3")
            mem.paso("Separación por área", "AØ·100/As",
                     f"{fmt(area(losa.diametro_malla), 3)}·100/{fmt(As)}", e2, "cm")
            mem.paso("Armado", "", "", texto)
        return texto
    rho = cuantia_minima_maciza(mat.fy)
    As = rho * 100 * losa.altura
    phi = losa.diametros[0]
    s = min(floor(area(phi) * 100 / As / 2.5) * 2.5, 5 * losa.altura, 45.0)
    texto = f"Ø{phi} @ {fmt(s, 1 if s % 1 else 0)} cm (As >= {fmt(As)} cm²/m)"
    if mem:
        mem.seccion("ACERO DE RETRACCIÓN Y TEMPERATURA")
        mem.paso("Acero requerido", "As = ρ·100·h", f"{fmt(rho, 4)}·100·{fmt(losa.altura)}", As,
                 "cm²/m", referencia="ACI 318-19, 24.4.3.2")
        mem.paso("Armado en la dirección sin flexión de diseño", "s <= mín(5h ; 45 cm)", "", texto)
    return texto


def alfa_borde(piso: Piso, pano: Pano, borde: str, sec: Seccion) -> float:
    """Relación de rigidez viga/losa en un borde (ACI 318-19, 8.10.2.7), como la hoja."""
    viga = piso.viga_en(pano.eje_de(borde))
    if pano.cond[borde] == "libre" or viga is None or viga.b <= 0 or viga.h <= 0:
        return 0.0
    propio = pano.luz_perpendicular(borde) * 100
    vol = pano.volado_en(borde)
    if vol:
        ancho = propio / 2 + vol.longitud * 100
    elif pano.vecinos[borde]:
        vecino = piso.pano(max(pano.vecinos[borde], key=lambda t: t[1])[0])
        ancho = (propio + vecino.luz_perpendicular(borde) * 100) / 2
    else:
        ancho = (propio + viga.b) / 2
    return (viga.b * viga.h**3 / 12) / (sec.Ig * ancho / sec.b_ala)


def ancho_viga(piso: Piso, pano: Pano, borde: str) -> float:
    viga = piso.viga_en(pano.eje_de(borde))
    return viga.b if viga and pano.cond[borde] != "libre" else 0.0


def hmin_bidireccional(piso: Piso, pano: Pano, largos, cortos, alfas: dict[str, float],
                       sec: Seccion, mem: Memoria | None = None) -> Verificacion:
    """Espesor mínimo de losa en dos direcciones con vigas (ACI 318-19, 8.3.1.2)."""
    fy = piso.materiales.fy
    Lx, Ly = pano.luz_perpendicular(largos[0]), pano.luz_perpendicular(cortos[0])
    ln_c = Lx * 100 - sum(ancho_viga(piso, pano, b) for b in largos) / 2
    ln_l = Ly * 100 - sum(ancho_viga(piso, pano, b) for b in cortos) / 2
    beta = ln_l / ln_c
    am = sum(alfas.values()) / 4
    k = 0.8 + fy / 14000
    if am > 2:
        h, piso_min, formula = ln_l * k / (36 + 9 * beta), 9.0, "ln·(0,8 + fy/14000)/(36 + 9β)"
        sust = f"{fmt(ln_l)}·{fmt(k, 3)}/(36 + 9·{fmt(beta, 3)})"
    else:
        h, piso_min = ln_l * k / (36 + 5 * beta * (am - 0.2)), 12.5
        formula = "ln·(0,8 + fy/14000)/(36 + 5β·(αm − 0,2))"
        sust = f"{fmt(ln_l)}·{fmt(k, 3)}/(36 + 5·{fmt(beta, 3)}·({fmt(am, 3)} − 0,2))"
    hmin = max(h, piso_min)
    debiles = [b for b in largos + cortos
               if pano.cond[b] != "continuo" and alfas[b] < 0.8]
    if debiles:
        hmin *= 1.10
    valor = sec.he if sec.nervada else sec.h
    nombre = "Altura equivalente he >= hmín" if sec.nervada else "Altura h >= hmín"
    v = Verificacion(nombre, valor, hmin, estado(valor >= hmin), "ACI 318-19, 8.3.1.2")
    if mem:
        for b, a in alfas.items():
            mem.paso(f"Rigidez relativa viga/losa, borde {b} (eje {pano.eje_de(b)})",
                     "α = Iviga/Ilosa", "", a, "", referencia="ACI 318-19, 8.10.2.7", nd=3)
        mem.paso("Rigidez relativa media", "αm = promedio de los cuatro bordes", "", am, "", nd=3)
        if am <= 2:
            mem.nota("αm <= 2: vigas de rigidez intermedia. Las tablas de coeficientes suponen "
                     "apoyos indeformables; con vigas flexibles los momentos positivos y las "
                     "flechas reales pueden ser mayores.")
        mem.paso("Luz libre larga / luz libre corta", "β = ln,larga/ln,corta",
                 f"{fmt(ln_l)}/{fmt(ln_c)}", beta, "", nd=3)
        mem.paso("Espesor mínimo", formula, sust, h, "cm",
                 f"y no menor que {fmt(piso_min, 1)} cm", "ACI 318-19, Tabla 8.3.1.2")
        if debiles:
            mem.paso("Aumento de 10 % por borde discontinuo sin viga rígida (α < 0,8)",
                     "1,10·hmín", f"bordes: {', '.join(debiles)}", hmin, "cm",
                     referencia="ACI 318-19, 8.3.1.2.1")
        mem.paso(nombre, "", f"{fmt(valor)} vs {fmt(hmin)}", valor, "cm", v.estado, v.referencia)
    return v


def hmin_unidireccional(luz: float, continuos: int, losa: Losa, fy: float,
                        mem: Memoria | None = None, voladizo: bool = False) -> Verificacion:
    """Altura mínima en una dirección: ACI 318-19 Tabla 7.3.1.1 (maciza) o 9.3.1.1 (nervios).

    ``continuos`` es el número de extremos continuos del vano (0, 1 o 2).
    """
    if losa.nervada:
        den, ref = (8.0 if voladizo else (16.0, 18.5, 21.0)[continuos]), "ACI 318-19, Tabla 9.3.1.1"
    else:
        den, ref = (10.0 if voladizo else (20.0, 24.0, 28.0)[continuos]), "ACI 318-19, Tabla 7.3.1.1"
    k = 0.4 + fy / 7000
    hmin = luz * 100 / den * k
    caso = "voladizo" if voladizo else ("simplemente apoyado", "un extremo continuo",
                                        "ambos extremos continuos")[continuos]
    v = Verificacion(f"Altura h >= L/{fmt(den, 1)} ({caso})", losa.altura, hmin,
                     estado(losa.altura >= hmin), ref)
    if mem:
        mem.paso(f"Altura mínima ({caso})", f"hmín = L/{fmt(den, 1)}·(0,4 + fy/7000)",
                 f"{fmt(luz * 100)}/{fmt(den, 1)}·{fmt(k, 3)}", hmin, "cm",
                 f"{v.estado}: h = {fmt(losa.altura)} cm", ref)
    return v
