"""
Configuración centralizada del agente de videos históricos.
Todas las constantes y rutas del proyecto vienen de aquí.
"""

import os
from pathlib import Path
from dotenv import load_dotenv

load_dotenv()

# ============================================================
# RUTAS BASE
# ============================================================
BASE_DIR = Path(__file__).parent
OUTPUT_DIR = BASE_DIR / "output"
LOGS_DIR = BASE_DIR / "logs"

PATHS = {
    "guiones":          OUTPUT_DIR / "guiones",
    "audio":            OUTPUT_DIR / "audio",
    "imagenes":         OUTPUT_DIR / "imagenes",
    "clips":            OUTPUT_DIR / "clips",
    "videos_largos":    OUTPUT_DIR / "videos_largos",
    "cortos":           OUTPUT_DIR / "cortos",
    "thumbnails":       OUTPUT_DIR / "thumbnails",
    "listos":           OUTPUT_DIR / "listos_para_subir",
    "musica":           OUTPUT_DIR / "musica",
    "logs":             LOGS_DIR,
}

def crear_directorios():
    """Crea todos los directorios necesarios si no existen."""
    for nombre, ruta in PATHS.items():
        ruta.mkdir(parents=True, exist_ok=True)
    print("✓ Estructura de carpetas lista")

# ============================================================
# APIs
# ============================================================
ANTHROPIC_API_KEY       = os.getenv("ANTHROPIC_API_KEY", "")
ELEVENLABS_API_KEY      = os.getenv("ELEVENLABS_API_KEY", "")
ELEVENLABS_VOICE_ES     = os.getenv("ELEVENLABS_VOICE_ES", "")
ELEVENLABS_VOICE_EN     = os.getenv("ELEVENLABS_VOICE_EN", "")
REPLICATE_API_TOKEN     = os.getenv("REPLICATE_API_TOKEN", "")
HAILUO_API_KEY          = os.getenv("HAILUO_API_KEY", "")
TELEGRAM_BOT_TOKEN      = os.getenv("TELEGRAM_BOT_TOKEN", "")
TELEGRAM_CHAT_ID        = os.getenv("TELEGRAM_CHAT_ID", "")

# ============================================================
# GOOGLE
# ============================================================
GOOGLE_CREDENTIALS_PATH     = os.getenv("GOOGLE_SHEETS_CREDENTIALS_PATH", "credentials.json")
SPREADSHEET_ID              = os.getenv("GOOGLE_SHEETS_SPREADSHEET_ID", "")
YOUTUBE_CLIENT_ID           = os.getenv("YOUTUBE_CLIENT_ID", "")
YOUTUBE_CLIENT_SECRET       = os.getenv("YOUTUBE_CLIENT_SECRET", "")
YOUTUBE_REFRESH_TOKEN       = os.getenv("YOUTUBE_REFRESH_TOKEN", "")

# Nombres de hojas en Google Sheets
SHEET_TEMAS         = "temas"
SHEET_PRODUCCION    = "produccion"
SHEET_CORTOS        = "cortos"

# ============================================================
# CANAL Y PUBLICACIÓN
# ============================================================
CHANNEL_NAME            = os.getenv("CHANNEL_NAME", "")
YOUTUBE_CATEGORY_ID     = int(os.getenv("YOUTUBE_CATEGORY_ID", "27"))
PUBLISH_TIME            = os.getenv("PUBLISH_TIME", "18:30")
PUBLISH_TIMEZONE        = os.getenv("PUBLISH_TIMEZONE", "Europe/Madrid")
VIDEOS_PER_WEEK         = int(os.getenv("VIDEOS_PER_WEEK", "3"))

ARTLIST_MUSIC_FOLDER    = Path(os.getenv("ARTLIST_MUSIC_FOLDER", str(OUTPUT_DIR / "musica")))

# ============================================================
# MODELOS DE IA
# ============================================================
CLAUDE_MODEL = "claude-sonnet-4-5"   # Cambia a claude-opus-4-5 si quieres máxima calidad
KLING_MODEL  = "minimax/video-01-live"   # Modelo de animación imagen→video (MiniMax Live2D)
IMAGENES_A_ANIMAR = 5                # Imágenes animadas por video (apertura, desarrollo x2, clímax, cierre)

# ============================================================
# PARÁMETROS DE GENERACIÓN
# ============================================================

# Guión
SCRIPT_LANGUAGE_PRIMARY     = "es-LA"   # Español Latino
SCRIPT_LANGUAGE_SECONDARY   = "en"      # Inglés
TARGET_DURATION_MIN         = 20        # minutos mínimos video largo
TARGET_DURATION_MAX         = 23        # minutos máximos video largo
SHORT_DURATION_MIN          = 30        # segundos mínimos corto
SHORT_DURATION_MAX          = 60        # segundos máximos corto
SHORTS_PER_VIDEO            = 3

