# -*- coding: utf-8 -*-
"""
Toolbox de ArcGIS Pro: Exportar Capas a KMZ Limpio (Sin Hipervínculos, con Atributos)
====================================================================================
Herramienta nativa (.pyt) para exportar capas vectoriales y Group Layers a KMZ
garantizando que:
- La pestaña 'Descripción' en las propiedades del KMZ (Google Earth) quede
  completamente vacía en todos los niveles (Documento, Carpetas y Placemarks).
- Se CONSERVE la tabla de atributos completa migrando los campos desde el HTML
  de ArcGIS hacia el estándar KML 2.2 (<Schema> + <ExtendedData><SchemaData><SimpleData>),
  permitiendo ver los atributos limpios al hacer clic en Google Earth y mantener las
  columnas reales al abrir el KMZ en QGIS/ArcGIS.
- Se eliminen todos los hipervínculos HTML (<a href>), URLs (http/https/www/file),
  <Snippet>, <BalloonStyle>, <NetworkLink>, <atom:link> y <href> externos.
- Se exporte geometría vectorial pura (NO_COMPOSITE) conservando simbología
  e íconos locales embebidos dentro del KMZ.
- Se ajusten las geometrías al terreno (CLAMPED_TO_GROUND) por defecto.
"""

import os
import re
import html
import shutil
import zipfile
import tempfile
import xml.etree.ElementTree as ET
from html.parser import HTMLParser
from xml.sax.saxutils import escape as xml_escape
import arcpy


def _sanitizar_nombre_archivo(nombre):
    """Limpia caracteres inválidos para nombres de archivo en Windows."""
    if not nombre:
        return "capa_sin_nombre"
    limpio = re.sub(r'[\\/*?:"<>|]', "_", str(nombre).strip())
    limpio = re.sub(r'\s+', "_", limpio)
    return limpio or "capa_sin_nombre"


