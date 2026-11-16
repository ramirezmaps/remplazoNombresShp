# -*- coding: utf-8 -*-
"""
Herramienta de Renombrado Masivo de Shapefiles (.shp) para ArcGIS Pro / Python
=============================================================================
Permite renombrar múltiples shapefiles ubicados en una carpeta a partir de un
archivo Excel (.xlsx / .xls) que define los nombres antiguos y nuevos.

Opciones:
- Renombrar en la misma carpeta original o guardar copias en una nueva carpeta.
- Sobrescribir archivos existentes si ya existe un shapefile con el nuevo nombre.
- Renombra automáticamente todos los archivos componentes del shapefile:
  .shp, .shx, .dbf, .prj, .cpg, .sbn, .sbx, .shp.xml, .qpj, .cst, etc.
"""

import os
import sys
import shutil
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


def limpiar_nombre_shp(nombre):
    if nombre is None:
        return ""
    texto = str(nombre).strip()
    if texto.lower().endswith(".shp"):
        texto = texto[:-4].strip()
    return texto


def leer_equivalencias_excel(excel_path, sheet_name=None, col_old=None, col_new=None):
    if not os.path.exists(excel_path):
        raise FileNotFoundError(f"No se encontró el archivo Excel: {excel_path}")

    if HAS_PANDAS:
        sheet = sheet_name if sheet_name else 0
        df = pd.read_excel(excel_path, sheet_name=sheet)
        df = df.dropna(how='all')

        if df.empty:
            raise ValueError(f"La hoja de Excel '{sheet}' está vacía.")

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
                log_warning(f"No se encontró columna para 'Nombre Antiguo'. Se usará '{selected_old}'.")
            else:
                raise ValueError("El archivo Excel no tiene suficientes columnas.")

        if not selected_new:
            if len(df.columns) >= 2:
                selected_new = df.columns[1]
                log_warning(f"No se encontró columna para 'Nombre Nuevo'. Se usará '{selected_new}'.")
            else:
                raise ValueError("El archivo Excel debe tener al menos dos columnas.")

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
            antiguo = limpiar_nombre_shp(val_old)
            nuevo = limpiar_nombre_shp(val_new)
            if antiguo and nuevo:
                pares.append((antiguo, nuevo))
        return pares
    else:
        raise ImportError("Se requiere 'pandas' u 'openpyxl' para leer el archivo Excel.")