# Voz Azure TTS
AZURE_VOICE_ES = "es-MX-JorgeNeural"       # Voz masculina profunda ES-LA
AZURE_VOICE_EN = "en-US-GuyNeural"         # Voz masculina dramática EN
AZURE_SPEAKING_RATE = "-10%"               # Ligeramente más lento que normal

# Imágenes
IMAGES_PER_CHAPTER  = 7        # promedio imágenes por capítulo
IMAGE_WIDTH         = 1344
IMAGE_HEIGHT        = 768
FLUX_MODEL          = "black-forest-labs/flux-1.1-pro"

# Video largo
VIDEO_WIDTH         = 1920
VIDEO_HEIGHT        = 1080
VIDEO_FPS           = 24
VIDEO_BITRATE       = "8000k"

# Video corto (vertical)
SHORT_WIDTH         = 1080
SHORT_HEIGHT        = 1920

# Música
MUSIC_VOLUME_BASE   = 0.25     # 25% del volumen total
MUSIC_VOLUME_CLIMAX = 0.30     # 30% en momentos épicos
MUSIC_VOLUME_SOFT   = 0.18     # 18% en momentos reflexivos

# ============================================================
# PROMPTS BASE PARA CLAUDE
# ============================================================

# Estilo visual para prompts FLUX (añadido a cada prompt de imagen)
FLUX_STYLE_SUFFIX = (
    "cinematic hyperrealistic photography, dramatic chiaroscuro lighting, "
    "historical epic, battle-hardened warriors, fierce expressions, muscles tense, "
    "swords shields spears axes armor leather iron, dust smoke fire, "
    "epic color palette (deep golds, steel grays, midnight blues, amber torchlight), "
    "low angle shot conveying power and dominance, extreme detail on faces and armor, "
    "film grain, anamorphic lens flare, shallow depth of field, "
    "no text, no watermarks, no modern elements, no empty landscapes, "
    "always include human figures warriors soldiers kings, "
    "Hollywood epic movie still, 300 movie style, Gladiator movie style, "
    "Braveheart style, Kingdom of Heaven style, 8K, photorealistic"
)

# ============================================================
# VALIDACIÓN DE CONFIGURACIÓN
# ============================================================
REQUIRED_VARS = {
    "ANTHROPIC_API_KEY":            ANTHROPIC_API_KEY,
    "GOOGLE_SHEETS_SPREADSHEET_ID": SPREADSHEET_ID,
}

OPTIONAL_VARS = {
    "ELEVENLABS_API_KEY":   ELEVENLABS_API_KEY,
    "REPLICATE_API_TOKEN":  REPLICATE_API_TOKEN,
    "CHANNEL_NAME":         CHANNEL_NAME,
}

def validar_config(modulo: str = "base") -> bool:
    """
    Verifica que las variables requeridas estén configuradas.
    modulo: 'base' | 'guion' | 'voz' | 'imagenes' | 'publicacion' | 'notificacion'
    """
    requeridas_por_modulo = {
        "base":        ["ANTHROPIC_API_KEY", "GOOGLE_SHEETS_SPREADSHEET_ID"],
        "guion":       ["ANTHROPIC_API_KEY", "GOOGLE_SHEETS_SPREADSHEET_ID"],
        "voz":         ["ELEVENLABS_API_KEY"],
        "imagenes":    ["REPLICATE_API_TOKEN"],
        "publicacion": ["YOUTUBE_CLIENT_ID", "YOUTUBE_CLIENT_SECRET"],
    }

    vars_a_verificar = requeridas_por_modulo.get(modulo, list(REQUIRED_VARS.keys()))
    todos_los_valores = {**REQUIRED_VARS, **OPTIONAL_VARS,
                         "ELEVENLABS_API_KEY": ELEVENLABS_API_KEY,
                         "REPLICATE_API_TOKEN": REPLICATE_API_TOKEN,
                         "YOUTUBE_CLIENT_ID": YOUTUBE_CLIENT_ID,
                         "YOUTUBE_CLIENT_SECRET": YOUTUBE_CLIENT_SECRET}

    faltantes = [k for k in vars_a_verificar if not todos_los_valores.get(k)]
    if faltantes:
        print(f"⚠️  Variables faltantes para módulo '{modulo}':")
        for var in faltantes:
            print(f"   → {var} (añádela a tu .env)")
        return False
    return True
