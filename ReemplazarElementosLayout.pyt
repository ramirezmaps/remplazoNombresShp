# -*- coding: utf-8 -*-
"""
Toolbox de ArcGIS Pro: Reemplazar Elementos y Exportar Layouts del Proyecto (.aprx)
==================================================================================
Herramienta nativa (.pyt) que permite:
1. Buscar y reemplazar textos en títulos, notas y membretes.
2. Actualizar logos e imágenes institucionales.
3. Reasignar mapas vinculados a marcos de mapa (Map Frames).
4. Exportar de forma masiva todos los layouts (o uno seleccionado) a una carpeta
   específica en formato PDF, JPEG, PNG o TIFF con resolución configurable y
   garantizando que el modo 'clip_to_elements' esté activo (True).
"""

import os
import sys
import re
import arcpy


def _exportar_un_layout(lyt, out_path, formato, dpi, clip_to_elements=True):
    """
    Exporta un layout garantizando clip_to_elements / clipToElements = True.
    """
    fmt = (formato or "PDF").upper().strip()
    dpi = int(dpi) if dpi else 300

    # Método 1: API moderna de ArcGIS Pro (CreateExportFormat)
    if hasattr(arcpy.mp, "CreateExportFormat"):
        try:
            export_fmt = arcpy.mp.CreateExportFormat(fmt, out_path)
            if hasattr(export_fmt, "clipToElements"):
                export_fmt.clipToElements = bool(clip_to_elements)
            if hasattr(export_fmt, "resolution"):
                export_fmt.resolution = dpi
            lyt.export(export_fmt)
            return
        except Exception:
            pass

    # Método 2: Métodos de exportación directa con clip_to_elements
    if fmt == "PDF":
        try:
            lyt.exportToPDF(out_path, resolution=dpi, clip_to_elements=clip_to_elements)
        except TypeError:
            lyt.exportToPDF(out_path, resolution=dpi)
    elif fmt in ("JPEG", "JPG"):
        try:
            lyt.exportToJPEG(out_path, resolution=dpi, clip_to_elements=clip_to_elements)
        except TypeError:
            lyt.exportToJPEG(out_path, resolution=dpi)
    elif fmt == "PNG":
        try:
            lyt.exportToPNG(out_path, resolution=dpi, clip_to_elements=clip_to_elements)
        except TypeError:
            lyt.exportToPNG(out_path, resolution=dpi)
    elif fmt in ("TIFF", "TIF"):
        try:
            lyt.exportToTIFF(out_path, resolution=dpi, clip_to_elements=clip_to_elements)
        except TypeError:
            lyt.exportToTIFF(out_path, resolution=dpi)
    else:
        try:
            lyt.exportToPDF(out_path, resolution=dpi, clip_to_elements=clip_to_elements)
        except TypeError:
            lyt.exportToPDF(out_path, resolution=dpi)


def _exportar_layouts(layouts, carpeta_export, formato="PDF", dpi=300, clip_to_elements=True):
    """Exporta los layouts indicados a la carpeta especificada."""
    os.makedirs(carpeta_export, exist_ok=True)
    fmt = (formato or "PDF").upper().strip()
    dpi = int(dpi) if dpi else 300
    exportados = 0

    arcpy.AddMessage("\n" + "-" * 50)
    arcpy.AddMessage(f"EXPORTANDO LAYOUTS A: {carpeta_export}")
    arcpy.AddMessage(f"Formato: {fmt} | Resolución: {dpi} DPI | clip_to_elements: {clip_to_elements}")
    arcpy.AddMessage("-" * 50)

    for lyt in layouts:
        safe_name = re.sub(r'[\\/*?:"<>|]', "_", lyt.name)
        ext = "jpg" if fmt in ("JPEG", "JPG") else ("tif" if fmt in ("TIFF", "TIF") else fmt.lower())
        out_path = os.path.join(carpeta_export, f"{safe_name}.{ext}")

        try:
            _exportar_un_layout(
                lyt=lyt,
                out_path=out_path,
                formato=fmt,
                dpi=dpi,
                clip_to_elements=clip_to_elements
            )
            arcpy.AddMessage(f" -> Exportado: '{lyt.name}' -> {os.path.basename(out_path)} (clip_to_elements={clip_to_elements})")
            exportados += 1
        except Exception as e:
            arcpy.AddWarning(f"Error al exportar layout '{lyt.name}': {e}")

    return exportados


