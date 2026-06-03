"""
Módulo 4: Generación de voz con ElevenLabs.

Convierte los guiones de texto a archivos de audio .mp3.
Genera:
- Audio ES-LA del guión largo
- Audio EN del guión largo (usando voz EN de ElevenLabs)
- 3 audios ES-LA de los guiones cortos

Uso directo para testear:
  python modules/voz.py --id 1
"""

import re
import sys
import time
import argparse
from pathlib import Path

import requests
from loguru import logger

sys.path.insert(0, str(Path(__file__).parent.parent))
import config
from sheets.sheets_client import (
    obtener_produccion,
    obtener_cortos,
    guardar_produccion,
    guardar_corto,
)

ELEVENLABS_API_KEY   = config.ELEVENLABS_API_KEY
VOICE_ES             = config.ELEVENLABS_VOICE_ES
VOICE_EN             = config.ELEVENLABS_VOICE_EN
ELEVENLABS_URL       = "https://api.elevenlabs.io/v1/text-to-speech/{voice_id}"

# ============================================================
# LIMPIEZA DE TEXTO
# ============================================================

def limpiar_texto(texto: str) -> str:
    """
    Elimina caracteres y símbolos que la voz pronunciaría incorrectamente.
    - Elimina markdown: **, *, #, [], ()
    - Elimina guiones largos al inicio de línea
    - Limpia espacios extra
    """
    # Eliminar formato markdown
    texto = re.sub(r'\*{1,2}([^*]+)\*{1,2}', r'\1', texto)  # **negrita** y *cursiva*
    texto = re.sub(r'#{1,6}\s+', '', texto)                   # # Títulos
    texto = re.sub(r'\[([^\]]+)\]\([^\)]+\)', r'\1', texto)  # [texto](url)
    texto = re.sub(r'\[([^\]]+)\]', r'\1', texto)             # [texto]

    # Eliminar caracteres especiales problemáticos
    texto = re.sub(r'[—–]\s*', ' ', texto)                    # guiones largos
    texto = re.sub(r'["""„]', '"', texto)                     # comillas tipográficas
    texto = re.sub(r"[''‛]", "'", texto)                      # apóstrofes tipográficos
    texto = re.sub(r'[•·▶►▸]', '', texto)                    # bullets
    texto = re.sub(r'_{1,2}([^_]+)_{1,2}', r'\1', texto)    # _subrayado_

    # Limpiar espacios y líneas extra
    texto = re.sub(r'\n{3,}', '\n\n', texto)
    texto = re.sub(r' {2,}', ' ', texto)
    texto = texto.strip()

    return texto


# ============================================================
# FUNCIÓN BASE DE SÍNTESIS
# ============================================================

def texto_a_audio(texto: str, ruta_salida: Path, voice_id: str) -> bool:
    """
    Convierte texto a audio usando ElevenLabs.
    Si el texto es muy largo lo divide en bloques y los une con FFmpeg.
    Retorna True si tuvo éxito, False si falló.
    """
    texto = limpiar_texto(texto)

    # ElevenLabs permite hasta ~5000 caracteres por llamada
    LIMITE_CHARS = 4500

    if len(texto) <= LIMITE_CHARS:
        return _sintetizar_bloque(texto, ruta_salida, voice_id)

    # Dividir en bloques respetando párrafos
    logger.info(f"Texto largo ({len(texto)} chars) — dividiendo en bloques...")
    bloques = _dividir_en_bloques(texto, LIMITE_CHARS)

    carpeta_temp = ruta_salida.parent / f"_temp_{ruta_salida.stem}"
    carpeta_temp.mkdir(exist_ok=True)

    rutas_partes = []
    for idx, bloque in enumerate(bloques):
        ruta_parte = carpeta_temp / f"parte_{idx:02d}.mp3"
        logger.info(f"  Generando parte {idx + 1}/{len(bloques)}...")
        if not _sintetizar_bloque(bloque, ruta_parte, voice_id):
            return False
        rutas_partes.append(ruta_parte)
        time.sleep(1)  # Pausa entre llamadas

    # Unir con FFmpeg
    logger.info("Uniendo partes de audio...")
    _unir_audios(rutas_partes, ruta_salida)

    # Limpiar temporales
    for ruta in rutas_partes:
        ruta.unlink(missing_ok=True)
    try:
        carpeta_temp.rmdir()
    except Exception:
        pass

    tamanio_mb = ruta_salida.stat().st_size / (1024 * 1024)
    logger.info(f"✓ Audio final: {ruta_salida.name} ({tamanio_mb:.1f} MB)")
    return True


def _dividir_en_bloques(texto: str, limite: int) -> list[str]:
    """
    Divide el texto en bloques respetando párrafos completos.
    Nunca corta una frase a la mitad.
    """
    parrafos = texto.split('\n\n')
    bloques = []
    bloque_actual = ""

    for parrafo in parrafos:
        if len(bloque_actual) + len(parrafo) + 2 <= limite:
            bloque_actual += ("\n\n" if bloque_actual else "") + parrafo
        else:
            if bloque_actual:
                bloques.append(bloque_actual)
            # Si un solo párrafo es más largo que el límite, lo dividimos por oraciones
            if len(parrafo) > limite:
                oraciones = re.split(r'(?<=[.!?])\s+', parrafo)
                sub_bloque = ""
                for oracion in oraciones:
                    if len(sub_bloque) + len(oracion) + 1 <= limite:
                        sub_bloque += (" " if sub_bloque else "") + oracion
                    else:
                        if sub_bloque:
                            bloques.append(sub_bloque)
                        sub_bloque = oracion
                if sub_bloque:
                    bloque_actual = sub_bloque
                else:
                    bloque_actual = ""
            else:
                bloque_actual = parrafo

    if bloque_actual:
        bloques.append(bloque_actual)

    return bloques