class _ArcGISTableHTMLParser(HTMLParser):
    """
    Extrae pares (campo, valor) desde las tablas HTML generadas por ArcGIS Pro
    dentro de <description>, soportando tablas anidadas y eliminando etiquetas
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
    texto = re.sub(r'(?:https?|ftp|file)://\S+', '', texto, flags=re.IGNORECASE)
    texto = re.sub(r'\bwww\.\S+', '', texto, flags=re.IGNORECASE)
    texto = re.sub(r'\s+', ' ', texto).strip()
    return texto


def _extraer_atributos_desde_descripcion(desc_inner):
    """Extrae pares (campo, valor) desde el contenido de una etiqueta <description>."""
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
    for m in re.finditer(r'<SimpleData\s+[^>]*name=["\']([^"\']+)["\'][^>]*>(.*?)</SimpleData>', ext_xml, flags=re.DOTALL | re.IGNORECASE):
        campo = html.unescape(m.group(1)).strip()
        valor = _limpiar_valor_atributo(html.unescape(m.group(2)))
        if campo:
            pares.append((campo, valor))

    if pares:
        return pares

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


def _limpiar_contenido_kml(kml_text, conservar_atributos=True):
    """
    Migra la tabla de atributos desde <description> hacia <Schema>/<ExtendedData>
    dejando la pestaña Descripción completamente vacía y libre de hipervínculos.
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
    schemas_por_campos = {}
    schemas_orden = []

    def _procesar_placemark(match):
        pm_xml = match.group(0)
        atributos = []

        if conservar_atributos:
            desc_match = re.search(r'<description\b[^>]*>(.*?)</description>', pm_xml, flags=re.DOTALL | re.IGNORECASE)
            if desc_match:
                atributos = _extraer_atributos_desde_descripcion(desc_match.group(1))

            if not atributos:
                ext_match = re.search(r'<ExtendedData\b[^>]*>(.*?)</ExtendedData>', pm_xml, flags=re.DOTALL | re.IGNORECASE)
                if ext_match:
                    atributos = _extraer_atributos_desde_extended_data(ext_match.group(1))

        # Eliminar <description>, <Snippet> y <ExtendedData> previos
        pm_xml, n = re.subn(r'<description\b[^>]*>.*?</description>', '', pm_xml, flags=re.DOTALL | re.IGNORECASE)
        stats["descriptions"] += n
        pm_xml, n = re.subn(r'<description\b[^>]*/>', '', pm_xml, flags=re.IGNORECASE)
        stats["descriptions"] += n

        pm_xml, n = re.subn(r'<snippet\b[^>]*>.*?</snippet>', '', pm_xml, flags=re.DOTALL | re.IGNORECASE)
        stats["snippets"] += n
        pm_xml, n = re.subn(r'<snippet\b[^>]*/>', '', pm_xml, flags=re.IGNORECASE)
        stats["snippets"] += n

        pm_xml = re.sub(r'<ExtendedData\b[^>]*>.*?</ExtendedData>', '', pm_xml, flags=re.DOTALL | re.IGNORECASE)

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

                lines = ['      <ExtendedData>', f'        <SchemaData schemaUrl="#{schema_id}">']
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

    kml_text = re.sub(
        r'<Placemark\b[^>]*>.*?</Placemark>',
        _procesar_placemark,
        kml_text,
        flags=re.DOTALL | re.IGNORECASE
    )

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

    # Limpiar <description> y <Snippet> restantes (Document / Folder)
    kml_text, n = re.subn(r'<description\b[^>]*>.*?</description>', '', kml_text, flags=re.DOTALL | re.IGNORECASE)
    stats["descriptions"] += n
    kml_text, n = re.subn(r'<description\b[^>]*/>', '', kml_text, flags=re.IGNORECASE)
    stats["descriptions"] += n

    kml_text, n = re.subn(r'<snippet\b[^>]*>.*?</snippet>', '', kml_text, flags=re.DOTALL | re.IGNORECASE)
    stats["snippets"] += n
    kml_text, n = re.subn(r'<snippet\b[^>]*/>', '', kml_text, flags=re.IGNORECASE)
    stats["snippets"] += n

    # Eliminar <BalloonStyle> para que Google Earth muestre la tabla nativa de ExtendedData
    kml_text, n = re.subn(r'<BalloonStyle\b[^>]*>.*?</BalloonStyle>', '', kml_text, flags=re.DOTALL | re.IGNORECASE)
    stats["balloon_styles"] += n

    # Eliminar <NetworkLink> y <atom:link>
    kml_text, n = re.subn(r'<NetworkLink\b[^>]*>.*?</NetworkLink>', '', kml_text, flags=re.DOTALL | re.IGNORECASE)
    stats["network_links"] += n

    kml_text = re.sub(r'<atom:link\b[^>]*>.*?</atom:link>', '', kml_text, flags=re.DOTALL | re.IGNORECASE)
    kml_text = re.sub(r'<atom:link\b[^>]*/>', '', kml_text, flags=re.IGNORECASE)

    # Eliminar <href> externos manteniendo íconos locales embebidos
    kml_text, n = re.subn(
        r'<href\b[^>]*>\s*(?:https?|ftp|file)://.*?</href>',
        '',
        kml_text,
        flags=re.DOTALL | re.IGNORECASE
    )
    stats["external_hrefs"] += n
    kml_text = re.sub(r'<Icon\b[^>]*>\s*</Icon>', '', kml_text, flags=re.IGNORECASE)

    kml_text = re.sub(r'\n[ \t]*\n+', '\n', kml_text)

    return kml_text, stats


