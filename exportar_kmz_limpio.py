# -*- coding: utf-8 -*-
"""
Exportador de Capas / Group Layers a KMZ Limpio (sin Hipervínculos ni Descripción)
=================================================================================
Permite exportar capas vectoriales y Group Layers de ArcGIS Pro a formato KMZ
asegurando que:
- La pestaña 'Descripción' en las propiedades del KMZ (Google Earth) quede
  completamente vacía en todos los niveles (Documento, Carpetas y Placemarks).
- No existan hipervínculos HTML (<a href>), URLs, <NetworkLink>, <ExtendedData>,
  <Snippet>, <BalloonStyle> ni enlaces externos (<href>http://...).
- Se exporte como geometría vectorial pura (NO_COMPOSITE) conservando la simbología
  y los íconos locales embebidos dentro del archivo KMZ.
- Las geometrías queden ajustadas al terreno (CLAMPED_TO_GROUND) por defecto.

También puede utilizarse por consola para limpiar archivos .kmz ya existentes.
"""

import os
import sys
import re
import shutil
import zipfile
import tempfile
import argparse
import xml.etree.ElementTree as ET

try:
    import arcpy
    HAS_ARCPY = True
except ImportError:
    HAS_ARCPY = False


def log_info(msg):
    if HAS_ARCPY:
        arcpy.AddMessage(msg)
    else:
        print(f"[INFO] {msg}")


def log_warning(msg):
    if HAS_ARCPY:
        arcpy.AddWarning(msg)
    else:
        print(f"[ADVERTENCIA] {msg}")


def log_error(msg):
    if HAS_ARCPY:
        arcpy.AddError(msg)
    else:
        print(f"[ERROR] {msg}")


def sanitizar_nombre_archivo(nombre):
    """Limpia caracteres inválidos para nombres de archivo en Windows."""
    if not nombre:
        return "capa_sin_nombre"
    limpio = re.sub(r'[\\/*?:"<>|]', "_", str(nombre).strip())
    limpio = re.sub(r'\s+', "_", limpio)
    return limpio or "capa_sin_nombre"


def limpiar_contenido_kml(kml_text):
    """
    Elimina del contenido XML de un KML todos los bloques que generan descripciones,
    burbujas emergentes o hipervínculos en Google Earth:
    - <description>...</description> (Documento, Carpetas y Placemarks)
    - <Snippet>...</Snippet>
    - <BalloonStyle>...</BalloonStyle>
    - <ExtendedData>...</ExtendedData>
    - <NetworkLink>...</NetworkLink>
    - <atom:link ...>
    - <href> externos (http://, https://, ftp://, file://)

    Conserva intactas las geometrías, nombres, jerarquía de carpetas, estilos
    y las referencias locales a íconos embebidos dentro del KMZ.
    """
    stats = {
        "descriptions": 0,
        "snippets": 0,
        "balloon_styles": 0,
        "extended_data": 0,
        "network_links": 0,
        "external_hrefs": 0
    }

    # 1. Eliminar <description>...</description> y <description/>
    kml_text, n = re.subn(r'<description\b[^>]*>.*?</description>', '', kml_text, flags=re.DOTALL | re.IGNORECASE)
    stats["descriptions"] += n
    kml_text, n = re.subn(r'<description\b[^>]*/>', '', kml_text, flags=re.IGNORECASE)
    stats["descriptions"] += n

    # 2. Eliminar <Snippet>...</Snippet> y <Snippet/>
    kml_text, n = re.subn(r'<snippet\b[^>]*>.*?</snippet>', '', kml_text, flags=re.DOTALL | re.IGNORECASE)
    stats["snippets"] += n
    kml_text, n = re.subn(r'<snippet\b[^>]*/>', '', kml_text, flags=re.IGNORECASE)
    stats["snippets"] += n

    # 3. Eliminar <BalloonStyle>...</BalloonStyle>
    kml_text, n = re.subn(r'<BalloonStyle\b[^>]*>.*?</BalloonStyle>', '', kml_text, flags=re.DOTALL | re.IGNORECASE)
    stats["balloon_styles"] += n

    # 4. Eliminar <ExtendedData>...</ExtendedData>
    kml_text, n = re.subn(r'<ExtendedData\b[^>]*>.*?</ExtendedData>', '', kml_text, flags=re.DOTALL | re.IGNORECASE)
    stats["extended_data"] += n

    # 5. Eliminar <NetworkLink>...</NetworkLink>
    kml_text, n = re.subn(r'<NetworkLink\b[^>]*>.*?</NetworkLink>', '', kml_text, flags=re.DOTALL | re.IGNORECASE)
    stats["network_links"] += n

    # 6. Eliminar etiquetas <atom:link ...>
    kml_text = re.sub(r'<atom:link\b[^>]*>.*?</atom:link>', '', kml_text, flags=re.DOTALL | re.IGNORECASE)
    kml_text = re.sub(r'<atom:link\b[^>]*/>', '', kml_text, flags=re.IGNORECASE)

    # 7. Eliminar <href> que apunten a enlaces externos (manteniendo íconos locales dentro del KMZ)
    kml_text, n = re.subn(
        r'<href\b[^>]*>\s*(?:https?|ftp|file)://.*?</href>',
        '',
        kml_text,
        flags=re.DOTALL | re.IGNORECASE
    )
    stats["external_hrefs"] += n

    # Limpiar contenedores <Icon> que hayan quedado vacíos tras quitar un href externo
    kml_text = re.sub(r'<Icon\b[^>]*>\s*</Icon>', '', kml_text, flags=re.IGNORECASE)

    # Compactar líneas vacías consecutivas
    kml_text = re.sub(r'\n[ \t]*\n+', '\n', kml_text)

    return kml_text, stats