def _sintetizar_bloque(texto: str, ruta_salida: Path, voice_id: str) -> bool:
    """Sintetiza un bloque de texto con ElevenLabs y lo guarda como MP3."""
    url = ELEVENLABS_URL.format(voice_id=voice_id)

    headers = {
        "xi-api-key": ELEVENLABS_API_KEY,
        "Content-Type": "application/json",
    }

    payload = {
        "text": texto,
        "model_id": "eleven_multilingual_v2",
        "voice_settings": {
            "stability": 0.5,
            "similarity_boost": 0.85,
            "style": 0.3,
            "use_speaker_boost": True,
        },
    }

    try:
        respuesta = requests.post(url, json=payload, headers=headers, timeout=120)

        if respuesta.status_code == 200:
            ruta_salida.write_bytes(respuesta.content)
            return True
        else:
            logger.error(f"✗ ElevenLabs error {respuesta.status_code}: {respuesta.text}")
            return False

    except requests.exceptions.Timeout:
        logger.error("✗ Timeout conectando con ElevenLabs")
        return False
    except Exception as e:
        logger.error(f"✗ Error inesperado: {e}")
        return False


def _unir_audios(rutas: list[Path], ruta_salida: Path):
    """Une múltiples MP3 en uno solo usando FFmpeg."""
    import subprocess

    lista_path = ruta_salida.parent / "_lista_concat.txt"
    with open(lista_path, "w") as f:
        for ruta in rutas:
            f.write(f"file '{ruta.absolute()}'\n")

    subprocess.run([
        "ffmpeg", "-y", "-f", "concat", "-safe", "0",
        "-i", str(lista_path),
        "-c", "copy",
        str(ruta_salida)
    ], check=True, capture_output=True)

    lista_path.unlink(missing_ok=True)


# ============================================================
# GENERACIÓN DE AUDIOS
# ============================================================

def generar_audio_largo(id_video: int, produccion: dict) -> str:
    """Genera el audio del guión largo en ES-LA."""
    carpeta = config.PATHS["audio"] / f"video_{id_video}"
    carpeta.mkdir(parents=True, exist_ok=True)

    ruta_es = carpeta / f"video_{id_video}_es.mp3"

    if not ruta_es.exists():
        logger.info("Generando audio ES-LA...")
        texto_es = produccion.get("guion_es", "")
        if not texto_es:
            raise ValueError(f"No hay guión ES para el video {id_video}")
        if not texto_a_audio(texto_es, ruta_es, VOICE_ES):
            raise RuntimeError("Falló generación audio ES")
    else:
        logger.info("Audio ES ya existe, saltando")

    return str(ruta_es)


def generar_audios_cortos(id_video: int, cortos: list) -> list[str]:
    """Genera el audio ES de cada corto."""
    carpeta = config.PATHS["audio"] / f"video_{id_video}" / "cortos"
    carpeta.mkdir(parents=True, exist_ok=True)

    rutas = []
    for corto in cortos:
        numero = corto.get("numero_corto", corto.get("numero", "?"))
        ruta = carpeta / f"corto_{numero}_es.mp3"

        if not ruta.exists():
            logger.info(f"Generando audio corto {numero}...")
            texto = corto.get("guion_corto", "")
            if not texto:
                logger.warning(f"Corto {numero} sin guión, saltando")
                continue
            if texto_a_audio(texto, ruta, VOICE_ES):
                rutas.append(str(ruta))
                guardar_corto(id_video, numero, {"ruta_video_corto": str(ruta)})
        else:
            logger.info(f"Audio corto {numero} ya existe, saltando")
            rutas.append(str(ruta))

        time.sleep(1)

    return rutas


# ============================================================
# ORQUESTADOR
# ============================================================

def generar_voces(id_video: int):
    """Ejecuta la generación completa de voces para un video."""
    produccion = obtener_produccion(id_video)
    if not produccion:
        raise ValueError(f"Video {id_video} no encontrado en Google Sheets")

    try:
        # Audio largo — verificar independientemente
        if produccion.get("ruta_audio_es") and Path(produccion["ruta_audio_es"]).exists():
            logger.info(f"Video {id_video}: audio largo ya existe, saltando")
        else:
            ruta_es = generar_audio_largo(id_video, produccion)
            guardar_produccion(id_video, {
                "ruta_audio_es":     ruta_es,
                "estado_produccion": "voz",
            })

        # Audios cortos — verificar independientemente
        cortos = obtener_cortos(id_video)
        if cortos:
            carpeta_cortos = config.PATHS["audio"] / f"video_{id_video}" / "cortos"
            cortos_pendientes = [
                c for c in cortos
                if not (carpeta_cortos / f"corto_{c.get('numero_corto', c.get('numero', '?'))}_es.mp3").exists()
            ]
            if cortos_pendientes:
                logger.info(f"Generando audios de {len(cortos_pendientes)} cortos pendientes...")
                generar_audios_cortos(id_video, cortos_pendientes)
            else:
                logger.info(f"Video {id_video}: audios de cortos ya existen, saltando")

        logger.success(f"✅ Módulo 4 completado para video {id_video}")

    except Exception as e:
        logger.error(f"Error en módulo voz: {e}")
        raise


# ============================================================
# EJECUCIÓN DIRECTA
# ============================================================

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--id", type=int, default=1, help="ID del video a procesar")
    args = parser.parse_args()

    logger.add(str(config.PATHS["logs"] / "pipeline.log"), rotation="10 MB")
    config.crear_directorios()

    generar_voces(args.id)
