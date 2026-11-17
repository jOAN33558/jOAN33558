# Diseño de losas de un piso (hormigón armado, Ecuador)

Guía para continuar el trabajo en otra sesión de Claude Code. Todo el proyecto está en
la carpeta `diseno_losas/` de la rama `claude/reinforced-concrete-slab-designer-3w34x6`.
La rama `main` solo tiene el README del perfil de GitHub: si no ves `diseno_losas/`,
ejecuta `git fetch origin && git checkout claude/reinforced-concrete-slab-designer-3w34x6`.

## Cómo trabajar con el usuario

- Todo en español. Unidades: kg, cm, m (kg/cm², kg/m², kg·m/m), como su hoja original.
- Normas: NEC-SE-HM y NEC-SE-CG; ACI 318-19 para el detalle.
- Excel sin emojis, fuente Arial. CUMPLE / NO CUMPLE en verde y rojo.
- No inventar valores de tablas normativas: si falta uno, preguntar o dejarlo como dato
  de entrada marcado. Los casos fuera de alcance se avisan, nunca se calculan en silencio.
- El usuario es estudiante o ingeniero civil y trabaja mucho desde el celular. Para
  entregar archivos, dar enlaces directos de GitHub `raw` de la rama, que se
  descargan sin iniciar sesión, por ejemplo:
  `https://github.com/jOAN33558/jOAN33558/raw/claude/reinforced-concrete-slab-designer-3w34x6/diseno_losas/ejemplos/edificio/salida/edificio_vivo.xlsx`
- El repositorio es público. No pasar nada a `main` ni abrir PR sin pedir permiso.

## Qué hay

| Ruta | Contenido |
|---|---|
| `diseno_losas/losas/` | Paquete Python. Entrada `python -m losas archivo.yaml [-o carpeta]` |
| `diseno_losas/losas/datos/` | Tabla 9.7 (nervadas) y Tabla 9.5 (macizas) en CSV, verificadas contra los PDF del usuario |
| `diseno_losas/tests/` | 99 pruebas con pytest |
| `diseno_losas/ejemplos/` | Entradas YAML y salidas generadas |
| `diseno_losas/web/losas_en_vivo.html` | Página interactiva (motor JS que replica el Python, solo bidireccional) |
| `diseno_losas/README.md` | Manual de uso, criterios e hipótesis |

### Salidas de `python -m losas`

1. `<nombre>_memoria.xlsx`: memoria con valores fijos, una hoja por paño (dato,
   fórmula, sustitución, resultado, verificación) y láminas PNG incrustadas
   (`salida_excel.py`, `figuras.py`, `fig_*.py`).
2. `<nombre>_plano.png`: plano esquemático (`plano.py`).
3. `<nombre>_figuras/`: láminas por paño.
4. `<nombre>_vivo.xlsx`: **Excel con fórmulas vivas y gráficos nativos**
   (`excel_edificio.py`). Es lo que el usuario más usa. Hojas: RESUMEN, MEMORIA
   (selector de piso y paño, 5 gráficos), PISOS (hasta 6, con cargas propias),
   PLANTA (existe, bordes, volados), DATOS (hasta 8 ejes por dirección), CALCULO
   (una fila por piso × celda de 7×7) y TABLAS.

### Módulos principales

`entrada.py` (YAML) → `geometria.py` (vecinos, bordes, tipo 1-18) → `analisis.py`
(alcance, clasificación, momentos) → `compatibilidad.py` (máximo M− en bordes
comunes) → `diseno.py` (flexión, cortante, flechas, altura mínima) con `flexion.py`,
`cortante.py`, `flechas.py`, `verificaciones.py`, `volado.py`, `unidireccional.py`,
`viga_continua.py`.

## Decisiones tomadas (no cambiar sin consultar)

- Tipo de paño deducido de los bordes: rayado = continuo, trazos = discontinuo,
  línea = libre. Lx siempre es la luz corta. Tabla de deducción en `geometria.py`.
- Borde con volado: se clasifica discontinuo y su M− se diseña con el mayor entre
  el del paño, el del vecino y el del volado.
- M+ con b = 100 cm (ala comprimida); M− con b = bw·100/s (solo nervios). El usuario
  lo preguntó y se le explicó: es correcto así.
- Varillas: una por nervio del menor diámetro que alcance (12 a 20 mm); si no, dos.
  Peralte por capas: la dirección corta va en la capa exterior.
- Cortante: vc = 1,1·0,53·√f'c en nervios (opción ACI 22.5.5.1 en el programa);
  si no cumple, se revisa el borde del macizado (0,425 m por defecto).
- Flechas con inercia efectiva (ACI Tabla 24.2.3.5, fr = 2·√f'c), λ = 2, límites
  L/360 y L/480 (o L/240 si no soporta mampostería). Por eso salen mayores que en
  la hoja original, que usa sección bruta.
- Tabla 9.7: paño 14, mx+ con Lx/Ly = 0,5 impreso 8187, se usa 916. Valores
  sospechosos dejados como están en el PDF: paño 14 mx+ 0,8 = 998; paño 12 δ 0,8 = 1768.
- Fuera de alcance (avisar, no calcular): losa plana sin vigas, αm < 0,2, paños no
  rectangulares, aberturas grandes, cargas puntuales o lineales, combinaciones de
  bordes no tabuladas.

## Prueba obligatoria y verificación

- Paño de la hoja de referencia (4 × 5 m, tipo 6, Lx/Ly = 0,8): My− = 1783,
  My+ = 988, Mx− = 1356, Mx+ = 587 kg·m/m; armado 1Ø16, 1Ø12, 1Ø14, 1Ø12 por nervio
  (`tests/test_referencia.py`).
- El Excel vivo se verifica recalculándolo con LibreOffice y comparando paño por
  paño con el Python (`tests/test_excel_edificio.py`). Cualquier cambio en las
  fórmulas debe mantener esa igualdad exacta.

```bash
cd diseno_losas
pip install -r requirements.txt
python -m pytest -q                      # 99 pruebas (las de Excel requieren soffice)
python -m losas ejemplos/edificio/edificio.yaml -o ejemplos/edificio/salida
```

## Proyecto del usuario

Ejercicio de su cuaderno: ejes A-B-C-D a 5 m; ejes 1-2 a 4 m y 2-3 a 5 m; vigas
25/45 (las 40/40 son columnas); losa nervada con loseta de 5, nervios de 10 y
bloques de 40 (s = 50), bloques 8 × 16 = 128 kg/m². Oficinas en +2,50 y +5,00
(sobrecarga 340, viva 250); terraza inaccesible en +7,50 (sobrecarga 100, viva 100).
Con h = 20 cm las oficinas no cumplen; con h = 30 cm todo cumple (h = 25 falla
flechas en dos paños de 5 × 5). El peso de bloques debe corregirse para el bloque de
25 cm (pendiente del usuario). Archivos: `ejemplos/ejercicio/` y `ejemplos/edificio/`
(este último con un volado de ejemplo de 1,20 m en el borde sur de A-B y B-C).

## Pendiente (propuesto al usuario, sin respuesta aún)

Llevar al Excel vivo lo que hoy solo hace el programa, en este orden:
1. Losa maciza (Tabla 9.5, franja de 1 m, separación de varillas).
2. Viga distinta por eje.
3. Losa en una dirección (ACI 6.5; viga continua por rigidez si no aplica).
4. Planta propia por piso.

También se ofreció pasar el programa a `main` (requiere permiso del usuario).
