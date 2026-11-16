# -*- coding: utf-8 -*-
"""
Herramienta de Renombrado Masivo de Shapefiles (.shp) para ArcGIS Pro / Python
=============================================================================
Permite renombrar múltiples shapefiles ubicados en una carpeta a partir de un
archivo Excel (.xlsx / .xls) que define los nombres antiguos y nuevos.

Renombra automáticamente todos los archivos componentes del shapefile:
.shp, .shx, .dbf, .prj, .cpg, .sbn, .sbx, .shp.xml, .qpj, .fbn, .fbx, etc.

Puede ser utilizado:
1. Como script independiente desde consola o terminal.
2. Como Script Tool dentro de ArcGIS Pro (dentro de un .tbx o .atbx).
3. Importado como módulo en otros scripts de automatización.
"""

import os
import sys
import argparse

try:
    import arcpy
    HAS_ARCPY = True
except ImportError:
    HAS_ARCPY = False

try:
    import pandas as pd
    HAS_PANDAS = True
except ImportError:
    HAS_PANDAS = False

try:
    import openpyxl
    HAS_OPENPYXL = True
except ImportError:
    HAS_OPENPYXL = False


def log_info(msg):
    """Emite un mensaje informativo a ArcGIS Pro o a la consola."""
    if HAS_ARCPY:
        arcpy.AddMessage(msg)
    else:
        print(f"[INFO] {msg}")


def log_warning(msg):
    """Emite un mensaje de advertencia a ArcGIS Pro o a la consola."""
    if HAS_ARCPY:
        arcpy.AddWarning(msg)
    else:
        print(f"[ADVERTENCIA] {msg}")


def log_error(msg):
    """Emite un mensaje de error a ArcGIS Pro o a la consola."""
    if HAS_ARCPY:
        arcpy.AddError(msg)
    else:
        print(f"[ERROR] {msg}")


def limpiar_nombre_shp(nombre):
    """Elimina la extensión .shp si viene en el texto y limpia espacios."""
    if nombre is None:
        return ""
    texto = str(nombre).strip()
    if texto.lower().endswith(".shp"):
        texto = texto[:-4].strip()
    return texto


def leer_equivalencias_excel(excel_path, sheet_name=None, col_old=None, col_new=None):
    """
    Lee el archivo Excel y devuelve una lista de tuplas (nombre_antiguo, nombre_nuevo).
    Detecta automáticamente las columnas si no se especifican.
    """
    if not os.path.exists(excel_path):
        raise FileNotFoundError(f"No se encontró el archivo Excel: {excel_path}")

    # Método 1: Uso de pandas (estándar en ArcGIS Pro)
    if HAS_PANDAS:
        sheet = sheet_name if sheet_name else 0
        df = pd.read_excel(excel_path, sheet_name=sheet)
        df = df.dropna(how='all')

        if df.empty:
            raise ValueError(f"La hoja de Excel '{sheet}' está vacía.")

        # Limpiar nombres de columnas
        df.columns = [str(c).strip() for c in df.columns]

        # Candidatos para auto-detección
        candidatos_old = [col_old] if col_old else []
        candidatos_old.extend([
            "nombre_antiguo", "nombre antiguo", "antiguo", "nombre_original",
            "nombre original", "original", "old_name", "old name", "old",
            "anterior", "capa_antigua", "shp_antiguo"
        ])

        candidatos_new = [col_new] if col_new else []
        candidatos_new.extend([
            "nombre_nuevo", "nombre nuevo", "nuevo", "nombre_actual",
            "nombre actual", "actual", "new_name", "new name", "new",
            "capa_nueva", "shp_nuevo"
        ])

        col_map = {str(c).lower().strip(): c for c in df.columns}
        
        # Buscar columna antigua
        selected_old = None
        for cand in candidatos_old:
            if cand and cand.lower().strip() in col_map:
                selected_old = col_map[cand.lower().strip()]
                break

        # Buscar columna nueva
        selected_new = None
        for cand in candidatos_new:
            if cand and cand.lower().strip() in col_map:
                selected_new = col_map[cand.lower().strip()]
                break

        # Fallback a posiciones si no se encontraron por nombre
        if not selected_old:
            if len(df.columns) >= 1:
                selected_old = df.columns[0]
                log_warning(f"No se encontró columna para 'Nombre Antiguo'. Se usará la columna 1: '{selected_old}'")
            else:
                raise ValueError("El archivo Excel no tiene suficientes columnas.")

        if not selected_new:
            if len(df.columns) >= 2:
                selected_new = df.columns[1]
                log_warning(f"No se encontró columna para 'Nombre Nuevo'. Se usará la columna 2: '{selected_new}'")
            else:
                raise ValueError("El archivo Excel debe tener al menos dos columnas (antiguo y nuevo).")

        log_info(f"Columna de Nombre Antiguo: '{selected_old}'")
        log_info(f"Columna de Nombre Nuevo:   '{selected_new}'")

        pares = []
        for _, row in df.iterrows():
            val_old = row[selected_old]
            val_new = row[selected_new]
            if pd.isna(val_old) or pd.isna(val_new):
                continue
            antiguo = limpiar_nombre_shp(val_old)
            nuevo = limpiar_nombre_shp(val_new)
            if antiguo and nuevo:
                pares.append((antiguo, nuevo))

        return pares

    # Método 2: Uso de openpyxl (fallback si no hubiera pandas)
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

        # Buscar en encabezado
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
            antiguo = limpiar_nombre_shp(val_old)
            nuevo = limpiar_nombre_shp(val_new)
            if antiguo and nuevo:
                pares.append((antiguo, nuevo))
        return pares
    else:
        raise ImportError("Se requiere la librería 'pandas' u 'openpyxl' para leer el archivo Excel.")


