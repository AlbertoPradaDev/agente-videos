"""
Orquestador principal del agente de videos históricos.
Ejecuta el pipeline completo para un video:
  Tema → Guión → Voz → Imágenes → Edición → Publicación → Notificación

Uso:
  python main.py                  # procesa el siguiente tema pendiente
  python main.py --id 5           # procesa el tema con id=5 (reanuda si estaba a medias)
  python main.py --solo-guion     # solo genera el guión (útil para testear)
  python main.py --test           # verifica configuración y conexiones
"""

import argparse
import sys
from pathlib import Path
from loguru import logger

import config
from config import crear_directorios, validar_config
from sheets.sheets_client import (
    obtener_siguiente_tema,
    actualizar_estado_tema,
    obtener_produccion,
    test_conexion,
)

# Configurar logging
config.PATHS["logs"].mkdir(parents=True, exist_ok=True)
logger.remove()
logger.add(sys.stdout, format="<green>{time:HH:mm:ss}</green> | <level>{level}</level> | {message}")
logger.add(
    str(config.PATHS["logs"] / "pipeline.log"),
    rotation="10 MB",
    retention="30 days",
    format="{time:YYYY-MM-DD HH:mm:ss} | {level} | {message}",
)


def run_pipeline(id_video: int = None, solo_guion: bool = False):
    """
    Ejecuta el pipeline completo o reanuda desde el estado guardado.
    """
    crear_directorios()

    # 1. Obtener tema
    if id_video:
        produccion_existente = obtener_produccion(id_video)
        if not produccion_existente:
            logger.error(f"No se encontró el video con id={id_video} en la hoja produccion")
            return
        tema = {"id": id_video, "tema": produccion_existente.get("titulo_yt", f"Video {id_video}")}
        estado_actual = produccion_existente.get("estado_produccion", "")
        logger.info(f"Reanudando video {id_video} desde estado: '{estado_actual}'")
    else:
        tema = obtener_siguiente_tema()
        if not tema:
            logger.warning("No hay temas pendientes. Añade temas a la hoja 'temas' en Google Sheets.")
            return
        id_video = tema["id"]
        estado_actual = ""
        actualizar_estado_tema(tema["_fila"], "en_proceso")
        logger.info(f"▶ Iniciando pipeline para: {tema['tema']} (ID: {id_video})")

    try:
        # 2. Guión (Módulos 2 y 3)
        if estado_actual in ("", "guion") or not estado_actual:
            if not validar_config("guion"):
                raise ValueError("Faltan variables de entorno para el módulo guión")
            logger.info("📝 [Módulo 2+3] Generando guión y guiones cortos...")
            from modules.guion import generar_guion_completo
            generar_guion_completo(id_video, tema)
            if solo_guion:
                logger.success("✓ Guión generado. Pipeline pausado (--solo-guion)")
                return

        # 3. Voz (Módulo 4)
        if estado_actual in ("", "guion", "voz") and not solo_guion:
            if not validar_config("voz"):
                logger.warning("⚠️  Azure TTS no configurado — saltando módulo voz")
            else:
                logger.info("🎙️  [Módulo 4] Generando audio TTS...")
                from modules.voz import generar_voces
                generar_voces(id_video)

        # 4. Imágenes (Módulo 5)
        if estado_actual in ("", "guion", "voz", "imagenes") and not solo_guion:
            if not validar_config("imagenes"):
                logger.warning("⚠️  Replicate no configurado — saltando módulo imágenes")
            else:
                logger.info("🖼️  [Módulo 5] Generando imágenes con FLUX...")
                from modules.imagenes import generar_imagenes
                generar_imagenes(id_video)

        # 5. Edición (Módulos 7A y 7B) — se añadirán en fases posteriores
        # 6. Publicación (Módulo 8)
        # 7. Notificación (Módulo 9)

        logger.success(f"✅ Pipeline completado para video {id_video}")

    except Exception as e:
        logger.error(f"✗ Error en pipeline video {id_video}: {e}")
        if tema.get("_fila"):
            actualizar_estado_tema(tema["_fila"], "error", str(e))
        raise


def run_test():
    """Verifica que todas las conexiones y configuraciones estén operativas."""
    logger.info("🔍 Verificando configuración del sistema...")
    crear_directorios()

    errores = []

    # Google Sheets
    logger.info("  → Probando conexión Google Sheets...")
    if not test_conexion():
        errores.append("Google Sheets: conexión fallida")

    # Variables base
    if not config.ANTHROPIC_API_KEY:
        errores.append("ANTHROPIC_API_KEY no configurada")

    if not config.SPREADSHEET_ID:
        errores.append("GOOGLE_SHEETS_SPREADSHEET_ID no configurado")

    # Opcional: Azure
    if not config.AZURE_SPEECH_KEY:
        logger.warning("  ⚠️  AZURE_SPEECH_KEY no configurada (módulo voz desactivado)")

    # Opcional: Replicate
    if not config.REPLICATE_API_TOKEN:
        logger.warning("  ⚠️  REPLICATE_API_TOKEN no configurado (módulo imágenes desactivado)")

    if errores:
        logger.error("✗ Configuración incompleta:")
        for e in errores:
            logger.error(f"   → {e}")
    else:
        logger.success("✅ Sistema listo para producción")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Agente de videos históricos épicos")
    parser.add_argument("--id",         type=int,   help="ID del video a procesar (para reanudar)")
    parser.add_argument("--solo-guion", action="store_true", help="Solo genera el guión")
    parser.add_argument("--test",       action="store_true", help="Verifica configuración")
    args = parser.parse_args()

    if args.test:
        run_test()
    else:
        run_pipeline(id_video=args.id, solo_guion=args.solo_guion)
