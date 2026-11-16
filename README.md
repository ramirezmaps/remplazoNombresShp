# Herramientas de Renombrado Masivo de Shapefiles para ArcGIS Pro

Repositorio con herramientas tipo **Python Toolbox (`.pyt`)** y scripts independientes para ArcGIS Pro diseñados para renombrar shapefiles de forma masiva e íntegra (renombrando automáticamente `.shp`, `.shx`, `.dbf`, `.prj`, `.cpg`, `.sbn`, `.sbx`, `.shp.xml`, `.qpj`, etc.).

---

## 🌟 Opciones Principales Disponibles

En ambas herramientas puedes elegir:
1. **Renombrar en la misma carpeta original** (*in-place*) dejando la carpeta de destino vacía.
2. **Guardar en una nueva ruta de salida:** Si seleccionas una carpeta de destino, los archivos originales **se conservan intactos** y se generan copias con los nuevos nombres en la carpeta de destino.
3. **Reemplazar / Sobrescribir archivos existentes:** Casilla para decidir si se sobrescriben archivos cuando el nombre de destino ya exista.

---

## 📦 Herramientas Incluidas

### 1. `ReemplazarTextoShp.pyt` — Reemplazo directo de cadena de texto
Permite buscar un patrón o fragmento de texto en los nombres de los shapefiles de una carpeta y reemplazarlo por otro valor definido por el usuario (o eliminarlo).

* **Ejemplo práctico:**
  - Carpeta contiene: `SITIO_N1_EL_SAUCE_rios.shp`, `SITIO_N1_EL_SAUCE_caminos.shp`
  - **Texto a buscar:** `SITIO_N1_EL_SAUCE`
  - **Texto de reemplazo:** `SITIO_N2_LOS_ALMENDROS`
  - **Resultado:** `SITIO_N2_LOS_ALMENDROS_rios.shp`, `SITIO_N2_LOS_ALMENDROS_caminos.shp` (con todos sus componentes `.dbf`, `.prj`, etc.).

* **Parámetros en ArcGIS Pro:**
  - **Carpeta de Origen con Shapefiles:** Carpeta que contiene las capas.
  - **Texto a Buscar en el Nombre:** Cadena o prefijo a sustituir.
  - **Texto de Reemplazo:** Nuevo texto (si se deja vacío, se elimina el fragmento buscado).
  - **Carpeta de Destino (Opcional):** Si se especifica, guarda copias renombradas en esta carpeta dejando el origen intacto. Si se deja vacía, renombra en la misma carpeta.
  - **Reemplazar / Sobrescribir archivos existentes:** Casilla para habilitar la sobrescritura.
  - **Diferenciar mayúsculas de minúsculas:** Opcional (por defecto ignora mayúsculas/minúsculas).
  - **Incluir Subcarpetas:** Opcional (permite procesar recursivamente).

---

### 2. `RenombrarShapefiles.pyt` — Renombrado mediante tabla Excel
Permite pasarle un archivo Excel (`.xlsx` o `.xls`) con una tabla de equivalencias con los nombres antiguos y nuevos.

* **Parámetros en ArcGIS Pro:**
  - **Carpeta de Origen con Shapefiles:** Carpeta que contiene los shapefiles.
  - **Archivo Excel con Equivalencias:** Archivo `.xlsx` o `.xls` con los pares de nombres.
  - **Carpeta de Destino (Opcional):** Si se especifica, guarda las copias renombradas allí.
  - **Reemplazar / Sobrescribir archivos existentes:** Casilla para habilitar la sobrescritura.
  - **Hoja de Excel (Opcional):** Desplegable con las pestañas del libro.
  - **Columna Nombre Antiguo / Nuevo (Opcional):** Detección automática por nombres comunes (`nombre_antiguo`, `antiguo`, etc.).

---

## 🚀 Cómo usar las herramientas en ArcGIS Pro

1. Abre tu proyecto en **ArcGIS Pro**.
2. Abre el panel **Catalog** (*Catálogo*).
3. Haz clic derecho sobre la carpeta **Toolboxes** (*Cajas de herramientas*) -> **Add Toolbox** (*Agregar caja de herramientas*).
4. Elige la herramienta que necesites:
   - `ReemplazarTextoShp.pyt`
   - `RenombrarShapefiles.pyt`
5. Haz doble clic sobre la herramienta para abrir el panel de Geoprocesamiento, configura los parámetros y haz clic en **Run** (*Ejecutar*).

Al terminar, se actualiza automáticamente el Catálogo de ArcGIS Pro (`arcpy.RefreshCatalog`).

---

## 💻 Ejecución desde Consola o Terminal (Python puro)

Ambas herramientas cuentan con su script equivalente ejecutable desde la terminal:

### Para reemplazo de texto:
```bash
# Modo interactivo:
python reemplazar_texto_shp.py

# Modo con argumentos (renombrar en el lugar):
python reemplazar_texto_shp.py --carpeta "C:\MisCapas" --buscar "SITIO_N1_EL_SAUCE" --reemplazo "SITIO_N2_LOS_ALMENDROS"

# Modo guardando en una nueva carpeta con sobrescritura:
python reemplazar_texto_shp.py --carpeta "C:\MisCapas" --buscar "SITIO_N1_EL_SAUCE" --reemplazo "SITIO_N2_LOS_ALMENDROS" --destino "C:\CapasNuevas" --sobrescribir
```

### Para renombrado por Excel:
```bash
# Modo interactivo:
python renombrar_shp.py

# Guardando en una nueva ruta:
python renombrar_shp.py --carpeta "C:\MisCapas" --excel "C:\MisCapas\plantilla_ejemplo.xlsx" --destino "C:\CapasNuevas" --sobrescribir
```

---

## 🧩 Archivos que se procesan automáticamente

Un **Shapefile** está compuesto por múltiples archivos que comparten el mismo nombre base. Ambas herramientas procesan de forma simultánea todos los componentes existentes:

- `.shp`: Geometría vectorial.
- `.shx`: Índice de geometrías.
- `.dbf`: Tabla de atributos dBase.
- `.prj`: Proyección cartográfica y sistema de coordenadas.
- `.cpg`: Juego de caracteres / codificación.
- `.sbn` y `.sbx`: Índices espaciales de ArcGIS.
- `.shp.xml`: Metadatos ArcGIS.
- `.qpj`: Proyección auxiliar QGIS.
- `.cst`, `.fbn`, `.fbx`, `.atx`, etc.
