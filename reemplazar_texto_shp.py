# -*- coding: utf-8 -*-
"""
Herramienta de Reemplazo de Texto en Nombres de Shapefiles (.shp)
================================================================
Busca una cadena de texto específica dentro de los nombres de los shapefiles
de una carpeta y la reemplaza por otra definida por el usuario.

Renombra de forma automática e íntegra todos los archivos componentes del shapefile:
.shp, .shx, .dbf, .prj, .cpg, .sbn, .sbx, .shp.xml, .qpj, .cst, etc.

Ejemplo de uso:
  - Texto a buscar: 'SITIO_N1_EL_SAUCE'
  - Texto nuevo:    'SITIO_N2_LOS_ALMENDROS'
  - 'SITIO_N1_EL_SAUCE_rios.shp' -> 'SITIO_N2_LOS_ALMENDROS_rios.shp'
"""

import os
import sys
import re
import argparse

try:
    import arcpy
    HAS_ARCPY = True
except ImportError:
    HAS_ARCPY = False


def log_info(msg):
    """Muestra un mensaje informativo en ArcGIS Pro o en consola."""
    if HAS_ARCPY:
        arcpy.AddMessage(msg)
    else:
        print(f"[INFO] {msg}")


def log_warning(msg):
    """Muestra un mensaje de advertencia en ArcGIS Pro o en consola."""
    if HAS_ARCPY:
        arcpy.AddWarning(msg)
    else:
        print(f"[ADVERTENCIA] {msg}")


def log_error(msg):
    """Muestra un mensaje de error en ArcGIS Pro o en consola."""
    if HAS_ARCPY:
        arcpy.AddError(msg)
    else:
        print(f"[ERROR] {msg}")


def limpiar_texto(valor):
    """Limpia espacios y elimina extensión .shp si el usuario la incluyó en la búsqueda."""
    if valor is None:
        return ""
    texto = str(valor).strip()
    if texto.lower().endswith(".shp"):
        texto = texto[:-4].strip()
    return texto


def validar_caracteres_prohibidos(texto):
    """Comprueba que no se introduzcan caracteres prohibidos por el sistema operativo."""
    caracteres_invalidos = set(r'\/:*?"<>|')
    encontrados = [c for c in texto if c in caracteres_invalidos]
    return encontrados


def renombrar_archivos_shapefile(directorio, base_old, base_new, sobrescribir=False):
    """
    Renombra todos los archivos asociados al shapefile base_old por base_new
    dentro del directorio indicado.
    """
    prefix_old = base_old.lower() + "."
    prefix_new = base_new

    archivos_en_carpeta = os.listdir(directorio)

    archivos_asociados = []
    for f in archivos_en_carpeta:
        f_lower = f.lower()
        if f_lower.startswith(prefix_old):
            suffix = f[len(base_old):]
            new_file_name = f"{prefix_new}{suffix}"
            archivos_asociados.append((f, new_file_name))

    if not archivos_asociados:
        return 0, f"No se encontraron archivos asociados a '{base_old}'."

    # Verificar que el shapefile principal .shp existe
    shp_antiguo = f"{base_old}.shp".lower()
    tiene_shp = any(f.lower() == shp_antiguo for f, _ in archivos_asociados)
    if not tiene_shp:
        return 0, f"No se encontró el archivo principal '{base_old}.shp'."

    # Comprobar si el destino ya existe
    shp_nuevo = os.path.join(directorio, f"{base_new}.shp")
    if os.path.exists(shp_nuevo) and not sobrescribir:
        return 0, f"El shapefile destino '{base_new}.shp' ya existe en la carpeta."

    renombrados = 0
    for old_name, new_name in archivos_asociados:
        old_path = os.path.join(directorio, old_name)
        new_path = os.path.join(directorio, new_name)

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
                f"Cierre la capa en el mapa o remuévala antes de renombrar."
            )

    return renombrados, None


