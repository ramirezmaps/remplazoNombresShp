# -*- coding: utf-8 -*-
"""
Toolbox de ArcGIS Pro: Renombrar Shapefiles con Excel
====================================================
Herramienta nativa para ArcGIS Pro (Python Toolbox .pyt) que permite
renombrar masivamente shapefiles contenidos en una carpeta en función de
un archivo Excel (.xlsx / .xls) de equivalencias.

Renombra todos los archivos asociados a cada shapefile:
.shp, .shx, .dbf, .prj, .cpg, .sbn, .sbx, .shp.xml, .qpj, .cst, etc.
"""

import os
import sys
import arcpy

try:
    import openpyxl
    HAS_OPENPYXL = True
except ImportError:
    HAS_OPENPYXL = False

try:
    import pandas as pd
    HAS_PANDAS = True
except ImportError:
    HAS_PANDAS = False


def _limpiar_nombre(nombre):
    """Elimina la extensión .shp si viene en el texto y limpia espacios."""
    if nombre is None:
        return ""
    texto = str(nombre).strip()
    if texto.lower().endswith(".shp"):
        texto = texto[:-4].strip()
    return texto


def _renombrar_archivos(folder_path, base_old, base_new, sobrescribir=False):
    """
    Renombra todos los archivos que componen el shapefile en la carpeta dada.
    """
    prefix_old = base_old.lower() + "."
    prefix_new = base_new
    
    archivos_en_carpeta = os.listdir(folder_path)
    
    archivos_asociados = []
    for f in archivos_en_carpeta:
        f_lower = f.lower()
        if f_lower.startswith(prefix_old):
            suffix = f[len(base_old):]
            new_file_name = f"{prefix_new}{suffix}"
            archivos_asociados.append((f, new_file_name))

    if not archivos_asociados:
        return 0, f"No se encontraron archivos con el nombre base '{base_old}'."

    # Verificar si el archivo .shp existe
    shp_antiguo = f"{base_old}.shp".lower()
    tiene_shp = any(f.lower() == shp_antiguo for f, _ in archivos_asociados)
    if not tiene_shp:
        return 0, f"No se encontró el archivo principal '{base_old}.shp'."

    # Verificar si el destino ya existe
    shp_nuevo = os.path.join(folder_path, f"{base_new}.shp")
    if os.path.exists(shp_nuevo) and not sobrescribir:
        return 0, f"El shapefile destino '{base_new}.shp' ya existe en la carpeta."

    renombrados = 0
    for old_name, new_name in archivos_asociados:
        old_path = os.path.join(folder_path, old_name)
        new_path = os.path.join(folder_path, new_name)
        
        if os.path.exists(new_path):
            if sobrescribir:
                try:
                    os.remove(new_path)
                except Exception as e:
                    raise PermissionError(f"No se pudo eliminar el archivo existente '{new_name}': {e}")
            else:
                continue

        try:
            os.rename(old_path, new_path)
            renombrados += 1
        except PermissionError:
            raise PermissionError(
                f"El archivo '{old_name}' está bloqueado por ArcGIS Pro u otro programa. "
                f"Remueva la capa del mapa o cierre el proyecto e intente nuevamente."
            )

    return renombrados, None


