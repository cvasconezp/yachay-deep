"""
Generador de mapas coropléticos cualitativos del Ecuador a nivel de cantones (ADM2).

Usa GeoPandas + Matplotlib para renderizar mapas limpios (estilo Power BI)
de cada provincia, resaltando la ciudad de procedencia del estudiante.

USO:
    # Generar mapa de una provincia específica, resaltando un cantón:
    python generar_mapas_cantones.py --provincia PICHINCHA --ciudad QUITO

    # Generar mapas de todas las provincias (galería):
    python generar_mapas_cantones.py --todas

    # Exportar como SVG limpio:
    python generar_mapas_cantones.py --provincia GUAYAS --ciudad GUAYAQUIL --formato svg

    # Exportar como PNG de alta resolución:
    python generar_mapas_cantones.py --provincia IMBABURA --ciudad OTAVALO --formato png --dpi 300

REQUISITOS:
    pip install geopandas matplotlib

DATOS GEOGRÁFICOS:
    El script necesita un archivo GeoJSON o Shapefile con la división política
    a nivel de cantones (ADM2) de Ecuador. Opciones de descarga:

    1. GADM (recomendado para uso académico):
       https://gadm.org/download_country.html ->Ecuador ->Level 2 (GeoJSON)
       Archivo: gadm41_ECU_2.json
       Guardar en: data/geo/gadm41_ECU_2.json

    2. INEC (Instituto Nacional de Estadística y Censos):
       https://www.ecuadorencifras.gob.ec/documentos/web-inec/Cartografia/
       Descargar: nxcantones.shp (y archivos asociados .dbf, .shx, .prj)
       Guardar en: data/geo/

    3. Natural Earth / DIVA-GIS:
       https://www.diva-gis.org/gdata ->Ecuador ->Administrative areas

    El script busca automáticamente archivos en data/geo/ con extensión
    .geojson, .json, o .shp que contengan geometría de cantones.
"""

import argparse
import sys
from pathlib import Path
from typing import Optional

try:
    import geopandas as gpd
    import matplotlib.pyplot as plt
    import matplotlib.patheffects as pe
    from matplotlib.patches import FancyBboxPatch
    import numpy as np
except ImportError as e:
    print(f"Error: {e}")
    print("Instala las dependencias: pip install geopandas matplotlib")
    sys.exit(1)


# ─────────────────────────────────────────────────────────────────────────────
# CONFIGURACIÓN DE ESTILO
# ─────────────────────────────────────────────────────────────────────────────

# Paleta de colores (estilo institucional YachayDeep)
COLOR_PROVINCIA_BASE   = "#D6E4F0"   # Azul claro para cantones normales
COLOR_CANTON_RESALTADO = "#1B3A6B"   # Azul oscuro institucional para cantón seleccionado
COLOR_BORDE            = "#FFFFFF"   # Blanco para bordes internos (estilo Power BI)
COLOR_BORDE_EXTERIOR   = "#8FA8C8"   # Gris-azul para borde de la provincia
COLOR_TEXTO            = "#1B3A6B"   # Azul oscuro para etiquetas
COLOR_FONDO            = "none"      # Transparente

BORDE_INTERIOR_WIDTH = 0.5   # Ancho de bordes entre cantones
BORDE_EXTERIOR_WIDTH = 1.2   # Ancho del borde de la provincia

# Fuentes
FONT_TITULO  = {"fontsize": 14, "fontweight": "bold", "color": COLOR_TEXTO, "fontfamily": "sans-serif"}
FONT_CANTON  = {"fontsize": 7, "fontweight": "normal", "color": "#333333", "fontfamily": "sans-serif"}
FONT_RESALT  = {"fontsize": 8, "fontweight": "bold", "color": "#FFFFFF", "fontfamily": "sans-serif"}


# ─────────────────────────────────────────────────────────────────────────────
# NORMALIZACIÓN DE NOMBRES
# ─────────────────────────────────────────────────────────────────────────────

def normalizar(texto: Optional[str]) -> str:
    """Normaliza un nombre geográfico para comparaciones flexibles."""
    if not texto:
        return ""
    import unicodedata
    texto = unicodedata.normalize("NFD", str(texto))
    texto = "".join(c for c in texto if unicodedata.category(c) != "Mn")
    return texto.strip().upper()


# ─────────────────────────────────────────────────────────────────────────────
# DETECCIÓN AUTOMÁTICA DEL ARCHIVO GEOGRÁFICO
# ─────────────────────────────────────────────────────────────────────────────