def ejecutar_reemplazo(carpeta, texto_buscar, texto_reemplazo="", case_sensitive=False, incluir_subcarpetas=False, sobrescribir=False):
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

    log_info("=" * 65)
    log_info("REEMPLAZO DE CADENA DE TEXTO EN NOMBRES DE SHAPEFILES")
    log_info(f"Carpeta:            {carpeta}")
    log_info(f"Texto a buscar:     '{texto_buscar}'")
    log_info(f"Texto de reemplazo: '{texto_reemplazo}'")
    log_info(f"Sensible a Mayús.:  {'Sí' if case_sensitive else 'No'}")
    log_info(f"Subcarpetas:        {'Sí' if incluir_subcarpetas else 'No'}")
    log_info("=" * 65)

    patron = None
    if not case_sensitive:
        patron = re.compile(re.escape(texto_buscar), re.IGNORECASE)

    # Identificar carpetas a examinar
    carpetas_a_procesar = []
    if incluir_subcarpetas:
        for root, dirs, _ in os.walk(carpeta):
            carpetas_a_procesar.append(root)
    else:
        carpetas_a_procesar.append(carpeta)

    total_shp_encontrados = 0
    total_coincidencias = 0
    total_renombrados = 0
    total_errores = 0
    total_omitidos = 0

    for dir_actual in carpetas_a_procesar:
        archivos = os.listdir(dir_actual)
        # Buscar todos los archivos .shp
        shp_archivos = [f for f in archivos if f.lower().endswith(".shp")]

        for shp_file in shp_archivos:
            total_shp_encontrados += 1
            base_old = shp_file[:-4]

            # Comprobar si contiene la cadena a buscar
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

            # Validar que el nuevo nombre no quede vacío
            if not base_new.strip():
                log_warning(f"Omitido '{shp_file}': El nuevo nombre resultante quedaría vacío.")
                total_omitidos += 1
                continue

            if base_new == base_old:
                total_omitidos += 1
                continue

            try:
                cant, err = renombrar_archivos_shapefile(
                    dir_actual, base_old, base_new, sobrescribir=sobrescribir
                )
                if err:
                    log_warning(f"Aviso en '{base_old}': {err}")
                    total_omitidos += 1
                else:
                    rel_dir = os.path.relpath(dir_actual, carpeta)
                    dir_label = "" if rel_dir == "." else f"[{rel_dir}] "
                    log_info(f"{dir_label}'{base_old}.shp' -> '{base_new}.shp' ({cant} archivos asociados renombrados)")
                    total_renombrados += 1
            except PermissionError as pe:
                log_error(f"ARCHIVO BLOQUEADO en '{base_old}': {pe}")
                total_errores += 1
            except Exception as e:
                log_error(f"Error al renombrar '{base_old}': {e}")
                total_errores += 1

    log_info("\n" + "=" * 65)
    log_info("RESUMEN DE REEMPLAZO")
    log_info(f" - Shapefiles analizados:               {total_shp_encontrados}")
    log_info(f" - Shapefiles con coincidencia de texto: {total_coincidencias}")
    log_info(f" - Shapefiles renombrados exitosamente: {total_renombrados}")
    log_info(f" - Shapefiles omitidos / sin cambios:   {total_omitidos}")
    log_info(f" - Errores encontrados:                 {total_errores}")
    log_info("=" * 65)

    if HAS_ARCPY:
        try:
            arcpy.RefreshCatalog(carpeta)
        except Exception:
            pass

    return total_errores == 0


def main():
    """Punto de entrada para CLI o ArcGIS Pro Script Tool."""
    if HAS_ARCPY and len(sys.argv) > 1 and not sys.argv[1].startswith("-"):
        # Llamado desde ArcGIS Pro
        carpeta = arcpy.GetParameterAsText(0)
        texto_buscar = arcpy.GetParameterAsText(1)
        texto_reemplazo = arcpy.GetParameterAsText(2) or ""
        case_sensitive = arcpy.GetParameter(3) if arcpy.GetParameterCount() > 3 else False
        incluir_subcarpetas = arcpy.GetParameter(4) if arcpy.GetParameterCount() > 4 else False
        sobrescribir = arcpy.env.overwriteOutput if hasattr(arcpy, "env") else False

        ejecutar_reemplazo(
            carpeta=carpeta,
            texto_buscar=texto_buscar,
            texto_reemplazo=texto_reemplazo,
            case_sensitive=case_sensitive,
            incluir_subcarpetas=incluir_subcarpetas,
            sobrescribir=sobrescribir
        )
    else:
        # Llamado por consola / interactivo
        parser = argparse.ArgumentParser(
            description="Reemplaza una cadena de texto en los nombres de shapefiles de una carpeta."
        )
        parser.add_argument("-c", "--carpeta", help="Ruta de la carpeta con los shapefiles")
        parser.add_argument("-b", "--buscar", help="Texto a buscar en el nombre del shapefile")
        parser.add_argument("-r", "--reemplazo", help="Texto nuevo de reemplazo", default="")
        parser.add_argument("--case-sensitive", help="Diferenciar mayúsculas de minúsculas", action="store_true")
        parser.add_argument("--subcarpetas", help="Buscar recursivamente en subcarpetas", action="store_true")
        parser.add_argument("--sobrescribir", help="Sobrescribir si el archivo destino existe", action="store_true")

        args = parser.parse_args()

        carpeta = args.carpeta
        texto_buscar = args.buscar
        texto_reemplazo = args.reemplazo

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
            case_sensitive=args.case_sensitive,
            incluir_subcarpetas=args.subcarpetas,
            sobrescribir=args.sobrescribir
        )


if __name__ == "__main__":
    main()