def _leer_pares_excel(excel_path, sheet_name=None, col_old=None, col_new=None):
    """Lee el archivo Excel y devuelve pares (antiguo, nuevo)."""
    if not os.path.exists(excel_path):
        raise FileNotFoundError(f"No se encontró el archivo Excel: {excel_path}")

    # Prioridad 1: pandas (incluido en el entorno de ArcGIS Pro)
    if HAS_PANDAS:
        sheet = sheet_name if sheet_name else 0
        df = pd.read_excel(excel_path, sheet_name=sheet)
        df = df.dropna(how='all')

        if df.empty:
            raise ValueError("El archivo Excel está vacío.")

        df.columns = [str(c).strip() for c in df.columns]

        candidatos_old = [col_old] if col_old else []
        candidatos_old.extend([
            "nombre_antiguo", "nombre antiguo", "antiguo", "nombre_original",
            "original", "old_name", "old", "anterior"
        ])

        candidatos_new = [col_new] if col_new else []
        candidatos_new.extend([
            "nombre_nuevo", "nombre nuevo", "nuevo", "nombre_actual",
            "actual", "new_name", "new"
        ])

        col_map = {str(c).lower().strip(): c for c in df.columns}
        
        selected_old = None
        for cand in candidatos_old:
            if cand and cand.lower().strip() in col_map:
                selected_old = col_map[cand.lower().strip()]
                break

        selected_new = None
        for cand in candidatos_new:
            if cand and cand.lower().strip() in col_map:
                selected_new = col_map[cand.lower().strip()]
                break

        if not selected_old:
            if len(df.columns) >= 1:
                selected_old = df.columns[0]
                arcpy.AddWarning(f"Columna de nombre antiguo no encontrada explícitamente. Se usará '{selected_old}'.")
            else:
                raise ValueError("El archivo Excel no tiene columnas suficientes.")

        if not selected_new:
            if len(df.columns) >= 2:
                selected_new = df.columns[1]
                arcpy.AddWarning(f"Columna de nombre nuevo no encontrada explícitamente. Se usará '{selected_new}'.")
            else:
                raise ValueError("El archivo Excel requiere al menos 2 columnas.")

        arcpy.AddMessage(f"Columna nombre antiguo: '{selected_old}'")
        arcpy.AddMessage(f"Columna nombre nuevo:   '{selected_new}'")

        pares = []
        for _, row in df.iterrows():
            val_old = row[selected_old]
            val_new = row[selected_new]
            if pd.isna(val_old) or pd.isna(val_new):
                continue
            antiguo = _limpiar_nombre(val_old)
            nuevo = _limpiar_nombre(val_new)
            if antiguo and nuevo:
                pares.append((antiguo, nuevo))
        return pares

    # Prioridad 2: openpyxl
    elif HAS_OPENPYXL:
        wb = openpyxl.load_workbook(excel_path, data_only=True)
        sheet = wb[sheet_name] if sheet_name and sheet_name in wb.sheetnames else wb.active
        rows = list(sheet.iter_rows(values_only=True))
        wb.close()

        if not rows:
            raise ValueError("El archivo Excel está vacío.")

        header = [str(c).strip() if c is not None else "" for c in rows[0]]
        idx_old = 0
        idx_new = 1 if len(header) > 1 else 0

        for i, h in enumerate(header):
            hl = h.lower()
            if col_old and hl == col_old.lower().strip():
                idx_old = i
            elif not col_old and any(k in hl for k in ["antiguo", "old", "original"]):
                idx_old = i

            if col_new and hl == col_new.lower().strip():
                idx_new = i
            elif not col_new and any(k in hl for k in ["nuevo", "new", "actual"]):
                idx_new = i

        pares = []
        for r in rows[1:]:
            if not r or len(r) <= max(idx_old, idx_new):
                continue
            val_old = r[idx_old]
            val_new = r[idx_new]
            if val_old is None or val_new is None:
                continue
            antiguo = _limpiar_nombre(val_old)
            nuevo = _limpiar_nombre(val_new)
            if antiguo and nuevo:
                pares.append((antiguo, nuevo))
        return pares

    else:
        raise ImportError("No se encontró la librería 'pandas' ni 'openpyxl' en el entorno de Python.")


class Toolbox(object):
    def __init__(self):
        """Definición del Toolbox para ArcGIS Pro."""
        self.label = "Herramientas de Renombrado Shapefile"
        self.alias = "renombrar_shp_toolbox"
        self.tools = [RenombrarShapefiles]


