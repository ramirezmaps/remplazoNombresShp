# -*- coding: utf-8 -*-
"""
Herramienta de Reemplazo de Elementos en Layouts de ArcGIS Pro (.aprx)
=====================================================================
Permite modificar masivamente elementos dentro de los layouts de un proyecto:
1. Textos: Buscar y reemplazar cadenas de texto en títulos, notas, membretes, etc.
2. Imágenes / Logos: Actualizar la ruta del archivo de imagen de logos o elementos gráficos.
3. Map Frames: Reasignar el mapa vinculado al marco de mapa.

Aplica a todos los layouts del proyecto o a un layout específico seleccionado.
"""

import os
import sys
import re

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


def procesar_elementos_layout(
    aprx_path=None,
    tipo_elemento="Texto",
    layout_filtro="* (Todos los Layouts)",
    nombre_elemento_filtro=None,
    texto_buscar=None,
    texto_reemplazo="",
    case_sensitive=False,
    nueva_imagen_path=None,
    nuevo_mapa_nombre=None,
    guardar_cambios=False
):
    """
    Función principal para buscar y reemplazar elementos en los layouts del proyecto.
    """
    if not HAS_ARCPY:
        log_error("Esta herramienta requiere el módulo 'arcpy' de ArcGIS Pro.")
        return False

    # 1. Determinar el proyecto
    es_current = False
    if not aprx_path or not str(aprx_path).strip() or str(aprx_path).upper() == "CURRENT":
        try:
            aprx = arcpy.mp.ArcGISProject("CURRENT")
            es_current = True
            proyecto_nombre = "Proyecto Activo (CURRENT)"
        except Exception as e:
            log_error(f"No se pudo acceder al proyecto activo ('CURRENT'): {e}")
            return False
    else:
        if not os.path.isfile(aprx_path):
            log_error(f"El archivo de proyecto no existe: {aprx_path}")
            return False
        try:
            aprx = arcpy.mp.ArcGISProject(aprx_path)
            proyecto_nombre = aprx_path
        except Exception as e:
            log_error(f"No se pudo abrir el proyecto .aprx: {e}")
            return False

    log_info("=" * 65)
    log_info("REEMPLAZO DE ELEMENTOS EN LAYOUTS DE ARCGIS PRO")
    log_info(f"Proyecto:           {proyecto_nombre}")
    log_info(f"Tipo de Elemento:   {tipo_elemento}")
    log_info(f"Filtro de Layout:   {layout_filtro or '* (Todos los Layouts)'}")
    if nombre_elemento_filtro and nombre_elemento_filtro.strip():
        log_info(f"Filtro de Elemento: '{nombre_elemento_filtro}'")
    log_info("=" * 65)

    # 2. Filtrar layouts
    todos_los_layouts = aprx.listLayouts()
    if not todos_los_layouts:
        log_warning("El proyecto no contiene ningún Layout.")
        return True

    layouts_a_procesar = []
    if not layout_filtro or layout_filtro.startswith("*"):
        layouts_a_procesar = todos_los_layouts
    else:
        layouts_a_procesar = [l for l in todos_los_layouts if l.name.lower() == layout_filtro.lower()]
        if not layouts_a_procesar:
            log_warning(f"No se encontró ningún layout con el nombre '{layout_filtro}'.")
            return False

    log_info(f"Layouts a examinar: {len(layouts_a_procesar)}")

    filtro_elem = nombre_elemento_filtro.strip().lower() if nombre_elemento_filtro and nombre_elemento_filtro.strip() else None

    total_elementos_modificados = 0
    total_layouts_modificados = 0

    # 3. Procesar según tipo de elemento
    if tipo_elemento == "Texto":
        if not texto_buscar:
            log_error("Debe ingresar un texto para buscar.")
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
                    log_info(f"[{lyt.name}] Elemento de texto '{elem.name}': Reemplazado con éxito.")

            if modificados_en_lyt > 0:
                total_layouts_modificados += 1

    elif tipo_elemento == "Imagen / Logo":
        if not nueva_imagen_path or not os.path.isfile(nueva_imagen_path):
            log_error(f"La ruta de la nueva imagen no es válida o el archivo no existe: {nueva_imagen_path}")
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
                    log_info(f"[{lyt.name}] Elemento de imagen '{elem.name}': Imagen actualizada a '{os.path.basename(nueva_imagen_path)}'.")
                except Exception as e:
                    log_warning(f"[{lyt.name}] No se pudo actualizar '{elem.name}': {e}")

            if modificados_en_lyt > 0:
                total_layouts_modificados += 1

    elif tipo_elemento == "Mapa en Map Frame":
        if not nuevo_mapa_nombre or not nuevo_mapa_nombre.strip():
            log_error("Debe especificar el nombre del nuevo Mapa a vincular al marco de mapa.")
            return False

        mapas_disponibles = {m.name.lower(): m for m in aprx.listMaps()}
        nuevo_map_obj = mapas_disponibles.get(nuevo_mapa_nombre.strip().lower())

        if not nuevo_map_obj:
            nombres_maps = [m.name for m in aprx.listMaps()]
            log_error(f"No se encontró el mapa '{nuevo_mapa_nombre}'. Mapas disponibles en el proyecto: {', '.join(nombres_maps)}")
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
                    log_info(f"[{lyt.name}] Marco de mapa '{elem.name}': Vinculado al mapa '{nuevo_map_obj.name}'.")
                except Exception as e:
                    log_warning(f"[{lyt.name}] Error al vincular mapa en '{elem.name}': {e}")

            if modificados_en_lyt > 0:
                total_layouts_modificados += 1

    else:
        log_error(f"Tipo de elemento desconocido: {tipo_elemento}")
        return False

    log_info("\n" + "=" * 65)
    log_info("RESUMEN DE MODIFICACIÓN DE LAYOUTS")
    log_info(f" - Layouts analizados:            {len(layouts_a_procesar)}")
    log_info(f" - Layouts con cambios:           {total_layouts_modificados}")
    log_info(f" - Total de elementos modificados:{total_elementos_modificados}")
    log_info("=" * 65)

    # 4. Guardar cambios si corresponde
    if guardar_cambios:
        try:
            aprx.save()
            log_info("Cambios guardados con éxito en el archivo .aprx.")
        except Exception as e:
            log_warning(f"No se pudo guardar automáticamente el proyecto: {e}")
    else:
        if es_current:
            log_info("Los cambios se aplicaron en el proyecto activo en memoria.")
            log_info("-> Revise los layouts en ArcGIS Pro y guarde con Ctrl+S si está conforme.")
        else:
            log_info("Aviso: El archivo .aprx no fue sobrescrito (active 'Guardar cambios automáticamente' si desea guardarlo en disco).")

    return True


