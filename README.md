# Herramientas de Renombrado Masivo de Shapefiles para ArcGIS Pro

Repositorio con herramientas tipo **Python Toolbox (`.pyt`)** y scripts independientes para ArcGIS Pro diseñados para renombrar shapefiles de forma masiva e íntegra (renombrando automáticamente `.shp`, `.shx`, `.dbf`, `.prj`, `.cpg`, `.sbn`, `.sbx`, `.shp.xml`, `.qpj`, etc.).

---

## 📦 Herramientas Incluidas

### 1. `ReemplazarTextoShp.pyt` — Reemplazo directo de cadena de texto (¡NUEVO!)
Permite buscar un patrón o fragmento de texto en los nombres de los shapefiles de una carpeta y reemplazarlo por otro valor definido por el usuario (o eliminarlo).

* **Ejemplo práctico:**
  - Carpeta contiene: `SITIO_N1_EL_SAUCE_rios.shp`, `SITIO_N1_EL_SAUCE_caminos.shp`
  - **Texto a buscar:** `SITIO_N1_EL_SAUCE`
  - **Texto de reemplazo:** `SITIO_N2_LOS_ALMENDROS`
  - **Resultado:** `SITIO_N2_LOS_ALMENDROS_rios.shp`, `SITIO_N2_LOS_ALMENDROS_caminos.shp` (con todos sus archivos asociados `.dbf`, `.prj`, etc.).

* **Parámetros disponibles:**
  - **Carpeta con Shapefiles:** Carpeta donde se ubican las capas.
  - **Texto a Buscar en el Nombre:** Cadena o prefijo a sustituir.
  - **Texto de Reemplazo:** Nuevo texto (si se deja vacío, se elimina el fragmento buscado).
  - **Diferenciar mayúsculas de minúsculas:** Opcional (por defecto ignora mayúsculas/minúsculas).
  - **Incluir Subcarpetas:** Opcional (permite procesar recursivamente).

---

### 2. `RenombrarShapefiles.pyt` — Renombrado mediante tabla Excel
Permite pasarle un archivo Excel (`.xlsx` o `.xls`) con una tabla de equivalencias con los nombres antiguos y nuevos.

* **Parámetros disponibles:**
  - **Carpeta con Shapefiles:** Carpeta que contiene los shapefiles.
  - **Archivo Excel con Equivalencias:** Archivo `.xlsx` o `.xls` con los pares de nombres.
  - **Hoja de Excel (Opcional):** Desplegable automático con las pestañas del libro.
  - **Columna Nombre Antiguo / Nuevo (Opcional):** Se autoseleccionan si se llaman `nombre_antiguo` / `nombre_nuevo`.

---

## 🚀 Cómo usar las herramientas en ArcGIS Pro

1. Abre tu proyecto en **ArcGIS Pro**.
2. Abre el panel **Catalog** (*Catálogo*).
3. Haz clic derecho sobre la carpeta **Toolboxes** (*Cajas de herramientas*) -> **Add Toolbox** (*Agregar caja de herramientas*).
4. Elige la herramienta que necesites:
   - `ReemplazarTextoShp.pyt`
   - `RenombrarShapefiles.pyt`
5. Haz doble clic sobre la herramienta para abrir el panel de Geoprocesamiento, ingresa los parámetros y pulsa **Run** (*Ejecutar*).

Al finalizar, el Catálogo de ArcGIS Pro se actualiza automáticamente (`arcpy.RefreshCatalog`) mostrando los nuevos nombres de inmediato.

---

## 💻 Ejecución desde Consola o Terminal (Python puro)

Ambas herramientas cuentan con su script equivalente ejecutable desde la terminal:

### Para reemplazo de texto:
```bash
# Modo interactivo:
python reemplazar_texto_shp.py

# Modo directo por línea de comandos:
python reemplazar_texto_shp.py --carpeta "C:\MisCapas" --buscar "SITIO_N1_EL_SAUCE" --reemplazo "SITIO_N2_LOS_ALMENDROS"
```

### Para renombrado por Excel:
```bash
# Modo interactivo:
python renombrar_shp.py

# Modo directo por línea de comandos:
python renombrar_shp.py --carpeta "C:\MisCapas" --excel "C:\MisCapas\plantilla_ejemplo.xlsx"
```

---

## 🧩 Archivos que se renombran automáticamente

Un **Shapefile** está compuesto por múltiples archivos que comparten el mismo nombre base. Ambas herramientas renombran de forma simultánea todos los componentes existentes:

- `.shp`: Geometría vectorial.
- `.shx`: Índice de geometrías.
- `.dbf`: Tabla de atributos dBase.
- `.prj`: Proyección cartográfica y sistema de coordenadas.
- `.cpg`: Juego de caracteres / codificación.
- `.sbn` y `.sbx`: Índices espaciales de ArcGIS.
- `.shp.xml`: Metadatos ArcGIS.
- `.qpj`: Proyección auxiliar QGIS.
- `.cst`, `.fbn`, `.fbx`, `.atx`, etc.

---

## ⚠️ Consejos Importantes

> [!IMPORTANT]
> **Bloqueos de archivo (.sr.lock):**
> Si el shapefile está cargado en el mapa activo de ArcGIS Pro, el programa genera un archivo de bloqueo (`.sr.lock`). En caso de advertencia por bloqueo, **remueve la capa del mapa o cierra el proyecto** antes de renombrar.
