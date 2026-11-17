# -*- coding: utf-8 -*-
"""
Exportador de Capas / Group Layers a KMZ Limpio (sin Hipervínculos, con Tabla de Atributos)
===========================================================================================
Permite exportar capas vectoriales y Group Layers de ArcGIS Pro a formato KMZ
asegurando que:
- La pestaña 'Descripción' en las propiedades del KMZ (Google Earth) quede
  completamente vacía en todos los niveles (Documento, Carpetas y Placemarks).
- Se CONSERVE la tabla de atributos completa migrando los atributos desde el HTML
  de ArcGIS hacia el estándar KML 2.2 (<Schema> + <ExtendedData><SchemaData><SimpleData>),
  lo que permite ver los atributos al hacer clic en Google Earth y mantener las columnas
  reales al abrir el KMZ en QGIS/ArcGIS, sin ensuciar la pestaña Descripción.
- No existan hipervínculos HTML (<a href>), URLs (http/https/www/file), <NetworkLink>,
  <Snippet>, <BalloonStyle> ni enlaces externos (<href>http://...).
- Se exporte como geometría vectorial pura (NO_COMPOSITE) conservando la simbología
  y los íconos locales embebidos dentro del archivo KMZ.
- Las geometrías queden ajustadas al terreno (CLAMPED_TO_GROUND) por defecto.

También puede utilizarse por consola para limpiar archivos .kmz ya existentes.
"""

import os
import sys
import re
import html
import shutil
import zipfile
import tempfile
import argparse
import xml.etree.ElementTree as ET
from html.parser import HTMLParser
from xml.sax.saxutils import escape as xml_escape

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


class _ArcGISTableHTMLParser(HTMLParser):
    """
    Extrae pares (campo, valor) desde las tablas HTML generadas por ArcGIS Pro
    dentro de <description>, manejando tablas anidadas y eliminando etiquetas
    HTML como <a href="..."> mientras conserva el texto limpio.
    """
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.rows = []
        self._tr_stack = []

    def handle_starttag(self, tag, attrs):
        t = tag.lower()
        if t == "tr":
            self._tr_stack.append({"cells": [], "in_cell": False, "has_nested_table": False})
        elif t == "table":
            if self._tr_stack:
                self._tr_stack[-1]["has_nested_table"] = True
        elif t in ("td", "th"):
            if self._tr_stack and not self._tr_stack[-1]["has_nested_table"]:
                self._tr_stack[-1]["in_cell"] = True
                self._tr_stack[-1]["cells"].append([])
        elif t == "br":
            if self._tr_stack and self._tr_stack[-1]["in_cell"]:
                self._tr_stack[-1]["cells"][-1].append(" ")

    def handle_endtag(self, tag):
        t = tag.lower()
        if t in ("td", "th"):
            if self._tr_stack and self._tr_stack[-1]["in_cell"]:
                self._tr_stack[-1]["in_cell"] = False
        elif t == "tr":
            if self._tr_stack:
                row = self._tr_stack.pop()
                if not row["has_nested_table"] and len(row["cells"]) == 2:
                    key = "".join(row["cells"][0]).strip()
                    val = "".join(row["cells"][1]).strip()
                    if key:
                        self.rows.append((key, val))

    def handle_data(self, data):
        if self._tr_stack and self._tr_stack[-1]["in_cell"] and not self._tr_stack[-1]["has_nested_table"]:
            self._tr_stack[-1]["cells"][-1].append(data)


def _limpiar_valor_atributo(valor):
    """Limpia espacios, valores <Null> y elimina URLs para evitar auto-hipervínculos en Google Earth."""
    if valor is None:
        return ""
    texto = re.sub(r'\s+', ' ', str(valor)).strip()
    if texto.lower() == "<null>":
        return ""
    # Eliminar URLs que Google Earth convertiría automáticamente en hipervínculos
    texto = re.sub(r'(?:https?|ftp|file)://\S+', '', texto, flags=re.IGNORECASE)
    texto = re.sub(r'\bwww\.\S+', '', texto, flags=re.IGNORECASE)
    texto = re.sub(r'\s+', ' ', texto).strip()
    return texto


def _extraer_atributos_desde_descripcion(desc_inner):
    """Extrae lista de (campo, valor) desde el contenido de una etiqueta <description>."""
    if not desc_inner:
        return []

    contenido = desc_inner.strip()
    cdata_match = re.match(r'^<!\[CDATA\[(.*)\]\]>$', contenido, flags=re.DOTALL)
    if cdata_match:
        html_str = cdata_match.group(1)
    else:
        html_str = html.unescape(contenido)

    parser = _ArcGISTableHTMLParser()
    try:
        parser.feed(html_str)
        parser.close()
    except Exception:
        return []

    pares_limpios = []
    for k, v in parser.rows:
        campo = re.sub(r'\s+', ' ', k).strip()
        if not campo:
            continue
        valor = _limpiar_valor_atributo(v)
        pares_limpios.append((campo, valor))
    return pares_limpios


