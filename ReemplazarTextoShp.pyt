# -*- coding: utf-8 -*-
"""
Toolbox de ArcGIS Pro: Reemplazar Texto en Nombres de Shapefiles
==============================================================
Herramienta nativa (.pyt) que permite buscar una cadena de texto en los
nombres de los shapefiles de una carpeta y reemplazarla por otro valor
definido por el usuario.

Opciones incorporadas:
- Renombrar en la misma carpeta original o guardar copia en una nueva ruta de salida.
- Sobrescribir archivos existentes si ya existe un shapefile con el nuevo nombre.
- Renombra de forma automática e íntegra todos los archivos componentes:
  .shp, .shx, .dbf, .prj, .cpg, .sbn, .sbx, .shp.xml, .qpj, .cst, etc.
"""

import os
import sys
import re
import shutil
import arcpy


def _limpiar_texto(valor):
    """Limpia espacios y elimina extensión .shp si el usuario la incluyó en la búsqueda."""
    if valor is None:
        return ""
    texto = str(valor).strip()
    if texto.lower().endswith(".shp"):
        texto = texto[:-4].strip()
    return texto


def _validar_caracteres_prohibidos(texto):
    """Comprueba que no se introduzcan caracteres prohibidos por el sistema operativo."""
    caracteres_invalidos = set(r'\/:*?"<>|')
    encontrados = [c for c in texto if c in caracteres_invalidos]
    return encontrados


def _procesar_archivos_shapefile(dir_origen, dir_destino, base_old, base_new, sobrescribir=False):
    """
    Renombra en la misma carpeta (in-place) o guarda una copia con nuevo nombre
    en una carpeta de destino diferente.
    """
    prefix_old = base_old.lower() + "."
    prefix_new = base_new

    archivos_en_carpeta = os.listdir(dir_origen)

    archivos_asociados = []
    for f in archivos_en_carpeta:
        f_lower = f.lower()
        if f_lower.startswith(prefix_old):
            suffix = f[len(base_old):]
            new_file_name = f"{prefix_new}{suffix}"
            archivos_asociados.append((f, new_file_name))

    if not archivos_asociados:
        return 0, f"No se encontraron archivos asociados a '{base_old}'."

    shp_antiguo = f"{base_old}.shp".lower()
    tiene_shp = any(f.lower() == shp_antiguo for f, _ in archivos_asociados)
    if not tiene_shp:
        return 0, f"No se encontró el archivo principal '{base_old}.shp'."

    es_nueva_ruta = (
        dir_destino is not None 
        and bool(dir_destino.strip()) 
        and os.path.abspath(dir_destino).lower() != os.path.abspath(dir_origen).lower()
    )
    target_dir = dir_destino if es_nueva_ruta else dir_origen

    if es_nueva_ruta:
        os.makedirs(target_dir, exist_ok=True)

    shp_nuevo = os.path.join(target_dir, f"{base_new}.shp")
    if os.path.exists(shp_nuevo) and not sobrescribir:
        ubicacion_txt = "en la carpeta de destino" if es_nueva_ruta else "en la carpeta original"
        return 0, f"El shapefile destino '{base_new}.shp' ya existe {ubicacion_txt} (active la opción de sobrescribir para reemplazarlo)."

    procesados = 0
    for old_name, new_name in archivos_asociados:
        old_path = os.path.join(dir_origen, old_name)
        new_path = os.path.join(target_dir, new_name)

        if os.path.exists(new_path):
            if sobrescribir and os.path.abspath(old_path).lower() != os.path.abspath(new_path).lower():
                try:
                    os.remove(new_path)
                except Exception as e:
                    raise PermissionError(f"No se pudo eliminar el archivo existente '{new_name}': {e}")
            elif not sobrescribir:
                continue

        try:
            if es_nueva_ruta:
                shutil.copy2(old_path, new_path)
            else:
                os.rename(old_path, new_path)
            procesados += 1
        except PermissionError:
            raise PermissionError(
                f"El archivo '{old_name}' está bloqueado por ArcGIS Pro u otro programa. "
                f"Cierre la capa en el mapa o remuévala antes de procesar."
            )

    return procesados, None


class Toolbox(object):
    def __init__(self):
        """Definición del Toolbox para ArcGIS Pro."""
        self.label = "Herramientas de Reemplazo de Texto en Shapefiles"
        self.alias = "reemplazar_texto_shp_toolbox"
        self.tools = [ReemplazarTextoShapefiles]


