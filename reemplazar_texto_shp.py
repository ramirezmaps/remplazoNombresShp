# -*- coding: utf-8 -*-
"""
Herramienta de Reemplazo de Texto en Nombres de Shapefiles (.shp)
================================================================
Busca una cadena de texto específica dentro de los nombres de los shapefiles
de una carpeta y la reemplaza por otra definida por el usuario.

Opciones:
- Renombrar en la misma carpeta o guardar copias en una carpeta de destino.
- Sobrescribir archivos existentes si ya existe un shapefile con el nuevo nombre.
- Renombra de forma automática e íntegra todos los archivos componentes del shapefile:
  .shp, .shx, .dbf, .prj, .cpg, .sbn, .sbx, .shp.xml, .qpj, .cst, etc.
"""

import os
import sys
import re
import shutil
import argparse

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


def limpiar_texto(valor):
    if valor is None:
        return ""
    texto = str(valor).strip()
    if texto.lower().endswith(".shp"):
        texto = texto[:-4].strip()
    return texto


def validar_caracteres_prohibidos(texto):
    caracteres_invalidos = set(r'\/:*?"<>|')
    encontrados = [c for c in texto if c in caracteres_invalidos]
    return encontrados


def procesar_archivos_shapefile(dir_origen, dir_destino, base_old, base_new, sobrescribir=False):
    """
    Renombra en el lugar o copia con el nuevo nombre en dir_destino.
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
                f"El archivo '{old_name}' está bloqueado por ArcGIS Pro u otro programa. "
                f"Cierre la capa en el mapa o remuévala antes de procesar."
            )

    return procesados, None


def ejecutar_reemplazo(carpeta, texto_buscar, texto_reemplazo="", carpeta_destino=None, case_sensitive=False, incluir_subcarpetas=False, sobrescribir=False):
    """
    Ejecuta el reemplazo de la cadena de texto en los nombres de shapefile.
    """
    if not os.path.isdir(carpeta):
        log_error(f"La carpeta especificada no existe: {carpeta}")
        return False

    texto_buscar = limpiar_texto(texto_buscar)
    texto_reemplazo = limpiar_texto(texto_reemplazo)

    if not texto_buscar:
        log_error("El texto a buscar no puede estar vacío.")
        return False

    prohibidos = validar_caracteres_prohibidos(texto_reemplazo)
    if prohibidos:
        log_error(f"El texto de reemplazo contiene caracteres no permitidos en nombres de archivo: {' '.join(prohibidos)}")
        return False

    es_nueva_ruta = (
        carpeta_destino is not None 
        and bool(carpeta_destino.strip()) 
        and os.path.abspath(carpeta_destino).lower() != os.path.abspath(carpeta).lower()
    )

    log_info("=" * 65)
    log_info("REEMPLAZO DE CADENA DE TEXTO EN NOMBRES DE SHAPEFILES")
    log_info(f"Carpeta Origen:     {carpeta}")
    if es_nueva_ruta:
        log_info(f"Carpeta Destino:    {carpeta_destino} (Se guardarán copias renombradas)")
    else:
        log_info("Modo de Salida:     Renombrado directo en la carpeta original")
    log_info(f"Texto a buscar:     '{texto_buscar}'")
    log_info(f"Texto de reemplazo: '{texto_reemplazo}'")
    log_info(f"Sobrescribir:       {'Sí' if sobrescribir else 'No'}")
    log_info(f"Sensible a Mayús.:  {'Sí' if case_sensitive else 'No'}")
    log_info(f"Subcarpetas:        {'Sí' if incluir_subcarpetas else 'No'}")
    log_info("=" * 65)

    patron = None
    if not case_sensitive:
        patron = re.compile(re.escape(texto_buscar), re.IGNORECASE)

    carpetas_a_procesar = []
    if incluir_subcarpetas:
        for root, dirs, _ in os.walk(carpeta):
            carpetas_a_procesar.append(root)
    else:
        carpetas_a_procesar.append(carpeta)

    total_shp_encontrados = 0
    total_coincidencias = 0
    total_procesados = 0
    total_errores = 0
    total_omitidos = 0

    for dir_actual in carpetas_a_procesar:
        try:
            archivos = os.listdir(dir_actual)
        except Exception as e:
            log_warning(f"No se pudo acceder a '{dir_actual}': {e}")
            continue

        if es_nueva_ruta:
            rel_path = os.path.relpath(dir_actual, carpeta)
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
                log_warning(f"Omitido '{shp_file}': El nuevo nombre resultante quedaría vacío.")
                total_omitidos += 1
                continue

            if base_new == base_old and not es_nueva_ruta:
                total_omitidos += 1
                continue

            try:
                cant, err = procesar_archivos_shapefile(
                    dir_origen=dir_actual,
                    dir_destino=dest_dir_actual,
                    base_old=base_old,
                    base_new=base_new,
                    sobrescribir=sobrescribir
                )
                if err:
                    log_warning(f"Aviso en '{base_old}': {err}")
                    total_omitidos += 1
                else:
                    rel_dir = os.path.relpath(dir_actual, carpeta)
                    dir_label = "" if rel_dir == "." else f"[{rel_dir}] "
                    accion_txt = "Copiado y renombrado" if es_nueva_ruta else "Renombrado"
                    log_info(f"{dir_label}'{base_old}.shp' -> '{base_new}.shp' ({accion_txt}: {cant} archivos asociados)")
                    total_procesados += 1
            except PermissionError as pe:
                log_error(f"ARCHIVO BLOQUEADO en '{base_old}': {pe}")
                total_errores += 1
            except Exception as e:
                log_error(f"Error al procesar '{base_old}': {e}")
                total_errores += 1

    log_info("\n" + "=" * 65)
    log_info("RESUMEN DE PROCESAMIENTO")
    log_info(f" - Shapefiles analizados:               {total_shp_encontrados}")
    log_info(f" - Shapefiles con coincidencia de texto: {total_coincidencias}")
    log_info(f" - Shapefiles procesados exitosamente:  {total_procesados}")
    log_info(f" - Shapefiles omitidos / sin cambios:   {total_omitidos}")
    log_info(f" - Errores encontrados:                 {total_errores}")
    log_info("=" * 65)

    if HAS_ARCPY:
        try:
            arcpy.RefreshCatalog(carpeta_destino if es_nueva_ruta else carpeta)
        except Exception:
            pass

    return total_errores == 0


def main():
    """Punto de entrada para CLI o ArcGIS Pro Script Tool."""
    if HAS_ARCPY and len(sys.argv) > 1 and not sys.argv[1].startswith("-"):
        carpeta = arcpy.GetParameterAsText(0)
        texto_buscar = arcpy.GetParameterAsText(1)
        texto_reemplazo = arcpy.GetParameterAsText(2) or ""
        carpeta_destino = arcpy.GetParameterAsText(3) or None
        sobrescribir = arcpy.GetParameter(4) if arcpy.GetParameterCount() > 4 else False
        if hasattr(arcpy, "env") and arcpy.env.overwriteOutput:
            sobrescribir = True
        case_sensitive = arcpy.GetParameter(5) if arcpy.GetParameterCount() > 5 else False
        incluir_subcarpetas = arcpy.GetParameter(6) if arcpy.GetParameterCount() > 6 else False

        ejecutar_reemplazo(
            carpeta=carpeta,
            texto_buscar=texto_buscar,
            texto_reemplazo=texto_reemplazo,
            carpeta_destino=carpeta_destino,
            case_sensitive=case_sensitive,
            incluir_subcarpetas=incluir_subcarpetas,
            sobrescribir=sobrescribir
        )
    else:
        parser = argparse.ArgumentParser(
            description="Reemplaza una cadena de texto en los nombres de shapefiles de una carpeta."
        )
        parser.add_argument("-c", "--carpeta", help="Ruta de la carpeta con los shapefiles")
        parser.add_argument("-b", "--buscar", help="Texto a buscar en el nombre del shapefile")
        parser.add_argument("-r", "--reemplazo", help="Texto nuevo de reemplazo", default="")
        parser.add_argument("-d", "--destino", help="Carpeta de destino (opcional: si se omite, se renombra en el lugar)", default=None)
        parser.add_argument("--sobrescribir", help="Sobrescribir si el archivo destino existe", action="store_true")
        parser.add_argument("--case-sensitive", help="Diferenciar mayúsculas de minúsculas", action="store_true")
        parser.add_argument("--subcarpetas", help="Buscar recursivamente en subcarpetas", action="store_true")

        args = parser.parse_args()

        carpeta = args.carpeta
        texto_buscar = args.buscar
        texto_reemplazo = args.reemplazo
        carpeta_destino = args.destino

        if not carpeta:
            carpeta = input("Ingrese la ruta de la carpeta con los shapefiles: ").strip().strip('"\'')
        if not texto_buscar:
            texto_buscar = input("Ingrese el texto que desea buscar y reemplazar: ").strip()
        if args.reemplazo == "" and "-r" not in sys.argv and "--reemplazo" not in sys.argv:
            texto_reemplazo = input("Ingrese el nuevo texto de reemplazo (enter para dejarlo vacío): ").strip()

        ejecutar_reemplazo(
            carpeta=carpeta,
            texto_buscar=texto_buscar,
            texto_reemplazo=texto_reemplazo,
            carpeta_destino=carpeta_destino,
            case_sensitive=args.case_sensitive,
            incluir_subcarpetas=args.subcarpetas,
            sobrescribir=args.sobrescribir
        )


if __name__ == "__main__":
    main()