def main():
    if not HAS_ARCPY:
        print("[ERROR] arcpy no está instalado o no se encuentra en el entorno actual.")
        return

    # Parámetros desde línea de comando / Script Tool
    if len(sys.argv) > 1 and not sys.argv[1].startswith("-"):
        aprx_path = arcpy.GetParameterAsText(0) or None
        tipo_elem = arcpy.GetParameterAsText(1) or "Texto"
        layout_filtro = arcpy.GetParameterAsText(2) or "* (Todos los Layouts)"
        nombre_filtro = arcpy.GetParameterAsText(3) or None
        texto_buscar = arcpy.GetParameterAsText(4) or None
        texto_reemplazo = arcpy.GetParameterAsText(5) or ""
        case_sensitive = arcpy.GetParameter(6) if arcpy.GetParameterCount() > 6 else False
        nueva_imagen = arcpy.GetParameterAsText(7) or None
        nuevo_mapa = arcpy.GetParameterAsText(8) or None
        guardar = arcpy.GetParameter(9) if arcpy.GetParameterCount() > 9 else False

        procesar_elementos_layout(
            aprx_path=aprx_path,
            tipo_elemento=tipo_elem,
            layout_filtro=layout_filtro,
            nombre_elemento_filtro=nombre_filtro,
            texto_buscar=texto_buscar,
            texto_reemplazo=texto_reemplazo,
            case_sensitive=case_sensitive,
            nueva_imagen_path=nueva_imagen,
            nuevo_mapa_nombre=nuevo_mapa,
            guardar_cambios=guardar
        )
    else:
        print("Para ejecutar interactivamente o en consola, proporcione los argumentos necesarios o ejecute a través de ArcGIS Pro.")


if __name__ == "__main__":
    main()
