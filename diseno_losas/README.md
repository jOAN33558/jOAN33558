# Diseño de losas de un piso

Herramienta en Python que diseña todas las losas de un piso de hormigón armado
(losa nervada o maciza apoyada en vigas) y entrega una memoria de cálculo en Excel
y un plano esquemático.

Normas: NEC-SE-HM y NEC-SE-CG; ACI 318-19 para el detalle.
Unidades: kg, cm, m (kg/cm², kg/m², kg·m/m), como la hoja de referencia.

## Uso

```bash
pip install -r requirements.txt
python -m losas ejemplos/piso_ejemplo.yaml --salida ejemplos/salida
```

Genera en la carpeta de salida:

- `piso_ejemplo_memoria.xlsx`: hoja RESUMEN (todos los paños, armado y
  CUMPLE / NO CUMPLE), hoja DATOS, una hoja de memoria por paño (dato, fórmula,
  sustitución, resultado, verificación y referencia), la tabla de coeficientes
  usada y el plano.
- `piso_ejemplo_plano.png`: plano esquemático con los paños, su tipo y el armado.

Ejemplos incluidos, con su salida ya generada en `ejemplos/salida/`:

| Archivo | Contenido |
|---|---|
| `ejemplos/piso_ejemplo.yaml` | Piso de seis paños: bidireccionales, uno unidireccional, un volado con antepecho y un paño fuera de alcance |
| `ejemplos/pano_referencia.yaml` | El paño de la hoja de referencia (4 x 5 m, tipo 6) |

## Archivo de entrada

Es un YAML. `ejemplos/piso_ejemplo.yaml` está comentado campo por campo.

| Sección | Datos |
|---|---|
| `materiales` | `fc`, `fy`, `peso_hormigon`, `recubrimiento`; opcionales `Ec`, `Es` |
| `losa` | `tipo` (nervada o maciza), `altura`, `loseta`, `ancho_nervio`, `separacion_nervios`, `peso_bloques`; opcionales `diametros`, `max_varillas_nervio`, `macizado`, `diametro_malla` |
| `cargas` | `acabados`, `paredes`, `otras`, `viva`, `uso`, `soporta_mamposteria`; opcionales `fraccion_viva_sostenida`, `lambda_diferida` |
| `vigas` | `b`, `h`; opcional `por_eje` para vigas distintas |
| `ejes` | `x` e `y`, cada uno con `nombres` y `distancias` |
| `opciones` | `cortante`: `nec` (por defecto) o `aci318_19` |
| `panos` | `id`, `ejes_x`, `ejes_y`, `bordes`, `volado` o `volados`, `viva` y otras cargas propias, `fuera_de_alcance` |

Bordes de cada paño (`norte`, `sur`, `este`, `oeste`): `auto`, `continuo`,
`discontinuo` o `libre`. Con `auto` el borde es continuo si hay un paño vecino y
discontinuo si es perimetral. El borde libre siempre se declara.

Volado: `borde`, `longitud`, `medida` (`eje` por defecto, o `cara`),
`carga_borde` (permanente, kg/m), `carga_borde_viva` y cargas propias opcionales.

La carga viva es un número que usted toma de la NEC-SE-CG; `uso` es solo una
etiqueta. El programa no trae valores normativos de carga.

## Qué calcula

1. **Clasificación.** Lx/Ly >= 0,5: dos direcciones. Menor: una dirección. Un
   paño apoyado solo en dos bordes opuestos también es unidireccional.
2. **Tipo de paño (1 a 18).** Se deduce de los bordes. Lx es siempre la luz corta.
3. **Dos direcciones.** M = 0,0001·q·m·Lx² con la Tabla 9.7 (nervada) o la
   Tabla 9.5 (maciza), interpolando en Lx/Ly. Se toma la envolvente con los
   momentos de borde libre.
4. **Una dirección.** Franja de 1 m continua a través de los paños vecinos.
   Coeficientes de ACI 318-19 6.5 si se cumplen sus condiciones; si no, viga
   continua por rigidez con carga viva alternada.
5. **Volado.** Mu = qu·L²/2 + Pu·L y Vu = qu·L + Pu en la cara de la viga, altura
   mínima L/8 (nervios) o L/10 (maciza), flecha en la punta y prolongación del
   acero negativo dentro del paño interior.
6. **Compatibilidad.** En cada borde común se diseña con el mayor de los dos
   momentos negativos, y con el del volado si lo hay.
7. **Flexión.** Acero requerido y mínimo, varillas por nervio o separación,
   bloque de compresión y εt >= 0,005. En momento negativo de losa nervada el
   ancho comprimido es el de los nervios.
8. **Cortante.** Solo nervios, con el aumento de 10 % de ACI 9.8.1.5 si cumple la
   geometría; se revisa el borde del macizado y la zona maciza.
9. **Flechas.** Con cargas de servicio e inercia efectiva (ACI Tabla 24.2.3.5),
   contra L/360 y L/480 o L/240.
10. **Altura mínima**, límites geométricos de nervios y acero de retracción.
11. **Combinaciones.** La mayor de 1,4D y 1,2D + 1,6L.

## Criterios e hipótesis que conviene conocer

- **Flechas con sección fisurada.** La hoja de referencia usa sección sin fisurar.
  Aquí la flecha de la tabla se multiplica por Ig/Ie, con fr = 2·√f'c. En losas
  nervadas poco armadas Ie baja a 0,2-0,3 de Ig, así que las flechas salen entre
  tres y cinco veces mayores que en la hoja. El paño de referencia cumple
  flexión y cortante pero no la flecha diferida L/480 (1,06 cm frente a 0,83 cm).
