# Herramientas de Automatización para ArcGIS Pro

Repositorio con herramientas tipo **Python Toolbox (`.pyt`)** y scripts independientes para ArcGIS Pro diseñados para automatizar tareas repetitivas sobre shapefiles, layouts `.aprx` y exportaciones KMZ.

---

## 📦 Herramientas Incluidas en este Repositorio

### 1. `ExportarKmzLimpio.pyt` — Exportar Capas y Group Layers a KMZ sin Hipervínculos (¡ACTUALIZADO!)
Exporta capas vectoriales individuales, selecciones múltiples o **Group Layers** completos a archivos `.kmz` limpios para Google Earth y plataformas de validación (como SEA/SEIA):

* **Conserva la tabla de atributos sin usar la pestaña Descripción:** Extrae automáticamente todos los campos y valores desde la tabla HTML generada por ArcGIS Pro y los migra al estándar oficial **KML 2.2 (`<Schema>` + `<ExtendedData><SchemaData><SimpleData>`)**. Así, al hacer clic en una entidad en Google Earth se muestra la tabla de atributos limpia y al abrir el KMZ en QGIS/ArcGIS se conservan todas las columnas, mientras que la pestaña **Descripción** en las propiedades de Google Earth queda **100% vacía** (sin HTML ni `xmlns:fo`).
* **Sin hipervínculos ni enlaces externos:** Elimina todas las etiquetas `<description>`, `<Snippet>`, `<BalloonStyle>`, `<a href>`, URLs (`http://`, `https://`, `www.`, `file://`), `<NetworkLink>`, `<atom:link>` y referencias web externas, conservando intactas las geometrías vectoriales (`NO_COMPOSITE`), nombres, simbología e íconos locales embebidos dentro del KMZ.
* **Manejo flexible de Group Layers:**
  - Por defecto exporta un Group Layer como un único `.kmz` respetando su estructura de carpetas interna.
  - Con la casilla *"Desglosar Group Layers"*, genera archivos `.kmz` individuales por cada subcapa (con opción de exportar solo las visibles).
* **Ajuste al terreno:** Activa `CLAMPED_TO_GROUND` por defecto (opcionalmente configurable a `ABSOLUTE`).
* **Herramienta extra incluida:** También incorpora *"Limpiar Archivos KMZ Existentes"* dentro del mismo `.pyt` para limpiar archivos `.kmz` que ya tengas generados en disco.

---

### 2. `ReemplazarElementosLayout.pyt` — Modificación y Exportación Masiva de Layouts
Permite buscar y reemplazar de forma masiva elementos dentro de los layouts y/o **exportar todos los layouts a una carpeta**:
* **Textos:** Busca y reemplaza palabras, frases, fechas, autores, códigos de proyecto o títulos en cuadros de texto, membretes y notas.
* **Imágenes / Logos:** Sustituye la ruta del archivo de imagen para actualizar logos de empresas, clientes o encabezados gráficos.
* **Marcos de Mapa (Map Frames):** Reasigna el mapa asociado al marco de mapa.
* **Exportación Masiva:** Exporta todos los layouts (o filtrados) a una carpeta en formato **PDF**, **JPEG**, **PNG** o **TIFF** con resolución (DPI) personalizable y `clip_to_elements = True` activado por defecto.

---

### 3. `ReemplazarTextoShp.pyt` — Reemplazo de texto en nombres de Shapefiles
Busca un patrón o fragmento de texto en los nombres de shapefiles de una carpeta y lo reemplaza por otro valor definido por el usuario (o lo elimina).

* **Opciones:**
  - Renombrar en la misma carpeta original (*in-place*) o guardar copias en una nueva carpeta de destino.
  - Sobrescribir archivos existentes si es necesario.
  - Renombra automáticamente todos los componentes asociados: `.shp`, `.shx`, `.dbf`, `.prj`, `.cpg`, `.sbn`, `.sbx`, `.shp.xml`, `.qpj`, etc.

---

### 4. `RenombrarShapefiles.pyt` — Renombrado masivo mediante tabla Excel
Renombra múltiples shapefiles según una tabla de equivalencias en Excel (`.xlsx` o `.xls`).

* **Opciones:**
  - Detección automática de columnas (`nombre_antiguo` / `nombre_nuevo`).
  - Guardar en el lugar o en una nueva ruta de salida.
  - Sobrescribir archivos existentes si es necesario.

---

## 🚀 Cómo usar las herramientas en ArcGIS Pro

1. Abre tu proyecto en **ArcGIS Pro**.
2. Abre el panel **Catalog** (*Catálogo*).
3. Haz clic derecho sobre la carpeta **Toolboxes** (*Cajas de herramientas*) -> **Add Toolbox** (*Agregar caja de herramientas*).
4. Elige la herramienta deseada:
   - `ExportarKmzLimpio.pyt`
   - `ReemplazarElementosLayout.pyt`
   - `ReemplazarTextoShp.pyt`
   - `RenombrarShapefiles.pyt`
5. Haz doble clic sobre la herramienta para abrir el panel de Geoprocesamiento, configura los parámetros y pulsa **Run** (*Ejecutar*).

---

## 💻 Ejecución desde Consola o Terminal (Python)

Todos los toolboxes cuentan con sus scripts complementarios ejecutables desde consola:
- `exportar_kmz_limpio.py` (incluye modo CLI para limpiar archivos `.kmz` existentes: `python exportar_kmz_limpio.py -i "mi_archivo.kmz"`)
- `reemplazar_elementos_layout.py`
- `reemplazar_texto_shp.py`
- `renombrar_shp.py`
