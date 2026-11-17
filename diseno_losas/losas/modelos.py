"""Modelos de datos del piso y de los resultados.

Unidades de todo el paquete (las mismas de la hoja de referencia):
fuerzas en kg, longitudes de sección en cm, luces en m, esfuerzos en kg/cm²,
cargas de área en kg/m² y momentos por metro de ancho en kg·m/m.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from math import sqrt

from .memoria import Memoria

BORDES = ("norte", "sur", "este", "oeste")
OPUESTO = {"norte": "sur", "sur": "norte", "este": "oeste", "oeste": "este"}
CONDICIONES = ("continuo", "discontinuo", "libre")

CALCULADO = "CALCULADO"
FUERA_DE_ALCANCE = "FUERA DE ALCANCE"
MENSAJE_MEF = "Se requiere un modelo de elementos finitos."


class ErrorEntrada(ValueError):
    """Error en el archivo de entrada, con mensaje para el usuario."""


@dataclass
class Materiales:
    fc: float
    fy: float
    peso_hormigon: float = 2400.0
    recubrimiento: float = 2.5
    Es: float = 2.0e6
    Ec: float | None = None

    @property
    def E(self) -> float:
        """Módulo del hormigón; por defecto 15000·√f'c como la hoja de referencia."""
        return self.Ec if self.Ec else 15000.0 * sqrt(self.fc)

    @property
    def beta1(self) -> float:
        return max(0.65, min(0.85, 0.85 - 0.05 * (self.fc - 280.0) / 70.0))

    @property
    def n(self) -> float:
        return self.Es / self.E


@dataclass
class Losa:
    tipo: str                       # "nervada" | "maciza"
    altura: float                   # cm, total
    loseta: float = 0.0             # cm
    ancho_nervio: float = 0.0       # cm
    separacion_nervios: float = 0.0  # cm, eje a eje
    peso_bloques: float = 0.0       # kg/m²
    diametros: list[int] = field(default_factory=list)   # mm
    max_varillas_nervio: int = 2
    macizado: float = 0.425         # m, desde la cara de la viga
    diametro_malla: float = 4.0     # mm

    @property
    def nervada(self) -> bool:
        return self.tipo == "nervada"

    @property
    def hn(self) -> float:
        return self.altura - self.loseta


@dataclass
class Cargas:
    acabados: float = 0.0
    paredes: float = 0.0
    otras: float = 0.0
    viva: float = 0.0
    uso: str = ""
    soporta_mamposteria: bool = True
    fraccion_viva_sostenida: float = 0.0
    lambda_diferida: float = 2.0


@dataclass
class Viga:
    b: float   # cm
    h: float   # cm


@dataclass
class Volado:
    borde: str
    longitud: float                 # m
    medida: str = "eje"             # "eje" (desde el eje de la viga) | "cara"
    carga_borde: float = 0.0        # kg/m, permanente (antepecho)
    carga_borde_viva: float = 0.0   # kg/m
    cargas: dict = field(default_factory=dict)   # reemplazos: viva, paredes, acabados


@dataclass
class Pano:
    id: str
    ejes_x: tuple[str, str]
    ejes_y: tuple[str, str]
    bordes: dict[str, str] = field(default_factory=dict)      # declarados
    volados: list[Volado] = field(default_factory=list)
    cargas: dict = field(default_factory=dict)                # reemplazos
    fuera_de_alcance: list[str] = field(default_factory=list)
    # geometría resuelta (geometria.preparar)
    x0: float = 0.0
    x1: float = 0.0
    y0: float = 0.0
    y1: float = 0.0
    cond: dict[str, str] = field(default_factory=dict)
    vecinos: dict[str, list[tuple[str, float]]] = field(default_factory=dict)

    @property
    def ancho_x(self) -> float:
        return self.x1 - self.x0

    @property
    def ancho_y(self) -> float:
        return self.y1 - self.y0

    def longitud_borde(self, borde: str) -> float:
        return self.ancho_x if borde in ("norte", "sur") else self.ancho_y

    def luz_perpendicular(self, borde: str) -> float:
        """Luz del paño en la dirección perpendicular al borde."""
        return self.ancho_y if borde in ("norte", "sur") else self.ancho_x

    def eje_de(self, borde: str) -> str:
        return {"norte": self.ejes_y[1], "sur": self.ejes_y[0],
                "este": self.ejes_x[1], "oeste": self.ejes_x[0]}[borde]

    def volado_en(self, borde: str) -> Volado | None:
        return next((v for v in self.volados if v.borde == borde), None)


@dataclass
class Opciones:
    cortante: str = "nec"     # "nec" (0,53·√f'c) | "aci318_19" (Tabla 22.5.5.1)


@dataclass
class Piso:
    proyecto: dict
    materiales: Materiales
    losa: Losa
    cargas: Cargas
    viga: Viga | None
    vigas_por_eje: dict[str, Viga]
    ejes_x: dict[str, float]      # nombre -> coordenada (m)
    ejes_y: dict[str, float]
    panos: list[Pano]
    opciones: Opciones = field(default_factory=Opciones)
    avisos: list[str] = field(default_factory=list)

    def pano(self, id_: str) -> Pano:
        return next(p for p in self.panos if p.id == id_)

    def viga_en(self, eje: str) -> Viga | None:
        return self.vigas_por_eje.get(eje, self.viga)