def limpiar_archivo_kmz(kmz_origen, kmz_destino):
    """
    Descomprime un archivo KMZ, limpia todos los archivos .kml internos para dejar
    la pestaña Descripción vacía y sin hipervínculos, valida el XML resultante
    y vuelve a empaquetar el archivo KMZ destino.
    """
    temp_dir = tempfile.mkdtemp(prefix="kmz_clean_")
    stats_totales = {
        "descriptions": 0,
        "snippets": 0,
        "balloon_styles": 0,
        "extended_data": 0,
        "network_links": 0,
        "external_hrefs": 0
    }

    try:
        with zipfile.ZipFile(kmz_origen, 'r') as zin:
            zin.extractall(temp_dir)

        kml_encontrados = 0
        for root, _, files in os.walk(temp_dir):
            for filename in files:
                if filename.lower().endswith(".kml"):
                    kml_encontrados += 1
                    kml_path = os.path.join(root, filename)

                    # Leer tolerando UTF-8 con o sin BOM y fallback latin-1
                    try:
                        with open(kml_path, 'r', encoding='utf-8-sig') as f:
                            contenido = f.read()
                    except UnicodeDecodeError:
                        with open(kml_path, 'r', encoding='latin-1') as f:
                            contenido = f.read()

                    contenido_limpio, st = limpiar_contenido_kml(contenido)

                    # Validar que el XML resultante esté bien formado
                    try:
                        ET.fromstring(contenido_limpio.encode('utf-8'))
                    except ET.ParseError as pe:
                        raise ValueError(f"El XML del archivo '{filename}' quedó mal formado tras la limpieza: {pe}")

                    with open(kml_path, 'w', encoding='utf-8') as f:
                        f.write(contenido_limpio)

                    for k in stats_totales:
                        stats_totales[k] += st[k]

        if kml_encontrados == 0:
            raise FileNotFoundError(f"No se encontró ningún archivo .kml dentro de '{kmz_origen}'.")

        os.makedirs(os.path.dirname(os.path.abspath(kmz_destino)), exist_ok=True)

        # Re-empaquetar en KMZ (ZIP con compresión DEFLATE)
        with zipfile.ZipFile(kmz_destino, 'w', zipfile.ZIP_DEFLATED) as zout:
            for root, _, files in os.walk(temp_dir):
                for filename in files:
                    full_path = os.path.join(root, filename)
                    rel_path = os.path.relpath(full_path, temp_dir)
                    zout.write(full_path, rel_path)

        return stats_totales

    finally:
        shutil.rmtree(temp_dir, ignore_errors=True)


def _resolver_capa_en_mapa(item, mapa_activo):
    """
    Intenta resolver una entrada (objeto Layer o texto) a un objeto arcpy.mp.Layer
    del mapa activo si existe.
    """
    if not isinstance(item, str):
        return item

    texto = item.strip().strip("'\"")
    if mapa_activo is not None:
        capas = mapa_activo.listLayers()
        for lyr in capas:
            if lyr.longName == texto:
                return lyr
        for lyr in capas:
            if lyr.name == texto:
                return lyr
    return texto


def _obtener_nombre_capa(item):
    """Obtiene un nombre legible para el archivo KMZ a partir de una capa o ruta."""
    if hasattr(item, "name"):
        return item.name
    texto = str(item).strip().strip("'\"")
    base = os.path.basename(texto)
    nombre, _ = os.path.splitext(base)
    return nombre or texto


