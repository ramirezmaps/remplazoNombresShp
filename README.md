# Herramientas de Automatización para ArcGIS Pro

Repositorio con herramientas tipo **Python Toolbox (`.pyt`)** y scripts independientes para ArcGIS Pro diseñados para automatizar tareas repetitivas sobre shapefiles y layouts en proyectos `.aprx`.

---

## 📦 Herramientas Incluidas en este Repositorio

### 1. `ReemplazarElementosLayout.pyt` — Modificación y Exportación Masiva de Layouts (¡ACTUALIZADO!)
Permite buscar y reemplazar de forma masiva elementos dentro de los layouts y/o **exportar todos los layouts a una carpeta**:
* **Textos:** Busca y reemplaza palabras, frases, fechas, autores, códigos de proyecto o títulos en cuadros de texto, membretes y notas.
* **Imágenes / Logos:** Sustituye la ruta del archivo de imagen para actualizar logos de empresas, clientes o encabezados gráficos.
* **Marcos de Mapa (Map Frames):** Reasigna el mapa asociado al marco de mapa.
* **Exportación Masiva:** Exporta todos los layouts (o filtrados) a una carpeta en formato **PDF**, **JPEG**, **PNG** o **TIFF** con resolución (DPI) personalizable.

**Modos de uso:**
- **Solo Exportar:** Selecciona la acción *"Ninguno (Solo Exportar)"*, elige la carpeta de salida, el formato (ej. PDF) y los DPI para generar los archivos de todos los layouts de una sola vez.
- **Reemplazar y Exportar:** Puedes reemplazar textos o logos y al mismo tiempo indicar la carpeta de exportación para obtener los layouts ya actualizados y listos para entrega.
- **Alcance flexible:** Aplica a `* (Todos los Layouts)` del proyecto o permite seleccionar uno específico desde un desplegable.
- **Proyecto activo o externo:** Funciona por defecto sobre el proyecto abierto (`"CURRENT"`) o seleccionando un archivo `.aprx` en disco.

---

### 2. `ReemplazarTextoShp.pyt` — Reemplazo de texto en nombres de Shapefiles
Busca un patrón o fragmento de texto en los nombres de shapefiles de una carpeta y lo reemplaza por otro valor definido por el usuario (o lo elimina).

* **Opciones:**
  - Renombrar en la misma carpeta original (*in-place*).
  - Guardar copias renombradas en una nueva carpeta de destino (conservando los originales).
  - Opción de sobrescribir archivos si el nombre destino ya existiera.
  - Renombra automáticamente todos los componentes asociados: `.shp`, `.shx`, `.dbf`, `.prj`, `.cpg`, `.sbn`, `.sbx`, `.shp.xml`, `.qpj`, etc.

---

### 3. `RenombrarShapefiles.pyt` — Renombrado masivo mediante tabla Excel
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
   - `ReemplazarElementosLayout.pyt`
   - `ReemplazarTextoShp.pyt`
   - `RenombrarShapefiles.pyt`
5. Haz doble clic sobre la herramienta para abrir el panel de Geoprocesamiento, configura los parámetros y pulsa **Run** (*Ejecutar*).

---

## 💻 Ejecución desde Consola o Terminal (Python)

Todos los toolboxes cuentan con sus scripts complementarios ejecutables desde consola:
- `reemplazar_elementos_layout.py`
- `reemplazar_texto_shp.py`
- `renombrar_shp.py`