def renombrar_archivos_shapefile(folder_path, base_old, base_new, sobrescribir=False):
    """
    Renombra todos los archivos que componen el shapefile (.shp, .dbf, .shx, .prj, .shp.xml, etc.)
    en la carpeta dada.
    """
    prefix_old = base_old.lower() + "."
    prefix_new = base_new
    
    archivos_en_carpeta = os.listdir(folder_path)
    
    # Identificar todos los archivos que pertenecen a este shapefile
    archivos_asociados = []
    for f in archivos_en_carpeta:
        f_lower = f.lower()
        if f_lower.startswith(prefix_old):
            suffix = f[len(base_old):]
            new_file_name = f"{prefix_new}{suffix}"
            archivos_asociados.append((f, new_file_name))

    if not archivos_asociados:
        return 0, "No se encontraron archivos asociados."

    # Verificar si el archivo principal .shp existe
    shp_antiguo = f"{base_old}.shp".lower()
    tiene_shp = any(f.lower() == shp_antiguo for f, _ in archivos_asociados)
    if not tiene_shp:
        return 0, f"No se encontró el archivo principal '{base_old}.shp'."

    # Verificar si el destino ya existe
    shp_nuevo = os.path.join(folder_path, f"{base_new}.shp")
    if os.path.exists(shp_nuevo) and not sobrescribir:
        return 0, f"El shapefile destino '{base_new}.shp' ya existe en la carpeta (omitiendo para evitar sobrescritura)."

    # Proceder a renombrar cada archivo componente
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
                f"El archivo '{old_name}' está bloqueado por ArcGIS Pro u otra aplicación. "
                f"Cierre la capa en el mapa o cierre el software e inténtelo nuevamente."
            )

    return renombrados, None