def encontrar_geodata(base_path: Path) -> Optional[Path]:
    """Busca archivos GeoJSON/Shapefile de cantones de Ecuador en data/geo/."""
    geo_dir = base_path / "data" / "geo"
    if not geo_dir.exists():
        geo_dir.mkdir(parents=True, exist_ok=True)
        return None

    # Prioridad: GeoJSON > Shapefile
    for pattern in ("*ECU*2*.geojson", "*ECU*2*.json", "*canton*.*", "*cantones*.*"):
        matches = list(geo_dir.glob(pattern))
        if matches:
            return matches[0]

    # Fallback: cualquier archivo geoespacial
    for ext in (".geojson", ".json", ".shp"):
        matches = list(geo_dir.glob(f"*{ext}"))
        if matches:
            return matches[0]

    return None


def detectar_columnas(gdf: gpd.GeoDataFrame) -> dict:
    """
    Detecta automáticamente las columnas de nombre de provincia y cantón
    en el GeoDataFrame, independientemente del formato del archivo.

    Soporta: GADM (NAME_1, NAME_2), INEC (DPA_DESPRO, DPA_DESCAN),
    y otros formatos comunes.
    """
    cols = {c.upper(): c for c in gdf.columns}

    # Columna de PROVINCIA (ADM1)
    provincia_col = None
    for candidato in ("NAME_1", "PROVINCIA", "DPA_DESPRO", "ADM1_ES", "PROV", "NOM_PROV"):
        if candidato.upper() in cols:
            provincia_col = cols[candidato.upper()]
            break
    if not provincia_col:
        # Heurística: buscar columna que tenga ~24 valores únicos (provincias de Ecuador)
        for col in gdf.columns:
            if gdf[col].dtype == object and 20 <= gdf[col].nunique() <= 26:
                provincia_col = col
                break

    # Columna de CANTÓN (ADM2)
    canton_col = None
    for candidato in ("NAME_2", "CANTON", "DPA_DESCAN", "ADM2_ES", "NOM_CAN", "NOMBRE"):
        if candidato.upper() in cols:
            canton_col = cols[candidato.upper()]
            break
    if not canton_col:
        # Heurística: columna con más valores únicos que la de provincia
        for col in gdf.columns:
            if col == provincia_col:
                continue
            if gdf[col].dtype == object and gdf[col].nunique() > 100:
                canton_col = col
                break

    return {"provincia": provincia_col, "canton": canton_col}


# ─────────────────────────────────────────────────────────────────────────────
# GENERACIÓN DEL MAPA
# ─────────────────────────────────────────────────────────────────────────────