def exportar_capas_a_kmz_limpio(
    capas_entrada,
    carpeta_salida,
    desglosar_grupos=False,
    solo_capas_visibles=True,
    clamped_to_ground=True,
    sobrescribir=True
):
    """
    Exporta una lista de capas / Group Layers / Feature Classes a archivos KMZ limpios
    en la carpeta de destino.
    """
    if not HAS_ARCPY:
        log_error("Se requiere 'arcpy' (ArcGIS Pro) para exportar capas vectoriales a KMZ.")
        return False

    if not os.path.isdir(carpeta_salida):
        try:
            os.makedirs(carpeta_salida, exist_ok=True)
        except Exception as e:
            log_error(f"No se pudo crear la carpeta de salida '{carpeta_salida}': {e}")
            return False

    # Intentar obtener el mapa activo para resolver Group Layers
    mapa_activo = None
    try:
        aprx = arcpy.mp.ArcGISProject("CURRENT")
        mapa_activo = aprx.activeMap
    except Exception:
        mapa_activo = None

    log_info("=" * 65)
    log_info("EXPORTACIÓN DE CAPAS A KMZ LIMPIO (SIN HIPERVÍNCULOS)")
    log_info(f"Carpeta destino:        {carpeta_salida}")
    log_info(f"Desglosar Group Layers: {'Sí (KMZ individuales)' if desglosar_grupos else 'No (KMZ agrupado)'}")
    log_info(f"Ajustar al terreno:     {'CLAMPED_TO_GROUND' if clamped_to_ground else 'ABSOLUTE'}")
    log_info(f"Sobrescribir:           {'Sí' if sobrescribir else 'No'}")
    log_info("Limpieza aplicada:      Pestaña Descripción vacía + sin hipervínculos")
    log_info("=" * 65)

    # Preparar lista final de tareas (objeto_a_exportar, nombre_deseado, es_temp_layer)
    tareas_exportacion = []
    for raw_item in capas_entrada:
        resuelto = _resolver_capa_en_mapa(raw_item, mapa_activo)

        if hasattr(resuelto, "isGroupLayer") and resuelto.isGroupLayer:
            if desglosar_grupos:
                subcapas = [
                    sub for sub in resuelto.listLayers()
                    if not sub.isGroupLayer and (not solo_capas_visibles or sub.visible)
                ]
                if not subcapas:
                    log_warning(f"El Group Layer '{resuelto.name}' no contiene subcapas exportables/visibles.")
                for sub in subcapas:
                    tareas_exportacion.append((sub, sub.name))
            else:
                tareas_exportacion.append((resuelto, resuelto.name))
        else:
            tareas_exportacion.append((resuelto, _obtener_nombre_capa(resuelto)))

    if not tareas_exportacion:
        log_warning("No se encontraron capas válidas para exportar.")
        return False

    log_info(f"Total de archivos KMZ a generar: {len(tareas_exportacion)}\n")

    nombres_usados = {}
    exitosos = 0
    omitidos = 0
    errores = 0
    temp_work_dir = tempfile.mkdtemp(prefix="arcpy_kmz_exp_")

    try:
        for idx, (capa_obj, nombre_base) in enumerate(tareas_exportacion, 1):
            nombre_limpio = sanitizar_nombre_archivo(nombre_base)

            # Evitar colisiones si hay dos subcapas con el mismo nombre en la misma ejecución
            clave_lower = nombre_limpio.lower()
            if clave_lower in nombres_usados:
                nombres_usados[clave_lower] += 1
                nombre_final = f"{nombre_limpio}_{nombres_usados[clave_lower]}"
            else:
                nombres_usados[clave_lower] = 1
                nombre_final = nombre_limpio

            kmz_final = os.path.join(carpeta_salida, f"{nombre_final}.kmz")
            kmz_temporal = os.path.join(temp_work_dir, f"raw_{idx}_{nombre_final}.kmz")

            if os.path.exists(kmz_final):
                if sobrescribir:
                    try:
                        os.remove(kmz_final)
                    except Exception as e:
                        log_error(f"[{idx}/{len(tareas_exportacion)}] No se pudo sobrescribir '{kmz_final}': {e}")
                        errores += 1
                        continue
                else:
                    log_warning(f"[{idx}/{len(tareas_exportacion)}] OMITIDO: '{nombre_final}.kmz' ya existe.")
                    omitidos += 1
                    continue

            temp_lyr_name = None
            capa_para_kml = capa_obj

            try:
                # Si es una ruta a Feature Class / Shapefile en disco, envolverla en Feature Layer temporal
                if isinstance(capa_obj, str):
                    ruta_limpia = capa_obj.strip().strip("'\"")
                    if not ruta_limpia.lower().endswith(".lyrx") and arcpy.Exists(ruta_limpia):
                        desc = arcpy.Describe(ruta_limpia)
                        if getattr(desc, "dataType", "") in ("FeatureClass", "ShapeFile"):
                            temp_lyr_name = f"tmp_kmz_lyr_{idx}"
                            if arcpy.Exists(temp_lyr_name):
                                arcpy.management.Delete(temp_lyr_name)
                            arcpy.management.MakeFeatureLayer(ruta_limpia, temp_lyr_name)
                            capa_para_kml = temp_lyr_name

                # Exportar usando LayerToKML con NO_COMPOSITE (vectorial puro)
                z_val = "CLAMPED_TO_GROUND" if clamped_to_ground else "ABSOLUTE"
                try:
                    arcpy.conversion.LayerToKML(
                        capa_para_kml,
                        kmz_temporal,
                        0,
                        "NO_COMPOSITE",
                        "DEFAULT",
                        1024,
                        96,
                        z_val
                    )
                except Exception:
                    # Fallback de compatibilidad entre versiones de ArcGIS Pro
                    arcpy.conversion.LayerToKML(
                        capa_para_kml,
                        kmz_temporal,
                        0,
                        "NO_COMPOSITE",
                        "",
                        1024,
                        96,
                        bool(clamped_to_ground)
                    )

                # Limpiar el KMZ temporal y guardar el KMZ limpio definitivo
                stats = limpiar_archivo_kmz(kmz_temporal, kmz_final)

                log_info(
                    f"[{idx}/{len(tareas_exportacion)}] EXPORTADO LIMPIO: '{nombre_final}.kmz' "
                    f"(descripciones eliminadas: {stats['descriptions']}, "
                    f"enlaces externos eliminados: {stats['external_hrefs'] + stats['network_links']})"
                )
                exitosos += 1

            except Exception as e:
                log_error(f"[{idx}/{len(tareas_exportacion)}] ERROR al exportar '{nombre_base}': {e}")
                errores += 1
            finally:
                if temp_lyr_name and arcpy.Exists(temp_lyr_name):
                    try:
                        arcpy.management.Delete(temp_lyr_name)
                    except Exception:
                        pass
                if os.path.exists(kmz_temporal):
                    try:
                        os.remove(kmz_temporal)
                    except Exception:
                        pass
    finally:
        shutil.rmtree(temp_work_dir, ignore_errors=True)

    log_info("\n" + "=" * 65)
    log_info("RESUMEN DE EXPORTACIÓN KMZ LIMPIO")
    log_info(f" - Archivos KMZ generados con éxito: {exitosos}")
    log_info(f" - Archivos omitidos:                {omitidos}")
    log_info(f" - Errores:                          {errores}")
    log_info("=" * 65)

    return errores == 0