def _limpiar_archivo_kmz(kmz_origen, kmz_destino, conservar_atributos=True):
    """
    Descomprime el KMZ, migra atributos a ExtendedData, limpia los archivos .kml internos,
    valida el XML y vuelve a comprimir en el archivo KMZ destino.
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

                    contenido_limpio, st = _limpiar_contenido_kml(
                        contenido,
                        conservar_atributos=conservar_atributos
                    )

                    try:
                        ET.fromstring(contenido_limpio.encode('utf-8'))
                    except ET.ParseError as pe:
                        raise ValueError(f"XML inválido tras limpiar '{filename}': {pe}")

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


class Toolbox(object):
    def __init__(self):
        """Definición del Toolbox para ArcGIS Pro."""
        self.label = "Herramientas de Exportación KMZ Limpio"
        self.alias = "exportar_kmz_limpio_toolbox"
        self.tools = [ExportarCapasKmzLimpio, LimpiarKmzExistentes]


class ExportarCapasKmzLimpio(object):
    def __init__(self):
        """Herramienta principal para exportar capas y Group Layers a KMZ sin hipervínculos."""
        self.label = "Exportar Capas / Group Layers a KMZ Limpio (Sin Hipervínculos)"
        self.description = (
            "Exporta una o varias capas vectoriales y/o Group Layers a archivos KMZ "
            "dejando vacía la pestaña Descripción y eliminando hipervínculos o enlaces "
            "externos, mientras conserva la tabla de atributos completa en ExtendedData/SchemaData."
        )
        self.canRunInBackground = False

    def getParameterInfo(self):
        """Definición de parámetros de la herramienta."""

        # 0: Capas o Group Layers de entrada
        param_capas = arcpy.Parameter(
            displayName="Capas o Group Layers a Exportar",
            name="capas_entrada",
            datatype=["GPLayer", "DEFeatureClass"],
            parameterType="Required",
            direction="Input",
            multiValue=True
        )

        # 1: Carpeta de destino
        param_carpeta = arcpy.Parameter(
            displayName="Carpeta de Destino para los KMZ",
            name="carpeta_salida",
            datatype="DEFolder",
            parameterType="Required",
            direction="Input"
        )

        # 2: Conservar tabla de atributos en ExtendedData
        param_atributos = arcpy.Parameter(
            displayName="Conservar tabla de atributos en ExtendedData (pestaña Descripción vacía)",
            name="conservar_atributos",
            datatype="GPBoolean",
            parameterType="Optional",
            direction="Input"
        )
        param_atributos.value = True

        # 3: Opción para desglosar Group Layers
        param_desglosar = arcpy.Parameter(
            displayName="Desglosar Group Layers en archivos KMZ individuales por cada subcapa",
            name="desglosar_grupos",
            datatype="GPBoolean",
            parameterType="Optional",
            direction="Input"
        )
        param_desglosar.value = False

        # 4: Solo subcapas visibles al desglosar
        param_visibles = arcpy.Parameter(
            displayName="Exportar solo subcapas visibles (cuando se desglosan Group Layers)",
            name="solo_capas_visibles",
            datatype="GPBoolean",
            parameterType="Optional",
            direction="Input"
        )
        param_visibles.value = True

        # 5: Ajustar geometrías al terreno (CLAMPED_TO_GROUND)
        param_clamped = arcpy.Parameter(
            displayName="Ajustar geometrías al terreno (CLAMPED_TO_GROUND)",
            name="clamped_to_ground",
            datatype="GPBoolean",
            parameterType="Optional",
            direction="Input"
        )
        param_clamped.value = True

        # 6: Sobrescribir KMZ existentes
        param_sobrescribir = arcpy.Parameter(
            displayName="Sobrescribir archivos KMZ existentes",
            name="sobrescribir",
            datatype="GPBoolean",
            parameterType="Optional",
            direction="Input"
        )
        param_sobrescribir.value = True

        # 7: Parámetro derivado de salida
        param_salida = arcpy.Parameter(
            displayName="Carpeta de Salida Procesada",
            name="carpeta_resultado",
            datatype="DEFolder",
            parameterType="Derived",
            direction="Output"
        )
        param_salida.parameterDependencies = [param_carpeta.name]

        return [
            param_capas, param_carpeta, param_atributos, param_desglosar,
            param_visibles, param_clamped, param_sobrescribir, param_salida
        ]

    def isLicensed(self):
        return True

    def updateParameters(self, parameters):
        """Habilita el filtro de visibilidad solo cuando se activa desglosar Group Layers."""
        parameters[4].enabled = bool(parameters[3].value)

    def updateMessages(self, parameters):
        return

    def execute(self, parameters, messages):
        """Ejecución principal de la exportación y limpieza."""
        capas_entrada = parameters[0].values or []
        carpeta_salida = parameters[1].valueAsText
        conservar_atributos = bool(parameters[2].value) if parameters[2].value is not None else True
        desglosar_grupos = bool(parameters[3].value)
        solo_visibles = bool(parameters[4].value)
        clamped_to_ground = bool(parameters[5].value)
        sobrescribir = bool(parameters[6].value) or (hasattr(arcpy, "env") and bool(arcpy.env.overwriteOutput))

        parameters[7].value = carpeta_salida

        if not os.path.isdir(carpeta_salida):
            os.makedirs(carpeta_salida, exist_ok=True)

        mapa_activo = None
        try:
            aprx = arcpy.mp.ArcGISProject("CURRENT")
            mapa_activo = aprx.activeMap
        except Exception:
            mapa_activo = None

        arcpy.AddMessage("=" * 65)
        arcpy.AddMessage("EXPORTACIÓN DE CAPAS A KMZ LIMPIO (SIN HIPERVÍNCULOS)")
        arcpy.AddMessage(f"Carpeta destino:        {carpeta_salida}")
        arcpy.AddMessage(f"Tabla de atributos:     {'Conservada en ExtendedData (Descripción vacía)' if conservar_atributos else 'Eliminada completamente'}")
        arcpy.AddMessage(f"Desglosar Group Layers: {'Sí (KMZ individuales)' if desglosar_grupos else 'No (KMZ agrupado)'}")
        arcpy.AddMessage(f"Ajustar al terreno:     {'CLAMPED_TO_GROUND' if clamped_to_ground else 'ABSOLUTE'}")
        arcpy.AddMessage(f"Sobrescribir:           {'Sí' if sobrescribir else 'No'}")
        arcpy.AddMessage("=" * 65)

        tareas_exportacion = []
        for raw_item in capas_entrada:
            resuelto = _resolver_capa_en_mapa(raw_item, mapa_activo)

            if hasattr(resuelto, "isGroupLayer") and resuelto.isGroupLayer:
                if desglosar_grupos:
                    subcapas = [
                        sub for sub in resuelto.listLayers()
                        if not sub.isGroupLayer and (not solo_visibles or sub.visible)
                    ]
                    if not subcapas:
                        arcpy.AddWarning(f"El Group Layer '{resuelto.name}' no contiene subcapas exportables/visibles.")
                    for sub in subcapas:
                        tareas_exportacion.append((sub, sub.name))
                else:
                    tareas_exportacion.append((resuelto, resuelto.name))
            else:
                tareas_exportacion.append((resuelto, _obtener_nombre_capa(resuelto)))

        if not tareas_exportacion:
            arcpy.AddWarning("No se encontraron capas válidas para exportar.")
            return

        arcpy.AddMessage(f"Total de archivos KMZ a generar: {len(tareas_exportacion)}\n")

        nombres_usados = {}
        exitosos = 0
        omitidos = 0
        errores = 0
        temp_work_dir = tempfile.mkdtemp(prefix="arcpy_kmz_exp_")

        try:
            for idx, (capa_obj, nombre_base) in enumerate(tareas_exportacion, 1):
                nombre_limpio = _sanitizar_nombre_archivo(nombre_base)

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
                            arcpy.AddError(f"[{idx}/{len(tareas_exportacion)}] No se pudo sobrescribir '{kmz_final}': {e}")
                            errores += 1
                            continue
                    else:
                        arcpy.AddWarning(f"[{idx}/{len(tareas_exportacion)}] OMITIDO: '{nombre_final}.kmz' ya existe.")
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

                    stats = _limpiar_archivo_kmz(
                        kmz_temporal,
                        kmz_final,
                        conservar_atributos=conservar_atributos
                    )

                    arcpy.AddMessage(
                        f"[{idx}/{len(tareas_exportacion)}] EXPORTADO LIMPIO: '{nombre_final}.kmz' "
                        f"(entidades con atributos migrados: {stats['placemarks_con_atributos']}, "
                        f"descripciones vaciadas: {stats['descriptions']}, "
                        f"enlaces externos eliminados: {stats['external_hrefs'] + stats['network_links']})"
                    )
                    exitosos += 1

                except Exception as e:
                    arcpy.AddError(f"[{idx}/{len(tareas_exportacion)}] ERROR al exportar '{nombre_base}': {e}")
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

        arcpy.AddMessage("\n" + "=" * 65)
        arcpy.AddMessage("RESUMEN DE EXPORTACIÓN KMZ LIMPIO")
        arcpy.AddMessage(f" - Archivos KMZ generados con éxito: {exitosos}")
        arcpy.AddMessage(f" - Archivos omitidos:                {omitidos}")
        arcpy.AddMessage(f" - Errores:                          {errores}")
        arcpy.AddMessage("=" * 65)

        try:
            arcpy.RefreshCatalog(carpeta_salida)
        except Exception:
            pass


class LimpiarKmzExistentes(object):
    def __init__(self):
        """Herramienta complementaria para limpiar archivos .kmz ya existentes."""
        self.label = "Limpiar Archivos KMZ Existentes (Quitar Descripción e Hipervínculos)"
        self.description = (
            "Limpia uno o varios archivos .kmz ya existentes dejando vacía la pestaña "
            "Descripción y eliminando hipervínculos, conservando la tabla de atributos "
            "en ExtendedData/SchemaData."
        )
        self.canRunInBackground = False

    def getParameterInfo(self):
        param_kmz = arcpy.Parameter(
            displayName="Archivos KMZ a Limpiar",
            name="archivos_kmz",
            datatype="DEFile",
            parameterType="Required",
            direction="Input",
            multiValue=True
        )
        param_kmz.filter.list = ["kmz"]

        param_carpeta_out = arcpy.Parameter(
            displayName="Carpeta de Destino (Opcional: dejar vacía para sobrescribir en el lugar)",
            name="carpeta_destino",
            datatype="DEFolder",
            parameterType="Optional",
            direction="Input"
        )

        param_atributos = arcpy.Parameter(
            displayName="Conservar tabla de atributos en ExtendedData (pestaña Descripción vacía)",
            name="conservar_atributos",
            datatype="GPBoolean",
            parameterType="Optional",
            direction="Input"
        )
        param_atributos.value = True

        return [param_kmz, param_carpeta_out, param_atributos]

    def isLicensed(self):
        return True

    def updateParameters(self, parameters):
        return

    def updateMessages(self, parameters):
        return

    def execute(self, parameters, messages):
        archivos = parameters[0].values or []
        carpeta_destino = parameters[1].valueAsText or None
        conservar_atributos = bool(parameters[2].value) if parameters[2].value is not None else True

        if carpeta_destino:
            os.makedirs(carpeta_destino, exist_ok=True)

        arcpy.AddMessage("=" * 65)
        arcpy.AddMessage("LIMPIEZA DE ARCHIVOS KMZ EXISTENTES")
        arcpy.AddMessage(f"Tabla de atributos: {'Conservada en ExtendedData' if conservar_atributos else 'Eliminada'}")
        arcpy.AddMessage("=" * 65)

        limpiados = 0
        errores = 0

        for idx, item in enumerate(archivos, 1):
            ruta_origen = str(item).strip().strip("'\"")
            if not os.path.isfile(ruta_origen):
                arcpy.AddWarning(f"[{idx}/{len(archivos)}] No encontrado: {ruta_origen}")
                continue

            nombre_archivo = os.path.basename(ruta_origen)
            if carpeta_destino:
                ruta_destino = os.path.join(carpeta_destino, nombre_archivo)
            else:
                ruta_destino = ruta_origen

            try:
                stats = _limpiar_archivo_kmz(
                    ruta_origen,
                    ruta_destino,
                    conservar_atributos=conservar_atributos
                )
                arcpy.AddMessage(
                    f"[{idx}/{len(archivos)}] LIMPIADO: '{nombre_archivo}' "
                    f"(entidades con atributos migrados: {stats['placemarks_con_atributos']}, "
                    f"descripciones vaciadas: {stats['descriptions']}, "
                    f"enlaces externos: {stats['external_hrefs'] + stats['network_links']})"
                )
                limpiados += 1
            except Exception as e:
                arcpy.AddError(f"[{idx}/{len(archivos)}] ERROR al limpiar '{nombre_archivo}': {e}")
                errores += 1

        arcpy.AddMessage("\n" + "=" * 65)
        arcpy.AddMessage(f"RESUMEN: {limpiados} KMZ limpiados exitosamente | {errores} errores")
        arcpy.AddMessage("=" * 65)
