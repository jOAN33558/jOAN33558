"""Uso:  python -m losas entrada.yaml [--salida carpeta]"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

from . import disenar_piso, leer
from .modelos import ErrorEntrada
from .plano import dibujar
from .salida_excel import escribir


def ejecutar(entrada: str | Path, salida: str | Path | None = None):
    """Diseña el piso descrito en ``entrada`` y escribe el Excel y el plano."""
    entrada = Path(entrada)
    carpeta = Path(salida) if salida else entrada.parent / "salida"
    resultado = disenar_piso(leer(entrada))
    plano = dibujar(resultado, carpeta / f"{entrada.stem}_plano.png")
    excel = escribir(resultado, carpeta / f"{entrada.stem}_memoria.xlsx", plano)
    return resultado, excel, plano


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(prog="losas", description="Diseño de losas de un piso "
                                 "(NEC-SE-HM, NEC-SE-CG, ACI 318-19).")
    ap.add_argument("entrada", help="archivo YAML con la descripción del piso")
    ap.add_argument("--salida", "-o", help="carpeta de salida (por defecto: ./salida junto a la entrada)")
    args = ap.parse_args(argv)
    try:
        res, excel, plano = ejecutar(args.entrada, args.salida)
    except ErrorEntrada as e:
        print(f"ERROR EN LA ENTRADA: {e}", file=sys.stderr)
        return 2
    print(f"{'Paño':<8}{'Clasificación':<26}{'Resultado'}")
    for r in res.panos.values():
        clasif = (f"Bidireccional, tipo {r.tipo}" if r.tipo else r.clasificacion or "-")
        print(f"{r.pano.id:<8}{clasif if r.calculado else 'No calculado':<26}{r.resultado}")
    if res.avisos:
        print("\nAVISOS:")
        for a in res.avisos:
            print(" - " + a)
    print(f"\nMemoria: {excel}\nPlano:   {plano}")
    print("RESULTADO DEL PISO: " + res.resultado)
    return 0


if __name__ == "__main__":
    sys.exit(main())