def generar_mapa_provincia(
    gdf: gpd.GeoDataFrame,
    col_provincia: str,
    col_canton: str,
    provincia: str,
    ciudad_resaltada: Optional[str] = None,
    titulo: Optional[str] = None,
    formato: str = "png",
    salida: Optional[Path] = None,
    dpi: int = 200,
    mostrar: bool = True,
):
    """
    Genera un mapa coroplético de una provincia mostrando todos sus cantones.

    Args:
        gdf: GeoDataFrame con geometría de cantones de Ecuador
        col_provincia: nombre de la columna de provincia
        col_canton: nombre de la columna de cantón
        provincia: nombre de la provincia a visualizar
        ciudad_resaltada: nombre del cantón a resaltar (ciudad de procedencia)
        titulo: título del mapa (default: nombre de la provincia)
        formato: "png", "svg", o "pdf"
        salida: ruta del archivo de salida (default: auto-generado)
        dpi: resolución en DPI (solo para PNG)
        mostrar: si True, muestra el mapa en pantalla
    """
    # Normalizar para búsqueda flexible
    prov_norm = normalizar(provincia)
    gdf["_prov_norm"] = gdf[col_provincia].apply(normalizar)
    gdf["_cant_norm"] = gdf[col_canton].apply(normalizar)

    # Filtrar cantones de la provincia
    mask = gdf["_prov_norm"] == prov_norm
    if not mask.any():
        # Intentar match parcial
        mask = gdf["_prov_norm"].str.contains(prov_norm, na=False)

    if not mask.any():
        print(f"Error: Provincia '{provincia}' no encontrada.")
        print(f"Provincias disponibles: {sorted(gdf[col_provincia].unique())}")
        return

    gdf_prov = gdf[mask].copy()
    print(f"Provincia: {gdf_prov[col_provincia].iloc[0]} ->{len(gdf_prov)} cantones")

    # Determinar cantón resaltado
    canton_mask = None
    if ciudad_resaltada:
        ciudad_norm = normalizar(ciudad_resaltada)
        canton_mask = gdf_prov["_cant_norm"] == ciudad_norm
        if not canton_mask.any():
            canton_mask = gdf_prov["_cant_norm"].str.contains(ciudad_norm, na=False)
        if not canton_mask.any():
            print(f"  Aviso: Cantón '{ciudad_resaltada}' no encontrado en {provincia}.")
            print(f"  Cantones disponibles: {sorted(gdf_prov[col_canton].unique())}")
            canton_mask = None

    # Asignar colores
    gdf_prov["_color"] = COLOR_PROVINCIA_BASE
    if canton_mask is not None and canton_mask.any():
        gdf_prov.loc[canton_mask, "_color"] = COLOR_CANTON_RESALTADO

    # ── Crear figura ─────────────────────────────────────────────────────
    fig, ax = plt.subplots(1, 1, figsize=(8, 8), facecolor=COLOR_FONDO)
    ax.set_facecolor(COLOR_FONDO)

    # Dibujar todos los cantones de la provincia
    gdf_prov.plot(
        ax=ax,
        color=gdf_prov["_color"],
        edgecolor=COLOR_BORDE,
        linewidth=BORDE_INTERIOR_WIDTH,
    )

    # Borde exterior de la provincia (dissolve ->contorno)
    provincia_contorno = gdf_prov.dissolve()
    provincia_contorno.boundary.plot(
        ax=ax,
        color=COLOR_BORDE_EXTERIOR,
        linewidth=BORDE_EXTERIOR_WIDTH,
    )

    # ── Etiquetas de cantones ────────────────────────────────────────────
    for _, row in gdf_prov.iterrows():
        centroid = row.geometry.representative_point()
        nombre = str(row[col_canton])
        is_resaltado = canton_mask is not None and canton_mask.loc[row.name]

        if is_resaltado:
            font_props = FONT_RESALT.copy()
            # Sombra para legibilidad sobre fondo oscuro
            path_effects = [
                pe.withStroke(linewidth=2.5, foreground="#1B3A6B"),
            ]
        else:
            font_props = FONT_CANTON.copy()
            path_effects = [
                pe.withStroke(linewidth=1.5, foreground="white"),
            ]

        ax.annotate(
            nombre.title(),
            xy=(centroid.x, centroid.y),
            ha="center", va="center",
            path_effects=path_effects,
            **font_props,
        )

    # ── Limpieza: sin ejes, sin recuadro (mapa flotante) ────────────────
    ax.set_axis_off()

    # Título
    if titulo is None:
        prov_display = gdf_prov[col_provincia].iloc[0]
        titulo = f"Provincia de {prov_display.title()}"
    if titulo:
        ax.set_title(titulo, pad=15, **FONT_TITULO)

    # Leyenda si hay cantón resaltado
    if canton_mask is not None and canton_mask.any():
        canton_nombre = gdf_prov.loc[canton_mask, col_canton].iloc[0]
        from matplotlib.patches import Patch
        legend_elements = [
            Patch(facecolor=COLOR_CANTON_RESALTADO, edgecolor=COLOR_BORDE,
                  label=f"Ciudad: {canton_nombre.title()}"),
            Patch(facecolor=COLOR_PROVINCIA_BASE, edgecolor=COLOR_BORDE,
                  label="Otros cantones"),
        ]
        ax.legend(
            handles=legend_elements,
            loc="lower right",
            frameon=True,
            facecolor="white",
            edgecolor="#E0E0E0",
            fontsize=8,
        )

    plt.tight_layout()

    # ── Exportar ─────────────────────────────────────────────────────────
    if salida is None:
        prov_slug = normalizar(provincia).lower().replace(" ", "_")
        ciudad_slug = normalizar(ciudad_resaltada or "").lower().replace(" ", "_")
        nombre_archivo = f"mapa_{prov_slug}"
        if ciudad_slug:
            nombre_archivo += f"_{ciudad_slug}"
        salida = Path(f"data/geo/output/{nombre_archivo}.{formato}")

    salida.parent.mkdir(parents=True, exist_ok=True)

    save_kwargs = {"bbox_inches": "tight", "facecolor": fig.get_facecolor()}
    if formato == "svg":
        save_kwargs["format"] = "svg"
    elif formato == "pdf":
        save_kwargs["format"] = "pdf"
    else:
        save_kwargs["dpi"] = dpi

    fig.savefig(str(salida), **save_kwargs)
    print(f"Mapa guardado en: {salida}")

    if mostrar:
        plt.show()
    else:
        plt.close(fig)

    return salida


def generar_galeria(
    gdf: gpd.GeoDataFrame,
    col_provincia: str,
    col_canton: str,
    formato: str = "png",
    dpi: int = 150,
):
    """Genera un mapa para cada provincia de Ecuador."""
    provincias = sorted(gdf[col_provincia].unique())
    print(f"\nGenerando {len(provincias)} mapas de provincias...\n")

    for prov in provincias:
        try:
            generar_mapa_provincia(
                gdf, col_provincia, col_canton,
                provincia=prov,
                formato=formato,
                dpi=dpi,
                mostrar=False,
            )
        except Exception as e:
            print(f"  Error en {prov}: {e}")

    print(f"\nGalería completa: {len(provincias)} mapas generados en data/geo/output/")


