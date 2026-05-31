"""
Módulo 6: Animación de imágenes con Kling AI via Replicate.

Toma las 5 imágenes más épicas del video y las convierte en clips
de 5 segundos con movimiento real (capas ondeando, llamas, humo, etc.)

Los clips animados se integran en el video largo y también se usan
para los Reels de Instagram.

Uso directo para testear:
  python modules/animacion.py --id 1
"""

import os
import sys
import time
import base64
import argparse
import urllib.request
from pathlib import Path

import replicate
from loguru import logger

sys.path.insert(0, str(Path(__file__).parent.parent))
import config
from sheets.sheets_client import obtener_produccion


# ============================================================
# PROMPTS DE MOVIMIENTO POR TIPO DE ESCENA
# ============================================================

# Palabras clave en el prompt visual → tipo de movimiento a aplicar
MOVIMIENTO_POR_ESCENA = {
    "battle":    "soldiers charging forward, weapons clashing, dramatic slow motion, dust rising",
    "fire":      "flames flickering intensely, embers floating upward, smoke swirling",
    "warrior":   "cloak flowing dramatically in wind, warrior breathing heavily, muscles tense",
    "army":      "army marching forward, banners waving in wind, ground shaking",
    "emperor":   "royal robe flowing, crowd bowing slowly, torches flickering",
    "city":      "clouds moving slowly overhead, flags waving, people moving in distance",
    "sea":       "waves crashing against rocks, ship sails billowing in wind",
    "storm":     "lightning flashing in distance, dark clouds rolling, rain falling",
    "default":   "subtle camera movement, atmospheric particles floating, dramatic lighting shift",
}

def detectar_tipo_movimiento(prompt_visual: str) -> str:
    """Detecta el tipo de movimiento apropiado basado en el prompt visual."""
    prompt_lower = prompt_visual.lower()
    for keyword, movimiento in MOVIMIENTO_POR_ESCENA.items():
        if keyword in prompt_lower:
            return movimiento
    return MOVIMIENTO_POR_ESCENA["default"]


# ============================================================
# SELECCIÓN DE IMÁGENES A ANIMAR
# ============================================================

def seleccionar_imagenes_a_animar(carpeta_imagenes: Path, n: int = 5) -> list[Path]:
    """
    Selecciona las N imágenes más estratégicas para animar:
    - Primera imagen (apertura)
    - Dos del desarrollo (índices medios)
    - Una del clímax (cerca del final)
    - Última imagen (cierre)
    """
    todas = sorted(carpeta_imagenes.rglob("img_*.jpg"))
    if not todas:
        return []

    total = len(todas)
    if total <= n:
        return todas

    # Índices estratégicos
    indices = [
        0,                          # Apertura
        total // 4,                 # Primer desarrollo
        total // 2,                 # Segundo desarrollo
        int(total * 0.75),          # Clímax
        total - 1,                  # Cierre
    ]
    # Quitar duplicados y limitar a N
    indices = list(dict.fromkeys(indices))[:n]
    return [todas[i] for i in indices]


# ============================================================
# ANIMACIÓN DE UNA IMAGEN
# ============================================================