def main():
    """Punto de entrada por consola para limpiar archivos KMZ existentes sin ArcGIS Pro."""
    parser = argparse.ArgumentParser(
        description="Limpia archivos KMZ existentes eliminando descripciones e hipervínculos."
    )
    parser.add_argument("-i", "--entrada", help="Ruta de un archivo .kmz o carpeta con archivos .kmz")
    parser.add_argument("-o", "--salida", help="Ruta del archivo .kmz o carpeta de salida (opcional)", default=None)

    args = parser.parse_args()
    entrada = args.entrada
    if not entrada:
        entrada = input("Ingrese la ruta del archivo .kmz o carpeta con archivos .kmz a limpiar: ").strip().strip("'\"")

    if os.path.isfile(entrada) and entrada.lower().endswith(".kmz"):
        destino = args.salida or entrada
        stats = limpiar_archivo_kmz(entrada, destino)
        print(f"[INFO] KMZ limpiado con éxito: {destino} -> {stats}")
    elif os.path.isdir(entrada):
        carpeta_out = args.salida or entrada
        os.makedirs(carpeta_out, exist_ok=True)
        for f in os.listdir(entrada):
            if f.lower().endswith(".kmz"):
                src = os.path.join(entrada, f)
                dst = os.path.join(carpeta_out, f)
                stats = limpiar_archivo_kmz(src, dst)
                print(f"[INFO] Limpiado '{f}': {stats}")
    else:
        print(f"[ERROR] Ruta inválida o sin archivos .kmz: {entrada}")


if __name__ == "__main__":
    main()