# --------------------------------------------------------------------------
# Resultados
# --------------------------------------------------------------------------
@dataclass
class DisenoFlexion:
    nombre: str
    signo: str            # "+" | "-"
    Mu: float             # kg·m/m
    b: float              # cm por metro de losa (ancho comprimido)
    d: float              # cm
    As_req: float | None  # cm²/m (None si la sección no alcanza)
    As_min: float         # cm²/m
    As_dis: float         # cm²/m
    diametro: int         # mm
    n: int                # varillas por nervio (0 en maciza)
    separacion: float     # cm (maciza; 0 en nervada)
    As_u: float           # cm² colocados por unidad (nervio o metro)
    As_col: float         # cm²/m colocados
    a: float              # cm
    eps_t: float
    armado: str
    cumple: bool
    constructivo: bool = False
    notas: list[str] = field(default_factory=list)


@dataclass
class ResultadoCortante:
    Vu: float             # kg/m a la distancia d de la cara
    vu: float             # kg/cm²
    vc: float             # kg/cm²
    estado: str           # CUMPLE | CUMPLE con macizado | NO CUMPLE
    Vu_mac: float = 0.0
    vu_mac: float = 0.0
    ubicacion: str = ""

    @property
    def cumple(self) -> bool:
        return not self.estado.startswith("NO")


@dataclass
class ResultadoFlechas:
    delta_L: float        # cm, inmediata por carga viva
    lim_L: float
    delta_lp: float       # cm, diferida + viva
    lim_lp: float
    Ie_Ig: float

    @property
    def cumple_L(self) -> bool:
        return self.delta_L <= self.lim_L

    @property
    def cumple_lp(self) -> bool:
        return self.delta_lp <= self.lim_lp

    @property
    def cumple(self) -> bool:
        return self.cumple_L and self.cumple_lp


@dataclass
class Verificacion:
    nombre: str
    valor: float | str
    limite: float | str
    estado: str           # CUMPLE | NO CUMPLE | texto
    referencia: str = ""

    @property
    def cumple(self) -> bool:
        return not self.estado.startswith("NO")


@dataclass
class ResultadoVolado:
    volado: Volado
    L: float              # m, longitud de diseño (desde la cara de la viga)
    L_eje: float          # m, desde el eje de la viga
    D: float              # kg/m²
    Lv: float             # kg/m² (viva)
    Mu: float             # kg·m/m
    Vu: float             # kg/m
    combo: str
    M_D: float = 0.0      # momentos de servicio
    M_L: float = 0.0
    M_pano: float = 0.0   # momento propio del paño en ese borde
    prolongacion: float = 0.0   # m dentro del paño interior
    ld: float = 0.0             # cm
    cortante: ResultadoCortante | None = None
    flechas: ResultadoFlechas | None = None
    checks: list[Verificacion] = field(default_factory=list)


@dataclass
class ResultadoPano:
    pano: Pano
    estado: str = CALCULADO
    motivos: list[str] = field(default_factory=list)
    clasificacion: str = ""            # Bidireccional | Unidireccional
    tipo: int | None = None
    metodo: str = ""
    Lx: float = 0.0
    Ly: float = 0.0
    beta: float = 0.0
    dir_corta: str = "X"               # dirección global de la luz corta
    largos: tuple[str, str] = ("oeste", "este")    # bordes de longitud Ly
    cortos: tuple[str, str] = ("sur", "norte")     # bordes de longitud Lx
    cargas: object | None = None
    coef: dict = field(default_factory=dict)
    M_pos: dict[str, float] = field(default_factory=dict)      # corta / larga
    M_borde: dict[str, float] = field(default_factory=dict)    # propio por borde
    M_dis: dict[str, float] = field(default_factory=dict)      # tras compatibilidad
    origen: dict[str, str] = field(default_factory=dict)
    V_cara: dict[str, float] = field(default_factory=dict)     # por borde de apoyo
    servicio: dict = field(default_factory=dict)               # datos para flechas
    d: dict[str, float] = field(default_factory=dict)
    flexion: dict[str, DisenoFlexion] = field(default_factory=dict)
    cortante: ResultadoCortante | None = None
    flechas: ResultadoFlechas | None = None
    volados: list[ResultadoVolado] = field(default_factory=list)
    checks: list[Verificacion] = field(default_factory=list)
    avisos: list[str] = field(default_factory=list)
    memoria: Memoria = field(default_factory=Memoria)

    @property
    def calculado(self) -> bool:
        return self.estado == CALCULADO

    @property
    def cumple(self) -> bool:
        return self.calculado and all(c.cumple for c in self.checks)

    @property
    def resultado(self) -> str:
        if not self.calculado:
            return FUERA_DE_ALCANCE
        return "CUMPLE" if self.cumple else "NO CUMPLE"

    def direccion_de(self, borde: str) -> str:
        """'corta' o 'larga': dirección de las varillas perpendiculares al borde."""
        return "corta" if borde in self.largos else "larga"


@dataclass
class BordeComun:
    eje: str
    pano_a: str
    borde_a: str
    M_a: float
    pano_b: str
    borde_b: str
    M_b: float
    M_dis: float
    armado: str = ""


@dataclass
class ResultadoPiso:
    piso: Piso
    seccion: object
    panos: dict[str, ResultadoPano]
    bordes_comunes: list[BordeComun]
    memoria_general: Memoria
    checks_generales: list[Verificacion]
    avisos: list[str]

    @property
    def cumple(self) -> bool:
        return self.resultado == "CUMPLE"

    @property
    def resultado(self) -> str:
        """CUMPLE, NO CUMPLE o INCOMPLETO (hay paños fuera de alcance sin calcular)."""
        calculados = [r for r in self.panos.values() if r.calculado]
        if (not all(r.cumple for r in calculados)
                or not all(c.cumple for c in self.checks_generales)):
            return "NO CUMPLE"
        if len(calculados) < len(self.panos):
            return "INCOMPLETO: hay paños fuera de alcance sin calcular"
        return "CUMPLE"
