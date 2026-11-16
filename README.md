# Herramienta de Renombrado Masivo de Shapefiles para ArcGIS Pro

Esta solución te permite renombrar automáticamente múltiples shapefiles (`.shp`) ubicados en una carpeta a partir de una tabla de equivalencias en **Excel** (`.xlsx` o `.xls`).

---

## 📁 Archivos Incluidos

1. **`RenombrarShapefiles.pyt`**: **Toolbox nativo de ArcGIS Pro (Recomendado)**. Solo tienes que agregarlo a tu proyecto y abrir la herramienta con interfaz gráfica interactiva.
2. **`renombrar_shp.py`**: Script de Python independiente. Puede ejecutarse por consola, importarse en otros scripts o usarse como *Script Tool* tradicional en un archivo `.tbx` o `.atbx`.
3. **`plantilla_ejemplo.xlsx`**: Archivo Excel de ejemplo con la estructura recomendada.

---

## 🚀 Método 1: Usar directamente en ArcGIS Pro (Recomendado)

No requiere compilar ni configurar parámetros manualmente:

1. Abre tu proyecto en **ArcGIS Pro**.
2. Ve al panel **Catalog** (*Catálogo*).
3. Despliega la sección **Toolboxes** (*Cajas de herramientas*).
4. Haz clic derecho sobre **Toolboxes** y selecciona **Add Toolbox** (*Agregar caja de herramientas*).
5. Navega y selecciona el archivo `RenombrarShapefiles.pyt`.
6. Al desplegar la caja, verás la herramienta **"Renombrar Shapefiles con Excel"**. Haz doble clic para abrirla.
7. En el panel de Geoprocesamiento:
   - **Carpeta con Shapefiles**: Selecciona la carpeta donde están tus archivos `.shp`.
   - **Archivo Excel con Equivalencias**: Selecciona tu archivo Excel (`.xlsx` o `.xls`).
   - *(Opcional)* **Hoja de Excel**: Se autocompletará con las hojas disponibles en tu Excel.
   - *(Opcional)* **Columna de Nombre Antiguo**: Selecciona la columna del nombre original (se detecta automáticamente si se llama `nombre_antiguo`, `antiguo`, etc.).
   - *(Opcional)* **Columna de Nombre Nuevo**: Selecciona la columna del nombre nuevo (se detecta automáticamente si se llama `nombre_nuevo`, `nuevo`, etc.).
8. Haz clic en **Run** (*Ejecutar*).

Al finalizar, el Catálogo de ArcGIS Pro se actualizará automáticamente mostrando los nuevos nombres.

---

## 💻 Método 2: Ejecución desde Consola o Terminal

Si prefieres ejecutar el proceso sin abrir ArcGIS Pro, puedes usar `renombrar_shp.py`:

### Modo Interactivo:
```bash
python renombrar_shp.py
```
El script te solicitará la ruta de la carpeta y del archivo Excel por pantalla.

### Modo con Parámetros:
```bash
python renombrar_shp.py --carpeta "C:\MisCapas\SHP" --excel "C:\MisCapas\equivalencias.xlsx"
```

Opciones adicionales:
- `--hoja "Hoja1"`: Especificar nombre de la hoja.
- `--col-antiguo "columna_origen"`: Nombre de la columna antigua.
- `--col-nuevo "columna_destino"`: Nombre de la columna nueva.
- `--sobrescribir`: Sobrescribe los archivos si el nombre destino ya existiera.

---

## 📊 Formato del Archivo Excel

El archivo Excel debe tener al menos dos columnas. Por ejemplo:

| nombre_antiguo | nombre_nuevo |
|---|---|
| parcelas_2020 | parcelas_catastro_2024 |
| red_vial_v1 | red_vial_nacional |
| rios_principales.shp | hidrografia_rios.shp |
| zonificacion_urbana | zonas_urbanas_actualizadas |

> [!TIP]
> - Puedes incluir o no la extensión `.shp` en las celdas; la herramienta la detecta y normaliza automáticamente.
> - Si tus columnas tienen otros nombres (ej. `Original` y `Nuevo`), la herramienta intentará detectarlas por coincidencia de palabras clave o por su posición (Columna 1 y Columna 2).

---

## 🧩 ¿Qué archivos se renombran?

Un **Shapefile** no es un único archivo, sino un conjunto de archivos con el mismo nombre base. La herramienta renombra automáticamente todos los componentes que encuentre para cada shapefile:

- `.shp`: Geometría.
- `.shx`: Índice de geometrías.
- `.dbf`: Tabla de atributos dBase.
- `.prj`: Proyección cartográfica y sistema de coordenadas.
- `.cpg`: Codificación de caracteres.
- `.sbn` y `.sbx`: Índices espaciales.
- `.shp.xml`: Metadatos de ArcGIS.
- `.qpj`: Proyección de QGIS (si existiese).
- Y cualquier otro archivo complementario asociado (`.cst`, `.fbn`, etc.).

---

## ⚠️ Consejos y Solución de Problemas

> [!IMPORTANT]
> **Bloqueos de archivos (.sr.lock):**
> Si alguno de los shapefiles está cargado como capa en el mapa activo de ArcGIS Pro, el programa colocará un bloqueo de archivo.
> Si la herramienta reporta que el archivo está bloqueado, **remueve la capa del mapa o cierra el proyecto** antes de ejecutar el renombrado.

> [!NOTE]
> **Archivos no encontrados:**
> Si un nombre listado en el Excel no existe en la carpeta, la herramienta emitirá una advertencia y continuará procesando el resto sin detenerse.