# ─────────────────────────────────────────────────────────────────────────────
# CLI
# ─────────────────────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(
        description="Genera mapas coropléticos de Ecuador a nivel de cantones (ADM2).",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Ejemplos:
  python generar_mapas_cantones.py --provincia PICHINCHA --ciudad QUITO
  python generar_mapas_cantones.py --provincia GUAYAS --ciudad GUAYAQUIL --formato svg
  python generar_mapas_cantones.py --todas --formato png --dpi 300
  python generar_mapas_cantones.py --archivo data/geo/gadm41_ECU_2.json --provincia IMBABURA
        """,
    )
    parser.add_argument("--provincia", "-p", help="Nombre de la provincia a visualizar")
    parser.add_argument("--ciudad", "-c", help="Nombre del cantón/ciudad a resaltar")
    parser.add_argument("--todas", action="store_true", help="Generar mapas de todas las provincias")
    parser.add_argument("--archivo", "-a", help="Ruta al archivo GeoJSON o Shapefile de cantones")
    parser.add_argument("--formato", "-f", default="png", choices=["png", "svg", "pdf"],
                        help="Formato de salida (default: png)")
    parser.add_argument("--dpi", type=int, default=200, help="Resolución DPI para PNG (default: 200)")
    parser.add_argument("--listar", action="store_true", help="Listar provincias y cantones disponibles")
    parser.add_argument("--no-mostrar", action="store_true", help="No mostrar el mapa en pantalla")

    args = parser.parse_args()

    # Buscar o cargar archivo geográfico
    base_path = Path(__file__).parent
    if args.archivo:
        geo_path = Path(args.archivo)
    else:
        geo_path = encontrar_geodata(base_path)

    if not geo_path or not geo_path.exists():
        print("=" * 70)
        print("ARCHIVO GEOGRÁFICO NO ENCONTRADO")
        print("=" * 70)
        print()
        print("Para usar este script, necesitas un archivo con la división política")
        print("de Ecuador a nivel de cantones (ADM2). Descárgalo de:")
        print()
        print("  1. GADM (recomendado):")
        print("     https://gadm.org/download_country.html")
        print("     ->Selecciona 'Ecuador' ->Level 2 ->GeoJSON")
        print("     ->Guarda como: data/geo/gadm41_ECU_2.json")
        print()
        print("  2. INEC:")
        print("     https://www.ecuadorencifras.gob.ec/documentos/web-inec/Cartografia/")
        print("     ->Busca 'cantones' ->Descarga el .shp")
        print("     ->Guarda en: data/geo/")
        print()
        print("  3. Descarga directa con wget (GADM GeoPackage):")
        print("     wget -O data/geo/gadm41_ECU.gpkg https://geodata.ucdavis.edu/gadm/gadm4.1/gpkg/gadm41_ECU.gpkg")
        print()

        # Crear directorio si no existe
        (base_path / "data" / "geo").mkdir(parents=True, exist_ok=True)
        sys.exit(1)

    print(f"Cargando: {geo_path.name}...")
    gdf = gpd.read_file(str(geo_path))
    print(f"  ->{len(gdf)} geometrías cargadas")

    # Detectar columnas
    columnas = detectar_columnas(gdf)
    if not columnas["provincia"] or not columnas["canton"]:
        print(f"Error: No se pudieron detectar las columnas de provincia/cantón.")
        print(f"Columnas disponibles: {list(gdf.columns)}")
        sys.exit(1)

    col_prov = columnas["provincia"]
    col_cant = columnas["canton"]
    print(f"  ->Columna provincia: '{col_prov}' ({gdf[col_prov].nunique()} provincias)")
    print(f"  ->Columna cantón: '{col_cant}' ({gdf[col_cant].nunique()} cantones)")

    # Listar provincias y cantones
    if args.listar:
        for prov in sorted(gdf[col_prov].unique()):
            cantones = sorted(gdf.loc[gdf[col_prov] == prov, col_cant].unique())
            print(f"\n{prov} ({len(cantones)} cantones):")
            for c in cantones:
                print(f"  - {c}")
        return

    # Generar mapa(s)
    if args.todas:
        generar_galeria(gdf, col_prov, col_cant, formato=args.formato, dpi=args.dpi)
    elif args.provincia:
        generar_mapa_provincia(
            gdf, col_prov, col_cant,
            provincia=args.provincia,
            ciudad_resaltada=args.ciudad,
            formato=args.formato,
            dpi=args.dpi,
            mostrar=not args.no_mostrar,
        )
    else:
        parser.print_help()
        print("\n  Usa --provincia NOMBRE o --todas para generar mapas.")


if __name__ == "__main__":
    main()