class RenombrarShapefiles(object):
    def __init__(self):
        """Definición de la herramienta."""
        self.label = "Renombrar Shapefiles con Excel"
        self.description = (
            "Renombra múltiples shapefiles (.shp y todos sus archivos asociados como "
            ".shx, .dbf, .prj, .cpg, .shp.xml, etc.) en una carpeta usando una tabla "
            "de equivalencias en Excel."
        )
        self.canRunInBackground = False

    def getParameterInfo(self):
        """Definición de los parámetros de la herramienta para ArcGIS Pro."""
        
        # Parámetro 0: Carpeta donde se ubican los Shapefiles
        param_folder = arcpy.Parameter(
            displayName="Carpeta con Shapefiles",
            name="carpeta_shapefiles",
            datatype="DEFolder",
            parameterType="Required",
            direction="Input"
        )

        # Parámetro 1: Archivo Excel con las equivalencias
        param_excel = arcpy.Parameter(
            displayName="Archivo Excel con Equivalencias (.xlsx / .xls)",
            name="archivo_excel",
            datatype="DEFile",
            parameterType="Required",
            direction="Input"
        )
        param_excel.filter.list = ["xlsx", "xls"]

        # Parámetro 2: Hoja del Excel (opcional)
        param_sheet = arcpy.Parameter(
            displayName="Hoja de Excel (Opcional)",
            name="hoja_excel",
            datatype="GPString",
            parameterType="Optional",
            direction="Input"
        )

        # Parámetro 3: Columna con el nombre original/antiguo
        param_col_old = arcpy.Parameter(
            displayName="Columna de Nombre Antiguo (Opcional)",
            name="columna_antiguo",
            datatype="GPString",
            parameterType="Optional",
            direction="Input"
        )
        param_col_old.value = "nombre_antiguo"

        # Parámetro 4: Columna con el nombre nuevo
        param_col_new = arcpy.Parameter(
            displayName="Columna de Nombre Nuevo (Opcional)",
            name="columna_nuevo",
            datatype="GPString",
            parameterType="Optional",
            direction="Input"
        )
        param_col_new.value = "nombre_nuevo"

        # Parámetro 5: Parámetro derivado para encadenar en ModelBuilder
        param_out = arcpy.Parameter(
            displayName="Carpeta de Salida",
            name="carpeta_salida",
            datatype="DEFolder",
            parameterType="Derived",
            direction="Output"
        )
        param_out.parameterDependencies = [param_folder.name]

        return [param_folder, param_excel, param_sheet, param_col_old, param_col_new, param_out]

    def isLicensed(self):
        """Verifica si la herramienta tiene licencia para ejecutarse."""
        return True

    def updateParameters(self, parameters):
        """Actualiza parámetros dinámicamente al seleccionar el archivo Excel."""
        if parameters[1].altered and parameters[1].valueAsText:
            excel_path = parameters[1].valueAsText
            if os.path.exists(excel_path):
                try:
                    import openpyxl
                    wb = openpyxl.load_workbook(excel_path, read_only=True)
                    sheet_names = wb.sheetnames
                    parameters[2].filter.list = sheet_names

                    # Asignar primera hoja si no está definida
                    curr_sheet = parameters[2].valueAsText
                    if not curr_sheet or curr_sheet not in sheet_names:
                        curr_sheet = sheet_names[0]
                        parameters[2].value = curr_sheet

                    # Leer encabezados de columnas de la hoja activa
                    sheet = wb[curr_sheet]
                    headers = [
                        str(cell.value).strip() 
                        for cell in next(sheet.iter_rows(max_row=1)) 
                        if cell.value is not None
                    ]
                    wb.close()

                    if headers:
                        parameters[3].filter.list = headers
                        parameters[4].filter.list = headers

                        # Auto-seleccionar si coincide con nombres comunes
                        val_old = parameters[3].valueAsText
                        if not val_old or val_old not in headers:
                            old_matches = [
                                h for h in headers if h.lower() in [
                                    "nombre_antiguo", "nombre antiguo", "antiguo", 
                                    "old_name", "old", "original", "anterior"
                                ]
                            ]
                            parameters[3].value = old_matches[0] if old_matches else headers[0]

                        val_new = parameters[4].valueAsText
                        if not val_new or val_new not in headers:
                            new_matches = [
                                h for h in headers if h.lower() in [
                                    "nombre_nuevo", "nombre nuevo", "nuevo", 
                                    "new_name", "new", "actual"
                                ]
                            ]
                            if new_matches:
                                parameters[4].value = new_matches[0]
                            elif len(headers) > 1:
                                parameters[4].value = headers[1]
                except Exception:
                    pass

    def updateMessages(self, parameters):
        """Validaciones en tiempo real para la interfaz de usuario."""
        if parameters[0].altered and parameters[0].valueAsText:
            if not os.path.isdir(parameters[0].valueAsText):
                parameters[0].setErrorMessage("La carpeta seleccionada no existe.")

        if parameters[1].altered and parameters[1].valueAsText:
            if not os.path.isfile(parameters[1].valueAsText):
                parameters[1].setErrorMessage("El archivo Excel seleccionado no existe.")

    def execute(self, parameters, messages):
        """Código de ejecución principal de la herramienta en ArcGIS Pro."""
        folder_path = parameters[0].valueAsText
        excel_path = parameters[1].valueAsText
        sheet_name = parameters[2].valueAsText or None
        col_old = parameters[3].valueAsText or None
        col_new = parameters[4].valueAsText or None

        parameters[5].value = folder_path
        sobrescribir = arcpy.env.overwriteOutput if hasattr(arcpy, "env") else False

        arcpy.AddMessage("=" * 65)
        arcpy.AddMessage("INICIANDO RENOMBRADO MASIVO DE SHAPEFILES")
        arcpy.AddMessage(f"Carpeta: {folder_path}")
        arcpy.AddMessage(f"Excel:   {excel_path}")
        arcpy.AddMessage("=" * 65)

        try:
            pares = _leer_pares_excel(excel_path, sheet_name, col_old, col_new)
        except Exception as e:
            arcpy.AddError(f"Error al leer el archivo Excel: {str(e)}")
            return

        arcpy.AddMessage(f"Total de registros a procesar: {len(pares)}\n")

        exitosos = 0
        no_encontrados = 0
        omitidos = 0
        errores = 0

        for idx, (old_name, new_name) in enumerate(pares, 1):
            if old_name.lower() == new_name.lower() and old_name == new_name:
                arcpy.AddMessage(f"[{idx}/{len(pares)}] OMITIDO: '{old_name}' no requiere cambio de nombre.")
                omitidos += 1
                continue

            try:
                cant_renombrada, detalle_error = _renombrar_archivos(
                    folder_path, old_name, new_name, sobrescribir=sobrescribir
                )

                if detalle_error:
                    err_l = detalle_error.lower()
                    if "no se encontr" in err_l:
                        arcpy.AddWarning(f"[{idx}/{len(pares)}] NO ENCONTRADO: '{old_name}.shp' no está en la carpeta.")
                        no_encontrados += 1
                    elif "ya existe" in err_l:
                        arcpy.AddWarning(f"[{idx}/{len(pares)}] OMITIDO: '{new_name}.shp' ya existe en la carpeta.")
                        omitidos += 1
                    else:
                        arcpy.AddWarning(f"[{idx}/{len(pares)}] AVISO ({old_name}): {detalle_error}")
                else:
                    arcpy.AddMessage(f"[{idx}/{len(pares)}] RENOMBRADO CON ÉXITO: '{old_name}' -> '{new_name}' ({cant_renombrada} archivos asociados)")
                    exitosos += 1

            except PermissionError as pe:
                arcpy.AddError(f"[{idx}/{len(pares)}] ARCHIVO BLOQUEADO en '{old_name}': {pe}")
                errores += 1
            except Exception as e:
                arcpy.AddError(f"[{idx}/{len(pares)}] ERROR al procesar '{old_name}': {e}")
                errores += 1

        arcpy.AddMessage("\n" + "=" * 65)
        arcpy.AddMessage("RESUMEN DEL PROCESO")
        arcpy.AddMessage(f" - Shapefiles renombrados exitosamente: {exitosos}")
        arcpy.AddMessage(f" - Shapefiles no encontrados:          {no_encontrados}")
        arcpy.AddMessage(f" - Shapefiles omitidos / sin cambios:   {omitidos}")
        arcpy.AddMessage(f" - Errores encontrados:                 {errores}")
        arcpy.AddMessage("=" * 65)

        # Refrescar la vista del Catálogo si está disponible
        try:
            arcpy.RefreshCatalog(folder_path)
        except Exception:
            pass