class ReemplazarTextoShapefiles(object):
    def __init__(self):
        """Definición de la herramienta."""
        self.label = "Reemplazar Cadena de Texto en Nombres de SHP"
        self.description = (
            "Busca una cadena de texto en los nombres de shapefiles de una carpeta y "
            "la reemplaza por otro texto. Permite renombrar en el lugar o guardar en "
            "una nueva carpeta, con opción de sobrescribir archivos existentes."
        )
        self.canRunInBackground = False

    def getParameterInfo(self):
        """Definición de los parámetros de la herramienta."""
        
        # Parámetro 0: Carpeta donde se ubican los Shapefiles
        param_folder = arcpy.Parameter(
            displayName="Carpeta de Origen con Shapefiles",
            name="carpeta_shapefiles",
            datatype="DEFolder",
            parameterType="Required",
            direction="Input"
        )

        # Parámetro 1: Cadena a buscar
        param_find = arcpy.Parameter(
            displayName="Texto a Buscar en el Nombre",
            name="texto_buscar",
            datatype="GPString",
            parameterType="Required",
            direction="Input"
        )

        # Parámetro 2: Cadena nueva de reemplazo
        param_replace = arcpy.Parameter(
            displayName="Texto de Reemplazo (dejar vacío para eliminar)",
            name="texto_reemplazo",
            datatype="GPString",
            parameterType="Optional",
            direction="Input"
        )

        # Parámetro 3: Carpeta de destino (Opcional)
        param_out_folder = arcpy.Parameter(
            displayName="Carpeta de Destino (Opcional: guardar en nueva ruta)",
            name="carpeta_destino",
            datatype="DEFolder",
            parameterType="Optional",
            direction="Input"
        )

        # Parámetro 4: Opción de sobrescribir archivos existentes
        param_overwrite = arcpy.Parameter(
            displayName="Reemplazar / Sobrescribir archivos existentes si ya existen",
            name="sobrescribir",
            datatype="GPBoolean",
            parameterType="Optional",
            direction="Input"
        )
        param_overwrite.value = False

        # Parámetro 5: Diferenciar mayúsculas de minúsculas
        param_case = arcpy.Parameter(
            displayName="Diferenciar mayúsculas de minúsculas (Sensible a mayúsculas)",
            name="case_sensitive",
            datatype="GPBoolean",
            parameterType="Optional",
            direction="Input"
        )
        param_case.value = False

        # Parámetro 6: Incluir subcarpetas
        param_sub = arcpy.Parameter(
            displayName="Incluir Subcarpetas",
            name="incluir_subcarpetas",
            datatype="GPBoolean",
            parameterType="Optional",
            direction="Input"
        )
        param_sub.value = False

        # Parámetro 7: Parámetro derivado de salida
        param_out = arcpy.Parameter(
            displayName="Carpeta Resultante",
            name="carpeta_salida",
            datatype="DEFolder",
            parameterType="Derived",
            direction="Output"
        )
        param_out.parameterDependencies = [param_folder.name]

        return [
            param_folder, param_find, param_replace, param_out_folder,
            param_overwrite, param_case, param_sub, param_out
        ]

    def isLicensed(self):
        return True

    def updateParameters(self, parameters):
        return

    def updateMessages(self, parameters):
        """Validaciones en tiempo real para los parámetros."""
        if parameters[0].altered and parameters[0].valueAsText:
            if not os.path.isdir(parameters[0].valueAsText):
                parameters[0].setErrorMessage("La carpeta de origen seleccionada no existe.")

        if parameters[2].altered and parameters[2].valueAsText:
            prohibidos = _validar_caracteres_prohibidos(parameters[2].valueAsText)
            if prohibidos:
                parameters[2].setErrorMessage(
                    f"El texto contiene caracteres no válidos para nombres de archivo: {' '.join(prohibidos)}"
                )

    def execute(self, parameters, messages):
        """Ejecución del reemplazo en ArcGIS Pro."""
        folder_path = parameters[0].valueAsText
        texto_buscar = parameters[1].valueAsText
        texto_reemplazo = parameters[2].valueAsText or ""
        carpeta_destino = parameters[3].valueAsText or None
        sobrescribir_param = parameters[4].value
        case_sensitive = parameters[5].value
        incluir_subcarpetas = parameters[6].value

        # Considerar sobrescritura si el checkbox está activo o el entorno global de ArcGIS Pro lo indica
        sobrescribir = bool(sobrescribir_param) or (hasattr(arcpy, "env") and bool(arcpy.env.overwriteOutput))

        es_nueva_ruta = (
            carpeta_destino is not None 
            and bool(carpeta_destino.strip()) 
            and os.path.abspath(carpeta_destino).lower() != os.path.abspath(folder_path).lower()
        )
        
        carpeta_final = carpeta_destino if es_nueva_ruta else folder_path
        parameters[7].value = carpeta_final

        texto_buscar = _limpiar_texto(texto_buscar)
        texto_reemplazo = _limpiar_texto(texto_reemplazo)

        if not texto_buscar:
            arcpy.AddError("El texto a buscar no puede estar vacío.")
            return

        prohibidos = _validar_caracteres_prohibidos(texto_reemplazo)
        if prohibidos:
            arcpy.AddError(f"El texto de reemplazo contiene caracteres inválidos: {' '.join(prohibidos)}")
            return

        arcpy.AddMessage("=" * 65)
        arcpy.AddMessage("REEMPLAZO DE CADENA DE TEXTO EN NOMBRES DE SHAPEFILES")
        arcpy.AddMessage(f"Carpeta Origen:     {folder_path}")
        if es_nueva_ruta:
            arcpy.AddMessage(f"Carpeta Destino:    {carpeta_destino} (Se guardarán copias renombradas)")
        else:
            arcpy.AddMessage("Modo de Salida:     Renombrado directo en la carpeta original")
        arcpy.AddMessage(f"Texto a buscar:     '{texto_buscar}'")
        arcpy.AddMessage(f"Texto de reemplazo: '{texto_reemplazo}'")
        arcpy.AddMessage(f"Sobrescribir:       {'Sí' if sobrescribir else 'No'}")
        arcpy.AddMessage(f"Sensible a Mayús.:  {'Sí' if case_sensitive else 'No'}")
        arcpy.AddMessage(f"Subcarpetas:        {'Sí' if incluir_subcarpetas else 'No'}")
        arcpy.AddMessage("=" * 65)

        patron = None
        if not case_sensitive:
            patron = re.compile(re.escape(texto_buscar), re.IGNORECASE)

        carpetas_a_procesar = []
        if incluir_subcarpetas:
            for root, _, _ in os.walk(folder_path):
                carpetas_a_procesar.append(root)
        else:
            carpetas_a_procesar.append(folder_path)

        total_shp_encontrados = 0
        total_coincidencias = 0
        total_procesados = 0
        total_errores = 0
        total_omitidos = 0

        for dir_actual in carpetas_a_procesar:
            try:
                archivos = os.listdir(dir_actual)
            except Exception as e:
                arcpy.AddWarning(f"No se pudo acceder a la carpeta '{dir_actual}': {e}")
                continue

            # Determinar carpeta destino para este directorio (reproduciendo estructura si hay subcarpetas)
            if es_nueva_ruta:
                rel_path = os.path.relpath(dir_actual, folder_path)
                dest_dir_actual = os.path.join(carpeta_destino, rel_path) if rel_path != "." else carpeta_destino
            else:
                dest_dir_actual = dir_actual

            shp_archivos = [f for f in archivos if f.lower().endswith(".shp")]

            for shp_file in shp_archivos:
                total_shp_encontrados += 1
                base_old = shp_file[:-4]

                tiene_coincidencia = False
                if case_sensitive:
                    tiene_coincidencia = texto_buscar in base_old
                    base_new = base_old.replace(texto_buscar, texto_reemplazo)
                else:
                    tiene_coincidencia = bool(patron.search(base_old))
                    base_new = patron.sub(texto_reemplazo, base_old)

                if not tiene_coincidencia:
                    continue

                total_coincidencias += 1

                if not base_new.strip():
                    arcpy.AddWarning(f"Omitido '{shp_file}': El nuevo nombre resultante quedaría vacío.")
                    total_omitidos += 1
                    continue

                if base_new == base_old and not es_nueva_ruta:
                    total_omitidos += 1
                    continue

                try:
                    cant, err = _procesar_archivos_shapefile(
                        dir_origen=dir_actual,
                        dir_destino=dest_dir_actual,
                        base_old=base_old,
                        base_new=base_new,
                        sobrescribir=sobrescribir
                    )
                    if err:
                        arcpy.AddWarning(f"Aviso en '{base_old}': {err}")
                        total_omitidos += 1
                    else:
                        rel_dir = os.path.relpath(dir_actual, folder_path)
                        dir_label = "" if rel_dir == "." else f"[{rel_dir}] "
                        accion_txt = "Copiado y renombrado" if es_nueva_ruta else "Renombrado"
                        arcpy.AddMessage(f"{dir_label}'{base_old}.shp' -> '{base_new}.shp' ({accion_txt}: {cant} archivos asociados)")
                        total_procesados += 1
                except PermissionError as pe:
                    arcpy.AddError(f"ARCHIVO BLOQUEADO en '{base_old}': {pe}")
                    total_errores += 1
                except Exception as e:
                    arcpy.AddError(f"Error al procesar '{base_old}': {e}")
                    total_errores += 1

        arcpy.AddMessage("\n" + "=" * 65)
        arcpy.AddMessage("RESUMEN DE PROCESAMIENTO")
        arcpy.AddMessage(f" - Shapefiles analizados:               {total_shp_encontrados}")
        arcpy.AddMessage(f" - Shapefiles con coincidencia de texto: {total_coincidencias}")
        arcpy.AddMessage(f" - Shapefiles procesados exitosamente:  {total_procesados}")
        arcpy.AddMessage(f" - Shapefiles omitidos / sin cambios:   {total_omitidos}")
        arcpy.AddMessage(f" - Errores encontrados:                 {total_errores}")
        arcpy.AddMessage("=" * 65)

        try:
            arcpy.RefreshCatalog(carpeta_final)
        except Exception:
            pass