- **Cortante del hormigón.** Por defecto vc = 0,53·√f'c (NEC-SE-HM, igual a la
  hoja). Con `opciones.cortante: aci318_19` se usa la Tabla 22.5.5.1, que da
  menos resistencia.
- **Cortante en dos direcciones.** Como la hoja: Vu = qu·(Lx/2 − b/2 − d). Con un
  borde largo libre se toma toda la franja corta sobre el apoyo opuesto.
- **Borde con volado.** Se clasifica como discontinuo (conservador para el
  momento positivo) y su acero negativo se diseña con el momento del volado. Se
  puede forzar `continuo`.
- **Varillas.** Una varilla por nervio del menor diámetro que alcance, con Ø
  mínimo 12 mm; si no alcanza, dos. La lista `diametros` es editable.
- **Peralte por capas.** La dirección corta va en la capa exterior.
- **Acero mínimo en bordes sin momento.** Los bordes discontinuos llevan acero
  superior constructivo igual al mínimo.
- **Franja unidireccional.** Los apoyos son articulados en los ejes de las vigas
  y los paños vecinos se cargan con toda su carga en esa dirección.
- **Prolongación del acero del volado.** Punto de inflexión del paño interior con
  carga mínima 0,9·D repartida por Grashof, más máx(d; 12db; ln/16), y no menos
  que ld (ACI 25.4.2.3).
- **Módulo del hormigón.** Ec = 15000·√f'c como la hoja; se puede dar `Ec`.
- **Vigas de rigidez intermedia.** Las tablas suponen apoyos indeformables. La
  memoria lo advierte cuando αm <= 2.

## Fuera de alcance

El programa lo detecta, avisa y no calcula el paño. En el resumen y en su hoja
aparece FUERA DE ALCANCE con el motivo y la indicación de usar un modelo de
elementos finitos.

| Caso | Cómo se detecta |
|---|---|
| Losa plana sin vigas (punzonamiento) | Borde apoyado sin viga, o `sin_vigas` |
| Vigas muy flexibles | αm < 0,2 (ACI 318-19, 8.3.1.1) |
| Paño no rectangular | `no_rectangular` |
| Abertura grande | `abertura` |
| Carga puntual o lineal dentro del paño | `carga_puntual`, `carga_lineal` |
| Combinación de bordes no tabulada | No existe entre los 18 tipos |
| Tres o más bordes libres | Es un voladizo, no un paño |
| Lx/Ly < 0,5 con un borde largo libre | La franja corta trabaja como volado |

## Tablas de coeficientes

Están en `losas/datos/` y se verificaron contra los PDF entregados.

- **Tabla 9.7 a-d (nervadas).** Coincide con la hoja TABLAS del Excel de
  referencia en los 18 tipos. Única corrección: paño 14, mx+ con Lx/Ly = 0,5,
  impreso 8187, se usa 916.
- **Tabla 9.5 a-d (macizas, μ = 0,20).** Transcrita del PDF. Cumple la simetría
  entre tipos espejo en Lx/Ly = 1,0.
- Dos valores rompen la tendencia de su fila pero están impresos así en el PDF y
  se dejaron sin cambio: paño 14, mx+ con Lx/Ly = 0,8 (998), y paño 12, δ con
  Lx/Ly = 0,8 (1768).

## Pruebas

```bash
python -m pytest
```

| Archivo | Qué prueba |
|---|---|
| `test_referencia.py` | Paño de la hoja: 1783, 988, 1356 y 587 kg·m/m; 1Ø16, 1Ø12, 1Ø14, 1Ø12 |
| `test_unidireccional.py` | Un vano simplemente apoyado da q·L²/8; coeficientes ACI; rigidez |
| `test_volado.py` | q·L²/2 y q·L; carga de borde; volado dentro del piso |
| `test_bidireccional.py` | Paño cuadrado, borde libre, interpolación, losa maciza |
| `test_tipos.py` | Los 18 tipos, combinaciones no tabuladas, tablas |
| `test_piso.py` | Piso de 3 x 3, compatibilidad, cortante que no cumple, fuera de alcance, errores de entrada |
| `test_secciones.py` | Sección T, flexión, inercia efectiva, nervios, malla |
| `test_salida.py` | Excel (hojas, fuente Arial, sin emojis) y plano |

## Módulos

| Módulo | Contenido |
|---|---|
| `entrada.py` | Lectura y validación del YAML |
| `geometria.py` | Vecinos, bordes automáticos y tipo de paño |
| `tablas.py` | Coeficientes e interpolación |
| `seccion.py`, `cargas.py` | Sección T, peso propio y combinaciones |
| `analisis.py` | Alcance, clasificación y momentos de cada paño |
| `unidireccional.py`, `viga_continua.py` | Coeficientes ACI 6.5 y método de rigidez |
| `volado.py` | Volados |
| `compatibilidad.py` | Momentos negativos en bordes comunes |
| `flexion.py`, `cortante.py`, `flechas.py`, `verificaciones.py` | Diseño y chequeos |
| `diseno.py` | Orquestador |
| `salida_excel.py`, `plano.py` | Salidas |

Este programa es una ayuda de cálculo. El diseño debe ser revisado y firmado por
el ingeniero responsable.