def _extraer_atributos_desde_extended_data(ext_xml):
    """Extrae pares (campo, valor) si el Placemark ya traía ExtendedData previo."""
    pares = []
    # Buscar <SimpleData name="...">...</SimpleData>
    for m in re.finditer(r'<SimpleData\s+[^>]*name=["\']([^"\']+)["\'][^>]*>(.*?)</SimpleData>', ext_xml, flags=re.DOTALL | re.IGNORECASE):
        campo = html.unescape(m.group(1)).strip()
        valor = _limpiar_valor_atributo(html.unescape(m.group(2)))
        if campo:
            pares.append((campo, valor))

    if pares:
        return pares

    # Buscar <Data name="..."><value>...</value></Data>
    for m in re.finditer(
        r'<Data\s+[^>]*name=["\']([^"\']+)["\'][^>]*>.*?<value[^>]*>(.*?)</value>.*?</Data>',
        ext_xml,
        flags=re.DOTALL | re.IGNORECASE
    ):
        campo = html.unescape(m.group(1)).strip()
        valor = _limpiar_valor_atributo(html.unescape(m.group(2)))
        if campo:
            pares.append((campo, valor))

    return pares


def limpiar_contenido_kml(kml_text, conservar_atributos=True):
    """
    Limpia el contenido XML de un archivo KML:
    - Si conservar_atributos=True: extrae la tabla de atributos del HTML de <description>
      de cada Placemark y la migra al estándar KML 2.2 (<Schema> + <ExtendedData><SchemaData>),
      limpiando cualquier etiqueta <a href> o URL.
    - Elimina TODAS las etiquetas <description> (Documento, Carpetas y Placemarks) para que
      la hoja 'Descripción' en las propiedades de Google Earth quede 100% vacía.
    - Elimina <Snippet>, <BalloonStyle>, <NetworkLink>, <atom:link> y <href> externos.
    - Conserva geometrías, nombres, carpetas, estilos e íconos locales embebidos.
    """
    stats = {
        "descriptions": 0,
        "atributos_migrados": 0,
        "placemarks_con_atributos": 0,
        "snippets": 0,
        "balloon_styles": 0,
        "network_links": 0,
        "external_hrefs": 0
    }

    tiene_document = bool(re.search(r'<Document\b[^>]*>', kml_text, flags=re.IGNORECASE))
    schemas_por_campos = {}  # tuple(field_names) -> schema_id
    schemas_orden = []       # list of (schema_id, tuple(field_names))

    def _procesar_placemark(match):
        pm_xml = match.group(0)
        atributos = []

        # 1. Extraer atributos desde <description> antes de borrarlo
        if conservar_atributos:
            desc_match = re.search(r'<description\b[^>]*>(.*?)</description>', pm_xml, flags=re.DOTALL | re.IGNORECASE)
            if desc_match:
                atributos = _extraer_atributos_desde_descripcion(desc_match.group(1))

            # Si no había tabla en <description>, verificar si ya existía <ExtendedData>
            if not atributos:
                ext_match = re.search(r'<ExtendedData\b[^>]*>(.*?)</ExtendedData>', pm_xml, flags=re.DOTALL | re.IGNORECASE)
                if ext_match:
                    atributos = _extraer_atributos_desde_extended_data(ext_match.group(1))

        # 2. Eliminar <description>, <Snippet> y <ExtendedData> anterior del Placemark
        pm_xml, n = re.subn(r'<description\b[^>]*>.*?</description>', '', pm_xml, flags=re.DOTALL | re.IGNORECASE)
        stats["descriptions"] += n
        pm_xml, n = re.subn(r'<description\b[^>]*/>', '', pm_xml, flags=re.IGNORECASE)
        stats["descriptions"] += n

        pm_xml, n = re.subn(r'<snippet\b[^>]*>.*?</snippet>', '', pm_xml, flags=re.DOTALL | re.IGNORECASE)
        stats["snippets"] += n
        pm_xml, n = re.subn(r'<snippet\b[^>]*/>', '', pm_xml, flags=re.IGNORECASE)
        stats["snippets"] += n

        pm_xml = re.sub(r'<ExtendedData\b[^>]*>.*?</ExtendedData>', '', pm_xml, flags=re.DOTALL | re.IGNORECASE)

        # 3. Insertar <ExtendedData> limpio si se extrajeron atributos
        if conservar_atributos and atributos:
            stats["placemarks_con_atributos"] += 1
            stats["atributos_migrados"] += len(atributos)

            if tiene_document:
                campos_tuple = tuple(dict.fromkeys(k for k, _ in atributos))
                if campos_tuple not in schemas_por_campos:
                    schema_id = f"Schema_Atributos_{len(schemas_orden) + 1}"
                    schemas_por_campos[campos_tuple] = schema_id
                    schemas_orden.append((schema_id, campos_tuple))
                else:
                    schema_id = schemas_por_campos[campos_tuple]

                lines = [f'      <ExtendedData>', f'        <SchemaData schemaUrl="#{schema_id}">']
                for campo, valor in atributos:
                    c_esc = xml_escape(campo, {'"': '&quot;', "'": '&apos;'})
                    v_esc = xml_escape(valor)
                    lines.append(f'          <SimpleData name="{c_esc}">{v_esc}</SimpleData>')
                lines.append('        </SchemaData>')
                lines.append('      </ExtendedData>')
                ext_block = "\n" + "\n".join(lines) + "\n"
            else:
                lines = ['      <ExtendedData>']
                for campo, valor in atributos:
                    c_esc = xml_escape(campo, {'"': '&quot;', "'": '&apos;'})
                    v_esc = xml_escape(valor)
                    lines.append(f'        <Data name="{c_esc}"><value>{v_esc}</value></Data>')
                lines.append('      </ExtendedData>')
                ext_block = "\n" + "\n".join(lines) + "\n"

            # Insertar <ExtendedData> antes de la geometría (orden oficial OGC KML 2.2)
            geom_match = re.search(r'<(?:MultiGeometry|Polygon|LineString|Point|Model|gx:Track)\b', pm_xml, flags=re.IGNORECASE)
            if geom_match:
                pos = geom_match.start()
                pm_xml = pm_xml[:pos] + ext_block.lstrip("\n") + "      " + pm_xml[pos:]
            else:
                pm_xml = re.sub(r'</Placemark>\s*$', ext_block + '    </Placemark>', pm_xml, flags=re.IGNORECASE)

        return pm_xml

    # Procesar cada <Placemark> individualmente
    kml_text = re.sub(
        r'<Placemark\b[^>]*>.*?</Placemark>',
        _procesar_placemark,
        kml_text,
        flags=re.DOTALL | re.IGNORECASE
    )

    # Insertar las definiciones <Schema> en <Document> antes del primer <Folder>/<Placemark> (orden OGC KML 2.2)
    if conservar_atributos and tiene_document and schemas_orden:
        schema_blocks = []
        for schema_id, campos_tuple in schemas_orden:
            s_lines = [f'  <Schema name="{schema_id}" id="{schema_id}">']
            for campo in campos_tuple:
                c_esc = xml_escape(campo, {'"': '&quot;', "'": '&apos;'})
                s_lines.append(f'    <SimpleField type="string" name="{c_esc}"/>')
            s_lines.append('  </Schema>')
            schema_blocks.append("\n".join(s_lines))

        all_schemas_xml = "\n" + "\n".join(schema_blocks) + "\n"
        first_container = re.search(r'(<(?:Folder|Placemark)\b[^>]*>)', kml_text, flags=re.IGNORECASE)
        if first_container:
            pos = first_container.start()
            kml_text = kml_text[:pos] + all_schemas_xml.lstrip("\n") + "  " + kml_text[pos:]
        else:
            kml_text = re.sub(
                r'(<Document\b[^>]*>)',
                lambda m: m.group(1) + all_schemas_xml,
                kml_text,
                count=1,
                flags=re.IGNORECASE
            )

    # Limpiar cualquier <description> restante en Document / Folder / GroundOverlay
    kml_text, n = re.subn(r'<description\b[^>]*>.*?</description>', '', kml_text, flags=re.DOTALL | re.IGNORECASE)
    stats["descriptions"] += n
    kml_text, n = re.subn(r'<description\b[^>]*/>', '', kml_text, flags=re.IGNORECASE)
    stats["descriptions"] += n

    # Limpiar cualquier <Snippet> restante
    kml_text, n = re.subn(r'<snippet\b[^>]*>.*?</snippet>', '', kml_text, flags=re.DOTALL | re.IGNORECASE)
    stats["snippets"] += n
    kml_text, n = re.subn(r'<snippet\b[^>]*/>', '', kml_text, flags=re.IGNORECASE)
    stats["snippets"] += n

    # Eliminar <BalloonStyle> (evita que $[description] vacío oculte la tabla de ExtendedData)
    kml_text, n = re.subn(r'<BalloonStyle\b[^>]*>.*?</BalloonStyle>', '', kml_text, flags=re.DOTALL | re.IGNORECASE)
    stats["balloon_styles"] += n

    # Eliminar <NetworkLink>
    kml_text, n = re.subn(r'<NetworkLink\b[^>]*>.*?</NetworkLink>', '', kml_text, flags=re.DOTALL | re.IGNORECASE)
    stats["network_links"] += n

    # Eliminar <atom:link>
    kml_text = re.sub(r'<atom:link\b[^>]*>.*?</atom:link>', '', kml_text, flags=re.DOTALL | re.IGNORECASE)
    kml_text = re.sub(r'<atom:link\b[^>]*/>', '', kml_text, flags=re.IGNORECASE)

    # Eliminar <href> externos (manteniendo íconos locales embebidos en el KMZ)
    kml_text, n = re.subn(
        r'<href\b[^>]*>\s*(?:https?|ftp|file)://.*?</href>',
        '',
        kml_text,
        flags=re.DOTALL | re.IGNORECASE
    )
    stats["external_hrefs"] += n
    kml_text = re.sub(r'<Icon\b[^>]*>\s*</Icon>', '', kml_text, flags=re.IGNORECASE)

    # Compactar líneas vacías consecutivas
    kml_text = re.sub(r'\n[ \t]*\n+', '\n', kml_text)

    return kml_text, stats