def _procesar_elementos(
    aprx_path,
    tipo_elemento,
    layout_filtro,
    nombre_elemento_filtro,
    texto_buscar,
    texto_reemplazo,
    case_sensitive,
    nueva_imagen_path,
    nuevo_mapa_nombre,
    guardar_cambios,
    carpeta_export,
    formato_export,
    dpi_export,
    clip_to_elements
):
    es_current = False
    if not aprx_path or not str(aprx_path).strip() or str(aprx_path).upper() == "CURRENT":
        try:
            aprx = arcpy.mp.ArcGISProject("CURRENT")
            es_current = True
            proyecto_nombre = "Proyecto Activo (CURRENT)"
        except Exception as e:
            arcpy.AddError(f"No se pudo acceder al proyecto activo ('CURRENT'): {e}")
            return False
    else:
        if not os.path.isfile(aprx_path):
            arcpy.AddError(f"El archivo de proyecto no existe: {aprx_path}")
            return False
        try:
            aprx = arcpy.mp.ArcGISProject(aprx_path)
            proyecto_nombre = aprx_path
        except Exception as e:
            arcpy.AddError(f"No se pudo abrir el proyecto .aprx: {e}")
            return False

    arcpy.AddMessage("=" * 65)
    arcpy.AddMessage("HERRAMIENTA DE MODIFICACIÓN Y EXPORTACIÓN DE LAYOUTS")
    arcpy.AddMessage(f"Proyecto:           {proyecto_nombre}")
    arcpy.AddMessage(f"Tipo de Acción:     {tipo_elemento}")
    arcpy.AddMessage(f"Filtro de Layout:   {layout_filtro or '* (Todos los Layouts)'}")
    if nombre_elemento_filtro and nombre_elemento_filtro.strip():
        arcpy.AddMessage(f"Filtro de Elemento: '{nombre_elemento_filtro}'")
    if carpeta_export and carpeta_export.strip():
        arcpy.AddMessage(f"Exportación activa: Sí ({formato_export} @ {dpi_export} DPI, clip_to_elements={clip_to_elements})")
    arcpy.AddMessage("=" * 65)

    todos_los_layouts = aprx.listLayouts()
    if not todos_los_layouts:
        arcpy.AddWarning("El proyecto no contiene ningún Layout.")
        return True

    layouts_a_procesar = []
    if not layout_filtro or layout_filtro.startswith("*"):
        layouts_a_procesar = todos_los_layouts
    else:
        layouts_a_procesar = [l for l in todos_los_layouts if l.name.lower() == layout_filtro.lower()]
        if not layouts_a_procesar:
            arcpy.AddWarning(f"No se encontró ningún layout con el nombre '{layout_filtro}'.")
            return False

    arcpy.AddMessage(f"Layouts seleccionados: {len(layouts_a_procesar)}")

    filtro_elem = nombre_elemento_filtro.strip().lower() if nombre_elemento_filtro and nombre_elemento_filtro.strip() else None

    total_elementos_modificados = 0
    total_layouts_modificados = 0

    if tipo_elemento == "Texto":
        if not texto_buscar:
            arcpy.AddError("Debe ingresar un texto para buscar.")
            return False

        patron = None if case_sensitive else re.compile(re.escape(texto_buscar), re.IGNORECASE)

        for lyt in layouts_a_procesar:
            modificados_en_lyt = 0
            text_elements = lyt.listElements("TEXT_ELEMENT")

            for elem in text_elements:
                if filtro_elem and filtro_elem not in elem.name.lower():
                    continue

                texto_original = elem.text
                if not texto_original:
                    continue

                tiene_coincidencia = False
                if case_sensitive:
                    if texto_buscar in texto_original:
                        tiene_coincidencia = True
                        nuevo_texto = texto_original.replace(texto_buscar, texto_reemplazo or "")
                else:
                    if patron.search(texto_original):
                        tiene_coincidencia = True
                        nuevo_texto = patron.sub(texto_reemplazo or "", texto_original)

                if tiene_coincidencia:
                    elem.text = nuevo_texto
                    modificados_en_lyt += 1
                    total_elementos_modificados += 1
                    arcpy.AddMessage(f"[{lyt.name}] Elemento '{elem.name}': Texto modificado.")

            if modificados_en_lyt > 0:
                total_layouts_modificados += 1

    elif tipo_elemento == "Imagen / Logo":
        if not nueva_imagen_path or not os.path.isfile(nueva_imagen_path):
            arcpy.AddError(f"La ruta de la imagen no es válida o el archivo no existe: {nueva_imagen_path}")
            return False

        for lyt in layouts_a_procesar:
            modificados_en_lyt = 0
            pic_elements = lyt.listElements("PICTURE_ELEMENT")

            for elem in pic_elements:
                if filtro_elem and filtro_elem not in elem.name.lower():
                    continue

                try:
                    elem.sourceImage = nueva_imagen_path
                    modificados_en_lyt += 1
                    total_elementos_modificados += 1
                    arcpy.AddMessage(f"[{lyt.name}] Elemento '{elem.name}': Imagen actualizada a '{os.path.basename(nueva_imagen_path)}'.")
                except Exception as e:
                    arcpy.AddWarning(f"[{lyt.name}] No se pudo actualizar '{elem.name}': {e}")

            if modificados_en_lyt > 0:
                total_layouts_modificados += 1

    elif tipo_elemento == "Mapa en Map Frame":
        if not nuevo_mapa_nombre or not nuevo_mapa_nombre.strip():
            arcpy.AddError("Debe especificar el nombre del mapa a vincular.")
            return False

        mapas_disponibles = {m.name.lower(): m for m in aprx.listMaps()}
        nuevo_map_obj = mapas_disponibles.get(nuevo_mapa_nombre.strip().lower())

        if not nuevo_map_obj:
            nombres_maps = [m.name for m in aprx.listMaps()]
            arcpy.AddError(f"No se encontró el mapa '{nuevo_mapa_nombre}'. Mapas disponibles: {', '.join(nombres_maps)}")
            return False

        for lyt in layouts_a_procesar:
            modificados_en_lyt = 0
            mf_elements = lyt.listElements("MAPFRAME_ELEMENT")

            for elem in mf_elements:
                if filtro_elem and filtro_elem not in elem.name.lower():
                    continue

                try:
                    elem.map = nuevo_map_obj
                    modificados_en_lyt += 1
                    total_elementos_modificados += 1
                    arcpy.AddMessage(f"[{lyt.name}] Marco de mapa '{elem.name}': Vinculado a '{nuevo_map_obj.name}'.")
                except Exception as e:
                    arcpy.AddWarning(f"[{lyt.name}] Error al vincular mapa en '{elem.name}': {e}")

            if modificados_en_lyt > 0:
                total_layouts_modificados += 1

    elif tipo_elemento == "Ninguno (Solo Exportar)":
        arcpy.AddMessage("Modo de solo exportación: No se aplicaron modificaciones sobre los elementos.")

    # Guardar cambios si corresponde
    if tipo_elemento != "Ninguno (Solo Exportar)":
        if guardar_cambios:
            try:
                aprx.save()
                arcpy.AddMessage("Cambios guardados con éxito en el archivo .aprx.")
            except Exception as e:
                arcpy.AddWarning(f"No se pudo guardar automáticamente el proyecto: {e}")
        else:
            if es_current:
                arcpy.AddMessage("Los cambios se aplicaron en el proyecto activo en memoria (guarde con Ctrl+S si desea).")

    # Exportación a carpeta
    total_exportados = 0
    if carpeta_export and carpeta_export.strip():
        total_exportados = _exportar_layouts(
            layouts=layouts_a_procesar,
            carpeta_export=carpeta_export.strip(),
            formato=formato_export,
            dpi=dpi_export,
            clip_to_elements=clip_to_elements
        )

    arcpy.AddMessage("\n" + "=" * 65)
    arcpy.AddMessage("RESUMEN DEL PROCESO")
    arcpy.AddMessage(f" - Layouts analizados:             {len(layouts_a_procesar)}")
    if tipo_elemento != "Ninguno (Solo Exportar)":
        arcpy.AddMessage(f" - Layouts con elementos editados: {total_layouts_modificados}")
        arcpy.AddMessage(f" - Total de elementos modificados: {total_elementos_modificados}")
    if carpeta_export and carpeta_export.strip():
        arcpy.AddMessage(f" - Layouts exportados con éxito:   {total_exportados} (en {carpeta_export})")
        arcpy.AddMessage(f" - Modo clip_to_elements aplicado: {clip_to_elements}")
    arcpy.AddMessage("=" * 65)

    return True