def ejecutar_renombrado(folder_path, excel_path, sheet_name=None, col_old=None, col_new=None, sobrescribir=False):
    """
    Función principal de ejecución del proceso de renombrado.
    """
    if not os.path.isdir(folder_path):
        log_error(f"La ruta de la carpeta no es válida: {folder_path}")
        return False

    log_info("=" * 65)
    log_info("INICIANDO RENOMBRADO MASIVO DE SHAPEFILES")
    log_info(f"Carpeta: {folder_path}")
    log_info(f"Excel:   {excel_path}")
    log_info("=" * 65)

    try:
        pares = leer_equivalencias_excel(excel_path, sheet_name, col_old, col_new)
    except Exception as e:
        log_error(f"Error al leer las equivalencias desde Excel: {e}")
        return False

    log_info(f"Total de pares de nombres leídos desde Excel: {len(pares)}\n")

    exitosos = 0
    no_encontrados = 0
    omitidos = 0
    errores = 0

    for idx, (old_name, new_name) in enumerate(pares, 1):
        if old_name.lower() == new_name.lower() and old_name == new_name:
            log_info(f"[{idx}/{len(pares)}] OMITIDO: '{old_name}' tiene el mismo nombre antiguo y nuevo.")
            omitidos += 1
            continue

        try:
            # Si arcpy está disponible, podemos comprobar bloqueo de esquema
            cant_renombrada, detalle_error = renombrar_archivos_shapefile(
                folder_path, old_name, new_name, sobrescribir=sobrescribir
            )

            if detalle_error:
                err_lower = detalle_error.lower()
                if "no se encontr" in err_lower:
                    log_warning(f"[{idx}/{len(pares)}] NO ENCONTRADO: '{old_name}.shp' no existe en la carpeta.")
                    no_encontrados += 1
                elif "ya existe" in err_lower:
                    log_warning(f"[{idx}/{len(pares)}] OMITIDO: '{new_name}.shp' ya existe en la carpeta destino.")
                    omitidos += 1
                else:
                    log_warning(f"[{idx}/{len(pares)}] AVISO ({old_name}): {detalle_error}")
            else:
                log_info(f"[{idx}/{len(pares)}] RENOMBRADO CON ÉXITO: '{old_name}' -> '{new_name}' ({cant_renombrada} archivos asociados)")
                exitosos += 1

        except PermissionError as pe:
            log_error(f"[{idx}/{len(pares)}] BLOQUEO DETECTADO en '{old_name}': {pe}")
            errores += 1
        except Exception as e:
            log_error(f"[{idx}/{len(pares)}] ERROR al procesar '{old_name}': {e}")
            errores += 1

    log_info("\n" + "=" * 65)
    log_info("RESUMEN DEL PROCESO")
    log_info(f" - Shapefiles renombrados exitosamente: {exitosos}")
    log_info(f" - Shapefiles no encontrados:          {no_encontrados}")
    log_info(f" - Shapefiles omitidos / sin cambios:   {omitidos}")
    log_info(f" - Errores encontrados:                 {errores}")
    log_info("=" * 65)

    return errores == 0


def main():
    """Punto de entrada principal para ArcGIS Pro Script Tool o CLI."""
    if HAS_ARCPY and len(sys.argv) > 1 and not sys.argv[1].startswith("-"):
        # Ejecución como Script Tool tradicional en ArcGIS Pro
        folder_path = arcpy.GetParameterAsText(0)
        excel_path = arcpy.GetParameterAsText(1)
        sheet_name = arcpy.GetParameterAsText(2) or None
        col_old = arcpy.GetParameterAsText(3) or None
        col_new = arcpy.GetParameterAsText(4) or None
        sobrescribir = arcpy.env.overwriteOutput if hasattr(arcpy, "env") else False

        ejecutar_renombrado(folder_path, excel_path, sheet_name, col_old, col_new, sobrescribir)
    else:
        # Ejecución desde línea de comandos / consola interactiva
        parser = argparse.ArgumentParser(
            description="Renombra shapefiles en una carpeta según un archivo Excel."
        )
        parser.add_argument("-c", "--carpeta", help="Ruta de la carpeta que contiene los shapefiles")
        parser.add_argument("-e", "--excel", help="Ruta del archivo Excel (.xlsx / .xls)")
        parser.add_argument("-s", "--hoja", help="Nombre de la hoja de Excel (opcional)", default=None)
        parser.add_argument("--col-antiguo", help="Nombre de la columna del nombre antiguo (opcional)", default=None)
        parser.add_argument("--col-nuevo", help="Nombre de la columna del nombre nuevo (opcional)", default=None)
        parser.add_argument("--sobrescribir", help="Sobrescribir si el archivo destino existe", action="store_true")

        args = parser.parse_args()

        folder_path = args.carpeta
        excel_path = args.excel

        # Si no se pasan por argumentos, solicitar interactivamente
        if not folder_path:
            folder_path = input("Ingrese la ruta de la carpeta con los Shapefiles: ").strip().strip('"\'')
        if not excel_path:
            excel_path = input("Ingrese la ruta del archivo Excel: ").strip().strip('"\'')

        ejecutar_renombrado(
            folder_path=folder_path,
            excel_path=excel_path,
            sheet_name=args.hoja,
            col_old=args.col_antiguo,
            col_new=args.col_nuevo,
            sobrescribir=args.sobrescribir
        )


if __name__ == "__main__":
    main()
