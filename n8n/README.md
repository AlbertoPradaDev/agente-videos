# Automatización con n8n (local)

Orquesta el pipeline de videos como un **flujo visual de 5 etapas**. Cada etapa
es un nodo que ejecuta una parte de tu pipeline Python (mismo código, mismas
APIs, mismos resultados), así ves las conexiones y en qué paso va:

```
[Trigger] → Guion → Voz → Imagenes → Edicion → Publicacion
            Claude   ElevenLabs  FLUX   FFmpeg+Whisper  YouTube
```

El ID del video se resuelve en la etapa **Guion** (toma el siguiente tema
`pendiente` de Google Sheets) y se pasa automáticamente a las etapas siguientes.

---

## 1. Arrancar n8n

Usa el script incluido (habilita que los nodos Code lancen el pipeline):

```bash
./n8n/start_n8n.sh
```

Abre **http://localhost:5678**. Deja esa terminal abierta.

> ¿Por qué el script y no `n8n start` a secas? n8n bloquea el módulo
> `child_process` por defecto. El script exporta
> `NODE_FUNCTION_ALLOW_BUILTIN=child_process` para que las etapas puedan
> ejecutar `run_pipeline.sh`.

## 2. Importar el workflow

1. Crea un workflow nuevo (botón **Create workflow**).
2. Dentro del editor, menú **⋮ (arriba a la derecha) → Import from File**.
   - Si no aparece "Import from File", arrastra el archivo `.json` directamente
     sobre el lienzo del editor.
3. Elige `n8n/agente_videos_workflow.json`.
4. Verás 7 nodos: 2 disparadores (**Ejecutar ahora**, **Lun/Mie/Vie 09:00**) y
   las 5 etapas encadenadas.
5. **Save**.

## 3. Probar

- Clic en **Execute workflow**.
- Cada nodo se ilumina al ejecutarse; si una etapa falla, ese nodo queda en rojo
  con el log del error. El log completo también se guarda en `logs/n8n_run_*.log`.
- Cada etapa tarda lo suyo (Claude, ElevenLabs, FLUX, FFmpeg+Whisper, subida);
  una corrida completa son ~10-15 min. Es normal que n8n quede "pensando".

## 4. Activar el programado

- Toggle **Active** (arriba a la derecha).
- Corre **lunes, miércoles y viernes a las 09:00**. Cada corrida toma el
  siguiente tema `pendiente` y produce+programa: largo día+1 13:00, cortos
  escalonados (día+1 19:30, día+2 13:00, día+3 13:00).

### Cambiar el horario

Abre el nodo **Lun/Mie/Vie 09:00** → edita el cron `0 9 * * 1,3,5`
(min hora * * días; 1=lun … 5=vie).

---

## Cómo funciona cada nodo

Cada etapa llama a `run_pipeline.sh` con `--solo <etapa>`:

| Nodo | Comando | Hace |
|------|---------|------|
| Guion | `run_pipeline.sh --solo guion` | Siguiente tema pendiente → guion + cortos. Emite `VIDEO_ID`. |
| Voz | `run_pipeline.sh --id N --solo voz` | TTS ElevenLabs |
| Imagenes | `run_pipeline.sh --id N --solo imagenes` | FLUX (Replicate) |
| Edicion | `run_pipeline.sh --id N --solo edicion` | FFmpeg + subtítulos (Whisper) |
| Publicacion | `run_pipeline.sh --id N --solo publicacion` | Sube/programa en YouTube |

`--solo` ejecuta **una sola** etapa (a diferencia de `--desde`, que corre de una
etapa hasta el final). Reanudar una etapa suelta a mano:

```bash
./run_pipeline.sh --id 6 --solo publicacion
```

---

## Notas

- **PATH:** `run_pipeline.sh` fija el PATH con ffmpeg (Homebrew) y el venv 3.11.
- **Sin temas pendientes:** la etapa Guion falla con "No se pudo resolver
  VIDEO_ID". Añade filas `pendiente` a la hoja `temas`.
- **OAuth de YouTube:** la etapa Publicacion necesita `youtube_credentials.json`
  + `youtube_token.pickle`. Sin ellos falla solo esa etapa (las demás corren).

## Arranque automático (opcional)

Para que n8n se levante al iniciar sesión en el Mac, crea un LaunchAgent en
`~/Library/LaunchAgents/com.n8n.plist` que ejecute `n8n/start_n8n.sh`.
Pídemelo y te lo genero.
