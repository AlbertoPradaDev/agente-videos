# Configuración Google Sheets API

Sigue estos pasos en orden. Toma ~15 minutos la primera vez.

## Paso 1 — Crear proyecto en Google Cloud

1. Ve a https://console.cloud.google.com/
2. Arriba a la izquierda, clic en el selector de proyecto → "Nuevo proyecto"
3. Nombre: `agente-videos` → Crear
4. Asegúrate de que ese proyecto esté seleccionado

## Paso 2 — Activar APIs necesarias

En el menú lateral: **APIs y servicios → Biblioteca**

Busca y activa estas dos:
- **Google Sheets API** → Habilitar
- **Google Drive API** → Habilitar

## Paso 3 — Crear cuenta de servicio (Service Account)

1. Menú lateral: **APIs y servicios → Credenciales**
2. Clic en "+ Crear credenciales" → "Cuenta de servicio"
3. Nombre: `agente-videos-bot` → Crear y continuar
4. Rol: **Editor** → Continuar → Listo

## Paso 4 — Descargar credentials.json

1. En la lista de cuentas de servicio, clic en la que acabas de crear
2. Pestaña **Claves** → "Agregar clave" → "Crear nueva clave"
3. Formato: **JSON** → Crear
4. Se descarga un archivo JSON → renómbralo `credentials.json`
5. Muévelo a la raíz del proyecto (junto a main.py)

⚠️  Este archivo NO debe subirse a GitHub (ya está en .gitignore)

## Paso 5 — Crear el Google Sheet

1. Ve a https://sheets.google.com → crear nueva hoja
2. Nómbrala: `Agente Videos Pipeline`
3. Copia el ID de la URL:
   `https://docs.google.com/spreadsheets/d/` **ESTE_ES_EL_ID** `/edit`
4. Pégalo en tu `.env`:
   ```
   GOOGLE_SHEETS_SPREADSHEET_ID=ESTE_ES_EL_ID
   ```

## Paso 6 — Compartir el Sheet con la cuenta de servicio

1. Abre el archivo credentials.json que descargaste
2. Busca el campo `client_email` — tiene el formato:
   `agente-videos-bot@agente-videos.iam.gserviceaccount.com`
3. En tu Google Sheet: clic en "Compartir" (arriba derecha)
4. Pega ese email → rol **Editor** → Enviar

## Paso 7 — Crear las tres hojas con los headers correctos

En tu Google Sheet, crea tres pestañas con exactamente estos nombres y columnas:

### Hoja: `temas`
| id | tema | categoria | estado | fecha_programada | prioridad | notas |

### Hoja: `produccion`
| id | guion_es | guion_en | prompts_visuales | titulo_yt | descripcion_yt | tags_yt | ruta_audio_es | ruta_audio_en | ruta_video_final | ruta_thumbnail | url_youtube | estado_produccion | duracion_segundos | fecha_creacion | fecha_publicacion |

### Hoja: `cortos`
| id_video_padre | numero_corto | guion_corto | ruta_video_corto | titulo_corto | descripcion_corto | hashtags | estado | plataformas_subido |

## Paso 8 — Añadir tu primer tema de prueba

En la hoja `temas`, añade una fila con:
- id: `1`
- tema: `La caída del Imperio Romano`
- categoria: `romanos`
- estado: `pendiente`
- prioridad: `alta`

## Paso 9 — Verificar conexión

```bash
python main.py --test
```

Deberías ver: `✅ Sistema listo para producción`

---

## Solución de problemas comunes

**Error: "File not found: credentials.json"**
→ Mueve el archivo credentials.json a la raíz del proyecto

**Error: "The caller does not have permission"**
→ No compartiste el Sheet con el email de la cuenta de servicio (Paso 6)

**Error: "Worksheet not found"**
→ Los nombres de las hojas deben ser exactamente: `temas`, `produccion`, `cortos`