def procesar_archivos_shapefile(dir_origen, dir_destino, base_old, base_new, sobrescribir=False):
    """
    Renombra en el lugar o copia con nuevo nombre en dir_destino.
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
        return 0, f"El shapefile destino '{base_new}.shp' ya existe {ubicacion_txt} (active sobrescribir para reemplazarlo)."

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
                f"El archivo '{old_name}' está bloqueado por ArcGIS Pro u otra aplicación. "
                f"Cierre la capa en el mapa o remuévala antes de continuar."
            )

    return procesados, None


def ejecutar_renombrado(folder_path, excel_path, carpeta_destino=None, sheet_name=None, col_old=None, col_new=None, sobrescribir=False):
    """
    Función principal de ejecución del proceso de renombrado.
    """
    if not os.path.isdir(folder_path):
        log_error(f"La ruta de la carpeta no es válida: {folder_path}")
        return False

    es_nueva_ruta = (
        carpeta_destino is not None 
        and bool(carpeta_destino.strip()) 
        and os.path.abspath(carpeta_destino).lower() != os.path.abspath(folder_path).lower()
    )

    log_info("=" * 65)
    log_info("INICIANDO RENOMBRADO MASIVO DE SHAPEFILES CON EXCEL")
    log_info(f"Carpeta Origen:  {folder_path}")
    if es_nueva_ruta:
        log_info(f"Carpeta Destino: {carpeta_destino} (Se guardarán copias renombradas)")
    else:
        log_info("Modo de Salida:  Renombrado directo en la carpeta original")
    log_info(f"Excel:           {excel_path}")
    log_info(f"Sobrescribir:    {'Sí' if sobrescribir else 'No'}")
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
        if old_name.lower() == new_name.lower() and old_name == new_name and not es_nueva_ruta:
            log_info(f"[{idx}/{len(pares)}] OMITIDO: '{old_name}' tiene el mismo nombre antiguo y nuevo.")
            omitidos += 1
            continue

        try:
            cant_proc, detalle_error = procesar_archivos_shapefile(
                dir_origen=folder_path,
                dir_destino=carpeta_destino,
                base_old=old_name,
                base_new=new_name,
                sobrescribir=sobrescribir
            )

            if detalle_error:
                err_lower = detalle_error.lower()
                if "no se encontr" in err_lower:
                    log_warning(f"[{idx}/{len(pares)}] NO ENCONTRADO: '{old_name}.shp' no existe en la carpeta.")
                    no_encontrados += 1
                elif "ya existe" in err_lower:
                    log_warning(f"[{idx}/{len(pares)}] OMITIDO: '{new_name}.shp' ya existe en destino.")
                    omitidos += 1
                else:
                    log_warning(f"[{idx}/{len(pares)}] AVISO ({old_name}): {detalle_error}")
            else:
                accion_txt = "Copiado y renombrado" if es_nueva_ruta else "Renombrado"
                log_info(f"[{idx}/{len(pares)}] {accion_txt.upper()}: '{old_name}' -> '{new_name}' ({cant_proc} archivos asociados)")
                exitosos += 1

        except PermissionError as pe:
            log_error(f"[{idx}/{len(pares)}] BLOQUEO DETECTADO en '{old_name}': {pe}")
            errores += 1
        except Exception as e:
            log_error(f"[{idx}/{len(pares)}] ERROR al procesar '{old_name}': {e}")
            errores += 1

    log_info("\n" + "=" * 65)
    log_info("RESUMEN DEL PROCESO")
    log_info(f" - Shapefiles procesados exitosamente: {exitosos}")
    log_info(f" - Shapefiles no encontrados:          {no_encontrados}")
    log_info(f" - Shapefiles omitidos / sin cambios:   {omitidos}")
    log_info(f" - Errores encontrados:                 {errores}")
    log_info("=" * 65)

    if HAS_ARCPY:
        try:
            arcpy.RefreshCatalog(carpeta_destino if es_nueva_ruta else folder_path)
        except Exception:
            pass

    return errores == 0


def main():
    if HAS_ARCPY and len(sys.argv) > 1 and not sys.argv[1].startswith("-"):
        folder_path = arcpy.GetParameterAsText(0)
        excel_path = arcpy.GetParameterAsText(1)
        carpeta_destino = arcpy.GetParameterAsText(2) or None
        sobrescribir = arcpy.GetParameter(3) if arcpy.GetParameterCount() > 3 else False
        if hasattr(arcpy, "env") and arcpy.env.overwriteOutput:
            sobrescribir = True
        sheet_name = arcpy.GetParameterAsText(4) or None
        col_old = arcpy.GetParameterAsText(5) or None
        col_new = arcpy.GetParameterAsText(6) or None

        ejecutar_renombrado(
            folder_path=folder_path,
            excel_path=excel_path,
            carpeta_destino=carpeta_destino,
            sheet_name=sheet_name,
            col_old=col_old,
            col_new=col_new,
            sobrescribir=sobrescribir
        )
    else:
        parser = argparse.ArgumentParser(
            description="Renombra shapefiles en una carpeta según un archivo Excel."
        )
        parser.add_argument("-c", "--carpeta", help="Ruta de la carpeta que contiene los shapefiles")
        parser.add_argument("-e", "--excel", help="Ruta del archivo Excel (.xlsx / .xls)")
        parser.add_argument("-d", "--destino", help="Carpeta de destino (opcional: si se omite, se renombra en el lugar)", default=None)
        parser.add_argument("-s", "--hoja", help="Nombre de la hoja de Excel (opcional)", default=None)
        parser.add_argument("--col-antiguo", help="Nombre de la columna del nombre antiguo (opcional)", default=None)
        parser.add_argument("--col-nuevo", help="Nombre de la columna del nombre nuevo (opcional)", default=None)
        parser.add_argument("--sobrescribir", help="Sobrescribir si el archivo destino existe", action="store_true")

        args = parser.parse_args()

        folder_path = args.carpeta
        excel_path = args.excel
        carpeta_destino = args.destino

        if not folder_path:
            folder_path = input("Ingrese la ruta de la carpeta con los Shapefiles: ").strip().strip('"\'')
        if not excel_path:
            excel_path = input("Ingrese la ruta del archivo Excel: ").strip().strip('"\'')

        ejecutar_renombrado(
            folder_path=folder_path,
            excel_path=excel_path,
            carpeta_destino=carpeta_destino,
            sheet_name=args.hoja,
            col_old=args.col_antiguo,
            col_new=args.col_nuevo,
            sobrescribir=args.sobrescribir
        )


if __name__ == "__main__":
    main()