class Toolbox(object):
    def __init__(self):
        """Definición del Toolbox para ArcGIS Pro."""
        self.label = "Herramientas de Modificación de Layouts"
        self.alias = "layout_tools"
        self.tools = [ReemplazarElementosLayout]


class ReemplazarElementosLayout(object):
    def __init__(self):
        """Definición de la herramienta."""
        self.label = "Reemplazar Elementos y Exportar Layouts del APRX"
        self.description = (
            "Permite buscar y reemplazar textos, imágenes/logos y mapas vinculados "
            "a marcos de mapa en los layouts de un proyecto .aprx, así como exportar "
            "masivamente todos los layouts a una carpeta en PDF, JPEG, PNG o TIFF con "
            "ajuste al contenido de los elementos (clip_to_elements = True)."
        )
        self.canRunInBackground = False

    def getParameterInfo(self):
        """Definición de los parámetros de la herramienta."""

        # 0: Archivo .aprx (Opcional, por defecto CURRENT)
        param_aprx = arcpy.Parameter(
            displayName="Proyecto ArcGIS Pro (.aprx) - Opcional, por defecto proyecto activo",
            name="proyecto_aprx",
            datatype="DEFile",
            parameterType="Optional",
            direction="Input"
        )
        param_aprx.filter.list = ["aprx"]

        # 1: Tipo de elemento / acción
        param_tipo = arcpy.Parameter(
            displayName="Tipo de Acción o Elemento a Modificar",
            name="tipo_elemento",
            datatype="GPString",
            parameterType="Required",
            direction="Input"
        )
        param_tipo.filter.type = "ValueList"
        param_tipo.filter.list = ["Texto", "Imagen / Logo", "Mapa en Map Frame", "Ninguno (Solo Exportar)"]
        param_tipo.value = "Texto"

        # 2: Layout objetivo
        param_layout = arcpy.Parameter(
            displayName="Layout Objetivo (Opcional: elegir layout específico o todos)",
            name="layout_objetivo",
            datatype="GPString",
            parameterType="Optional",
            direction="Input"
        )
        param_layout.filter.type = "ValueList"
        param_layout.filter.list = ["* (Todos los Layouts)"]
        param_layout.value = "* (Todos los Layouts)"

        # 3: Filtro por nombre del elemento
        param_filtro_nombre = arcpy.Parameter(
            displayName="Filtrar por Nombre del Elemento (Opcional: dejar vacío para todos)",
            name="filtro_nombre_elemento",
            datatype="GPString",
            parameterType="Optional",
            direction="Input"
        )

        # 4: Texto a buscar (para tipo Texto)
        param_buscar = arcpy.Parameter(
            displayName="Texto a Buscar",
            name="texto_buscar",
            datatype="GPString",
            parameterType="Optional",
            direction="Input"
        )

        # 5: Texto de reemplazo (para tipo Texto)
        param_reemplazo = arcpy.Parameter(
            displayName="Texto de Reemplazo (dejar vacío para borrar)",
            name="texto_reemplazo",
            datatype="GPString",
            parameterType="Optional",
            direction="Input"
        )

        # 6: Case sensitive (para tipo Texto)
        param_case = arcpy.Parameter(
            displayName="Diferenciar mayúsculas de minúsculas",
            name="case_sensitive",
            datatype="GPBoolean",
            parameterType="Optional",
            direction="Input"
        )
        param_case.value = False

        # 7: Nueva imagen / Logo (para tipo Imagen)
        param_imagen = arcpy.Parameter(
            displayName="Nueva Ruta de Imagen / Logo (.png, .jpg, .svg, etc.)",
            name="nueva_imagen",
            datatype="DEFile",
            parameterType="Optional",
            direction="Input"
        )
        param_imagen.filter.list = ["png", "jpg", "jpeg", "svg", "bmp", "tif", "tiff"]

        # 8: Nuevo Mapa (para tipo Map Frame)
        param_mapa = arcpy.Parameter(
            displayName="Nuevo Mapa a Vincular al Map Frame",
            name="nuevo_mapa",
            datatype="GPString",
            parameterType="Optional",
            direction="Input"
        )

        # 9: Guardar cambios automáticamente
        param_guardar = arcpy.Parameter(
            displayName="Guardar cambios automáticamente en el archivo .aprx",
            name="guardar_cambios",
            datatype="GPBoolean",
            parameterType="Optional",
            direction="Input"
        )
        param_guardar.value = False

        # 10: Carpeta de Exportación (Opcional)
        param_export_folder = arcpy.Parameter(
            displayName="Carpeta de Exportación de Layouts (Opcional)",
            name="carpeta_export",
            datatype="DEFolder",
            parameterType="Optional",
            direction="Input"
        )

        # 11: Formato de Exportación
        param_formato = arcpy.Parameter(
            displayName="Formato de Exportación",
            name="formato_export",
            datatype="GPString",
            parameterType="Optional",
            direction="Input"
        )
        param_formato.filter.type = "ValueList"
        param_formato.filter.list = ["PDF", "JPEG", "PNG", "TIFF"]
        param_formato.value = "PDF"

        # 12: Resolución DPI
        param_dpi = arcpy.Parameter(
            displayName="Resolución de Exportación (DPI)",
            name="dpi_export",
            datatype="GPLong",
            parameterType="Optional",
            direction="Input"
        )
        param_dpi.value = 300

        # 13: Ajustar al contenido de los elementos (clip_to_elements)
        param_clip = arcpy.Parameter(
            displayName="Ajustar al contenido de los elementos (clip_to_elements)",
            name="clip_to_elements",
            datatype="GPBoolean",
            parameterType="Optional",
            direction="Input"
        )
        param_clip.value = True

        # 14: Parámetro derivado de salida
        param_salida = arcpy.Parameter(
            displayName="Proyecto Modificado",
            name="proyecto_salida",
            datatype="DEFile",
            parameterType="Derived",
            direction="Output"
        )

        return [
            param_aprx, param_tipo, param_layout, param_filtro_nombre,
            param_buscar, param_reemplazo, param_case, param_imagen,
            param_mapa, param_guardar, param_export_folder, param_formato,
            param_dpi, param_clip, param_salida
        ]

    def isLicensed(self):
        return True

    def updateParameters(self, parameters):
        """Actualiza opciones dinámicas según el proyecto, tipo de elemento y exportación."""
        try:
            aprx_file = parameters[0].valueAsText or "CURRENT"
            aprx_obj = arcpy.mp.ArcGISProject(aprx_file)

            layouts = ["* (Todos los Layouts)"] + [l.name for l in aprx_obj.listLayouts()]
            parameters[2].filter.list = layouts
            if not parameters[2].valueAsText or parameters[2].valueAsText not in layouts:
                parameters[2].value = "* (Todos los Layouts)"

            maps = [m.name for m in aprx_obj.listMaps()]
            parameters[8].filter.list = maps
        except Exception:
            pass

        tipo = parameters[1].valueAsText
        if tipo == "Texto":
            parameters[3].enabled = True
            parameters[4].enabled = True
            parameters[5].enabled = True
            parameters[6].enabled = True
            parameters[7].enabled = False
            parameters[8].enabled = False
            parameters[9].enabled = True
        elif tipo == "Imagen / Logo":
            parameters[3].enabled = True
            parameters[4].enabled = False
            parameters[5].enabled = False
            parameters[6].enabled = False
            parameters[7].enabled = True
            parameters[8].enabled = False
            parameters[9].enabled = True
        elif tipo == "Mapa en Map Frame":
            parameters[3].enabled = True
            parameters[4].enabled = False
            parameters[5].enabled = False
            parameters[6].enabled = False
            parameters[7].enabled = False
            parameters[8].enabled = True
            parameters[9].enabled = True
        elif tipo == "Ninguno (Solo Exportar)":
            parameters[3].enabled = False
            parameters[4].enabled = False
            parameters[5].enabled = False
            parameters[6].enabled = False
            parameters[7].enabled = False
            parameters[8].enabled = False
            parameters[9].enabled = False

        # Habilitar opciones de exportación si hay carpeta o si es modo solo exportar
        tiene_carpeta = bool(parameters[10].valueAsText) or (tipo == "Ninguno (Solo Exportar)")
        parameters[11].enabled = tiene_carpeta # formato
        parameters[12].enabled = tiene_carpeta # dpi
        parameters[13].enabled = tiene_carpeta # clip_to_elements

    def updateMessages(self, parameters):
        """Validación de parámetros obligatorios según el tipo seleccionado."""
        tipo = parameters[1].valueAsText
        if tipo == "Texto":
            if parameters[4].altered and not parameters[4].valueAsText:
                parameters[4].setErrorMessage("Debe indicar el texto a buscar.")
        elif tipo == "Imagen / Logo":
            if parameters[7].altered and not parameters[7].valueAsText:
                parameters[7].setErrorMessage("Debe seleccionar el archivo de la nueva imagen.")
        elif tipo == "Mapa en Map Frame":
            if parameters[8].altered and not parameters[8].valueAsText:
                parameters[8].setErrorMessage("Debe indicar el nombre del nuevo mapa.")
        elif tipo == "Ninguno (Solo Exportar)":
            if not parameters[10].valueAsText:
                parameters[10].setErrorMessage("Debe seleccionar una carpeta de exportación.")

    def execute(self, parameters, messages):
        """Ejecución de la herramienta."""
        aprx_path = parameters[0].valueAsText or None
        tipo_elemento = parameters[1].valueAsText or "Texto"
        layout_filtro = parameters[2].valueAsText or "* (Todos los Layouts)"
        nombre_filtro = parameters[3].valueAsText or None
        texto_buscar = parameters[4].valueAsText or None
        texto_reemplazo = parameters[5].valueAsText or ""
        case_sensitive = parameters[6].value
        nueva_imagen = parameters[7].valueAsText or None
        nuevo_mapa = parameters[8].valueAsText or None
        guardar_cambios = parameters[9].value
        carpeta_export = parameters[10].valueAsText or None
        formato_export = parameters[11].valueAsText or "PDF"
        dpi_export = parameters[12].value or 300
        clip_to_elements = parameters[13].value if parameters[13].value is not None else True

        parameters[14].value = aprx_path or "CURRENT"

        _procesar_elementos(
            aprx_path=aprx_path,
            tipo_elemento=tipo_elemento,
            layout_filtro=layout_filtro,
            nombre_elemento_filtro=nombre_filtro,
            texto_buscar=texto_buscar,
            texto_reemplazo=texto_reemplazo,
            case_sensitive=case_sensitive,
            nueva_imagen_path=nueva_imagen,
            nuevo_mapa_nombre=nuevo_mapa,
            guardar_cambios=guardar_cambios,
            carpeta_export=carpeta_export,
            formato_export=formato_export,
            dpi_export=dpi_export,
            clip_to_elements=clip_to_elements
        )