def animar_imagen(ruta_imagen: Path, prompt_movimiento: str, ruta_salida: Path) -> bool:
    """
    Anima una imagen estática usando Kling AI via Replicate.
    Genera un clip de 5 segundos con movimiento real.
    Retorna True si tuvo éxito.
    """
    if ruta_salida.exists():
        logger.info(f"  Clip ya existe, saltando: {ruta_salida.name}")
        return True

    try:
        # Convertir imagen a base64 para enviar a MiniMax
        with open(ruta_imagen, "rb") as f:
            imagen_b64 = base64.b64encode(f.read()).decode("utf-8")
        imagen_data = f"data:image/jpeg;base64,{imagen_b64}"

        logger.info(f"  Animando: {ruta_imagen.name}")

        # Crear predicción asíncrona para evitar timeouts de conexión
        prediction = replicate.predictions.create(
            model=config.KLING_MODEL,
            input={
                "first_frame_image": imagen_data,
                "prompt":            "subtle natural movement, gentle camera drift, cinematic atmospheric motion, animate existing elements only, no new characters or objects",
                "prompt_optimizer":  False,
            }
        )
        logger.info(f"  Predicción creada: {prediction.id} — esperando resultado...")

        # Polling hasta que termine (máx 20 minutos)
        MAX_ESPERA = 1200  # segundos
        INTERVALO  = 10    # segundos entre checks
        tiempo_total = 0

        while prediction.status not in ("succeeded", "failed", "canceled"):
            time.sleep(INTERVALO)
            tiempo_total += INTERVALO
            prediction.reload()
            logger.info(f"  Estado: {prediction.status} ({tiempo_total}s)")
            if tiempo_total >= MAX_ESPERA:
                logger.error("  Timeout: la predicción tardó más de 20 minutos")
                return False

        if prediction.status != "succeeded":
            logger.error(f"  Predicción fallida: {prediction.error}")
            return False

        # Obtener URL del video generado
        output = prediction.output
        if hasattr(output, 'url'):
            url = output.url
        elif isinstance(output, str):
            url = output
        elif isinstance(output, list):
            url = output[0]
        else:
            url = str(output)

        if not url:
            logger.error("  MiniMax no devolvió URL de video")
            return False

        # Descargar el clip
        urllib.request.urlretrieve(url, str(ruta_salida))
        tamanio_mb = ruta_salida.stat().st_size / (1024 * 1024)
        logger.info(f"  ✓ Clip animado: {ruta_salida.name} ({tamanio_mb:.1f} MB)")
        return True

    except Exception as e:
        logger.error(f"  ✗ Error animando imagen: {e}")
        return False


# ============================================================
# ORQUESTADOR
# ============================================================

def generar_animaciones(id_video: int):
    """
    Selecciona las 5 imágenes más épicas y las anima con Kling.
    Guarda los clips en output/clips/video_{id}/
    """
    carpeta_imagenes = config.PATHS["imagenes"] / f"video_{id_video}"
    carpeta_clips = config.PATHS["clips"] / f"video_{id_video}"
    carpeta_clips.mkdir(parents=True, exist_ok=True)

    # Seleccionar imágenes a animar
    imagenes = seleccionar_imagenes_a_animar(carpeta_imagenes, config.IMAGENES_A_ANIMAR)
    if not imagenes:
        logger.error(f"No hay imágenes en {carpeta_imagenes}")
        return []

    logger.info(f"Animando {len(imagenes)} imágenes del video {id_video}...")

    clips_generados = []
    for idx, imagen in enumerate(imagenes):
        # Nombre del clip basado en la imagen original
        nombre_clip = f"animado_{imagen.parent.name}_{imagen.stem}.mp4"
        ruta_clip = carpeta_clips / nombre_clip

        # Detectar movimiento apropiado (usamos el nombre de la imagen como referencia)
        prompt_movimiento = MOVIMIENTO_POR_ESCENA["warrior"]  # Default épico

        exito = animar_imagen(imagen, prompt_movimiento, ruta_clip)
        if exito:
            clips_generados.append({
                "imagen_original": str(imagen),
                "clip_animado": str(ruta_clip),
            })

        # Kling tarda ~30-60 segundos por clip
        if idx < len(imagenes) - 1:
            logger.info("  Esperando 5s antes del siguiente clip...")
            time.sleep(5)

    logger.success(f"✅ Módulo 6 completado — {len(clips_generados)}/5 clips animados")
    return clips_generados


# ============================================================
# EJECUCIÓN DIRECTA
# ============================================================

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--id", type=int, default=1, help="ID del video a procesar")
    args = parser.parse_args()

    logger.add(str(config.PATHS["logs"] / "pipeline.log"), rotation="10 MB")
    config.crear_directorios()

    os.environ["REPLICATE_API_TOKEN"] = config.REPLICATE_API_TOKEN
    generar_animaciones(args.id)