def limpiar_archivo_kmz(kmz_origen, kmz_destino, conservar_atributos=True):
    """
    Descomprime un archivo KMZ, migra las tablas de atributos a ExtendedData/SchemaData,
    deja vacía la pestaña Descripción y elimina hipervínculos, valida el XML resultante
    y vuelve a empaquetar el archivo KMZ destino.
    """
    temp_dir = tempfile.mkdtemp(prefix="kmz_clean_")
    stats_totales = {
        "descriptions": 0,
        "atributos_migrados": 0,
        "placemarks_con_atributos": 0,
        "snippets": 0,
        "balloon_styles": 0,
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

                    try:
                        with open(kml_path, 'r', encoding='utf-8-sig') as f:
                            contenido = f.read()
                    except UnicodeDecodeError:
                        with open(kml_path, 'r', encoding='latin-1') as f:
                            contenido = f.read()

                    contenido_limpio, st = limpiar_contenido_kml(
                        contenido,
                        conservar_atributos=conservar_atributos
                    )

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
    sobrescribir=True,
    conservar_atributos=True
):
    """
    Exporta una lista de capas / Group Layers / Feature Classes a archivos KMZ limpios
    en la carpeta de destino, conservando la tabla de atributos en ExtendedData y dejando
    la pestaña Descripción completamente vacía.
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
    log_info(f"Tabla de atributos:     {'Conservar en ExtendedData (sin HTML en Descripción)' if conservar_atributos else 'Eliminar completamente'}")
    log_info(f"Sobrescribir:           {'Sí' if sobrescribir else 'No'}")
    log_info("=" * 65)

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

                stats = limpiar_archivo_kmz(
                    kmz_temporal,
                    kmz_final,
                    conservar_atributos=conservar_atributos
                )

                log_info(
                    f"[{idx}/{len(tareas_exportacion)}] EXPORTADO LIMPIO: '{nombre_final}.kmz' "
                    f"(entidades con atributos migrados: {stats['placemarks_con_atributos']}, "
                    f"descripciones vaciadas: {stats['descriptions']}, "
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
        description="Limpia archivos KMZ existentes vaciando Descripción y migrando atributos a ExtendedData."
    )
    parser.add_argument("-i", "--entrada", help="Ruta de un archivo .kmz o carpeta con archivos .kmz")
    parser.add_argument("-o", "--salida", help="Ruta del archivo .kmz o carpeta de salida (opcional)", default=None)
    parser.add_argument("--sin-atributos", help="Eliminar también la tabla de atributos", action="store_true")

    args = parser.parse_args()
    entrada = args.entrada
    if not entrada:
        entrada = input("Ingrese la ruta del archivo .kmz o carpeta con archivos .kmz a limpiar: ").strip().strip("'\"")

    conservar = not args.sin_atributos

    if os.path.isfile(entrada) and entrada.lower().endswith(".kmz"):
        destino = args.salida or entrada
        stats = limpiar_archivo_kmz(entrada, destino, conservar_atributos=conservar)
        print(f"[INFO] KMZ limpiado con éxito: {destino} -> {stats}")
    elif os.path.isdir(entrada):
        carpeta_out = args.salida or entrada
        os.makedirs(carpeta_out, exist_ok=True)
        for f in os.listdir(entrada):
            if f.lower().endswith(".kmz"):
                src = os.path.join(entrada, f)
                dst = os.path.join(carpeta_out, f)
                stats = limpiar_archivo_kmz(src, dst, conservar_atributos=conservar)
                print(f"[INFO] Limpiado '{f}': {stats}")
    else:
        print(f"[ERROR] Ruta inválida o sin archivos .kmz: {entrada}")


if __name__ == "__main__":
    main()
