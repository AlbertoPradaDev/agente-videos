"""
Pipeline completo del agente de videos históricos — Archivos Oscuros.

Ejecuta todos los módulos en orden para producir y publicar un video:
  Tema → Guión → Voz → Imágenes → Animación → Edición → Publicación

Uso:
  python main.py                    # procesa el siguiente tema pendiente
  python main.py --id 2             # procesa/reanuda el video con id=2
  python main.py --id 2 --desde voz # reanuda desde un módulo específico
  python main.py --test             # verifica configuración y conexiones

Módulos disponibles para --desde:
  guion | voz | imagenes | animacion | edicion | publicacion
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

# Logging
config.PATHS["logs"].mkdir(parents=True, exist_ok=True)
logger.remove()
logger.add(
    sys.stdout,
    format="<green>{time:HH:mm:ss}</green> | <level>{level: <8}</level> | {message}",
    colorize=True,
)
logger.add(
    str(config.PATHS["logs"] / "pipeline.log"),
    rotation="10 MB",
    retention="30 days",
    format="{time:YYYY-MM-DD HH:mm:ss} | {level} | {message}",
)

# Orden de módulos para saber desde dónde reanudar
ORDEN_MODULOS = ["guion", "voz", "imagenes", "animacion", "edicion", "publicacion"]


def modulo_pendiente(estado_actual: str, modulo: str) -> bool:
    """Retorna True si el módulo todavía no se ha ejecutado."""
    if not estado_actual:
        return True
    try:
        return ORDEN_MODULOS.index(modulo) >= ORDEN_MODULOS.index(estado_actual)
    except ValueError:
        return True


def _emitir_id(id_video: int):
    """Imprime el ID en una línea parseable para que n8n lo capture y lo pase
    entre nodos. Va por stdout directo (no logger) para que sea fácil de extraer."""
    print(f"VIDEO_ID={id_video}", flush=True)


def _ejecutar_etapa(etapa: str, id_video: int, tema: dict):
    """Ejecuta exactamente UNA etapa del pipeline. Es la misma llamada,
    al mismo módulo, con los mismos parámetros que el pipeline completo —
    solo que aislada, para poder orquestarla nodo a nodo en n8n."""
    if etapa == "guion":
        from modules.guion import generar_guion_completo
        generar_guion_completo(id_video, tema)
        logger.success("✓ Guión completado")

    elif etapa == "voz":
        from modules.voz import generar_voces
        generar_voces(id_video)
        logger.success("✓ Voz completada")

    elif etapa == "imagenes":
        if not config.REPLICATE_API_TOKEN:
            logger.warning("⚠️  REPLICATE_API_TOKEN no configurado — saltando imágenes")
            return
        from modules.imagenes import generar_imagenes
        generar_imagenes(id_video)
        logger.success("✓ Imágenes completadas")

    elif etapa == "animacion":
        if not config.REPLICATE_API_TOKEN:
            logger.warning("⚠️  REPLICATE_API_TOKEN no configurado — saltando animación")
            return
        from modules.animacion import generar_animaciones
        generar_animaciones(id_video)
        logger.success("✓ Animaciones completadas")

    elif etapa == "edicion":
        from modules.edicion import ensamblar_video
        ensamblar_video(id_video, tipo="todo")
        logger.success("✓ Edición completada")

    elif etapa == "publicacion":
        from modules.publicacion import publicar_video
        publicar_video(id_video, tipo="todo")
        logger.success("✓ Publicación completada")

    else:
        raise ValueError(f"Etapa desconocida: {etapa}")


def run_solo(etapa: str, id_video: int = None):
    """
    Ejecuta UNA sola etapa del pipeline (para orquestación con n8n).

    - `etapa == "guion"` sin id: toma el siguiente tema pendiente de la hoja
      'temas', lo marca 'en_proceso', genera el guión (crea la fila de
      producción) y emite VIDEO_ID para los nodos siguientes.
    - cualquier otra etapa: requiere --id (la fila de producción ya existe).
    """
    crear_directorios()

    tema = None

    if etapa == "guion" and not id_video:
        tema = obtener_siguiente_tema()
        if not tema:
            logger.warning("No hay temas pendientes en Google Sheets. Añade temas a la hoja 'temas'.")
            return
        id_video = tema["id"]
        actualizar_estado_tema(tema["_fila"], "en_proceso")
        logger.info(f"▶  Etapa '{etapa}' — {tema.get('tema', tema.get('titulo_yt', id_video))} (ID: {id_video})")
    else:
        if not id_video:
            logger.error(f"La etapa '{etapa}' requiere --id (la producción debe existir).")
            raise SystemExit(2)
        produccion = obtener_produccion(id_video)
        if not produccion and etapa != "guion":
            logger.error(f"No se encontró producción del video {id_video}. ¿Corrió ya la etapa 'guion'?")
            raise SystemExit(2)
        tema = {
            "id":        id_video,
            "tema":      (produccion or {}).get("titulo_yt", f"Video {id_video}"),
            "categoria": "historia",
        }
        logger.info(f"▶  Etapa '{etapa}' (ID: {id_video})")

    try:
        _ejecutar_etapa(etapa, id_video, tema)
        logger.success(f"🎉  Etapa '{etapa}' completada para video {id_video}")
    except Exception as e:
        logger.error(f"✗ Error en etapa '{etapa}' video {id_video}: {e}")
        if tema and tema.get("_fila"):
            actualizar_estado_tema(tema["_fila"], "error")
        _emitir_id(id_video)
        raise

    _emitir_id(id_video)


def run_pipeline(id_video: int = None, desde: str = None):
    """
    Ejecuta el pipeline completo o reanuda desde un módulo específico.
    Si no se indica id_video, toma el siguiente tema pendiente de Google Sheets.
    """
    crear_directorios()

    # ── Obtener tema ──────────────────────────────────────────────
    if id_video:
        produccion = obtener_produccion(id_video)
        if not produccion:
            logger.error(f"No se encontró el video {id_video} en Google Sheets")
            return
        tema = {
            "id":       id_video,
            "tema":     produccion.get("titulo_yt", f"Video {id_video}"),
            "categoria": "historia",
        }
        estado_actual = desde or produccion.get("estado_produccion", "")
        logger.info(f"Reanudando video {id_video} | estado: '{estado_actual}'")
    else:
        tema = obtener_siguiente_tema()
        if not tema:
            logger.warning("No hay temas pendientes en Google Sheets. Añade temas a la hoja 'temas'.")
            return
        id_video = tema["id"]
        estado_actual = desde or ""
        actualizar_estado_tema(tema["_fila"], "en_proceso")
        logger.info(f"▶  Iniciando pipeline — {tema['tema']} (ID: {id_video})")

    try:

        # ── MÓDULO 2+3: Guión ─────────────────────────────────────
        if modulo_pendiente(estado_actual, "guion"):
            logger.info("📝  [Módulo 2+3] Generando guión y cortos...")
            from modules.guion import generar_guion_completo
            generar_guion_completo(id_video, tema)
            logger.success("✓ Guión completado")

        # ── MÓDULO 4: Voz ─────────────────────────────────────────
        if modulo_pendiente(estado_actual, "voz"):
            logger.info("🎙️   [Módulo 4] Generando audio con ElevenLabs...")
            from modules.voz import generar_voces
            generar_voces(id_video)
            logger.success("✓ Voz completada")

        # ── MÓDULO 5: Imágenes ────────────────────────────────────
        if modulo_pendiente(estado_actual, "imagenes"):
            if not config.REPLICATE_API_TOKEN:
                logger.warning("⚠️  REPLICATE_API_TOKEN no configurado — saltando imágenes")
            else:
                logger.info("🖼️   [Módulo 5] Generando imágenes con FLUX...")
                from modules.imagenes import generar_imagenes
                generar_imagenes(id_video)
                logger.success("✓ Imágenes completadas")

        # ── MÓDULO 6: Animación ─── DESACTIVADO (alto costo) ─────
        # if modulo_pendiente(estado_actual, "animacion"):
        #     if not config.REPLICATE_API_TOKEN:
        #         logger.warning("⚠️  REPLICATE_API_TOKEN no configurado — saltando animación")
        #     else:
        #         logger.info("🎬  [Módulo 6] Animando imágenes con MiniMax...")
        #         from modules.animacion import generar_animaciones
        #         generar_animaciones(id_video)
        #         logger.success("✓ Animaciones completadas")

        # ── MÓDULO 7: Edición ─────────────────────────────────────
        if modulo_pendiente(estado_actual, "edicion"):
            logger.info("✂️   [Módulo 7] Editando video largo y cortos...")
            from modules.edicion import ensamblar_video
            ensamblar_video(id_video, tipo="todo")
            logger.success("✓ Edición completada")

        # ── MÓDULO 8: Publicación ─────────────────────────────────
        if modulo_pendiente(estado_actual, "publicacion"):
            logger.info("🚀  [Módulo 8] Publicando en YouTube...")
            from modules.publicacion import publicar_video
            publicar_video(id_video, tipo="todo")
            logger.success("✓ Publicación completada")

        logger.success(f"🎉  Pipeline completado para video {id_video}")

    except Exception as e:
        logger.error(f"✗ Error en pipeline video {id_video}: {e}")
        if tema.get("_fila"):
            actualizar_estado_tema(tema["_fila"], "error")
        raise


# ============================================================
# TEST DE CONFIGURACIÓN
# ============================================================

def run_test():
    """Verifica que todas las conexiones y configuraciones estén operativas."""
    logger.info("🔍 Verificando configuración del sistema...")
    crear_directorios()
    errores = []

    logger.info("  → Google Sheets...")
    if test_conexion():
        logger.success("  ✓ Google Sheets conectado")
    else:
        errores.append("Google Sheets: conexión fallida")

    checks = [
        ("ANTHROPIC_API_KEY",   config.ANTHROPIC_API_KEY[:8] if config.ANTHROPIC_API_KEY else "", "Claude API"),
        ("ELEVENLABS_API_KEY",  config.ELEVENLABS_API_KEY,  "ElevenLabs TTS"),
        ("REPLICATE_API_TOKEN", config.REPLICATE_API_TOKEN, "Replicate (FLUX + MiniMax)"),
        ("CHANNEL_NAME",        config.CHANNEL_NAME,        "Nombre del canal"),
    ]

    for var, valor, nombre in checks:
        if valor:
            logger.success(f"  ✓ {nombre}")
        else:
            logger.warning(f"  ⚠️  {nombre} no configurado ({var})")

    if Path("youtube_token.pickle").exists():
        logger.success("  ✓ YouTube autenticado")
    else:
        logger.warning("  ⚠️  YouTube no autenticado — ejecuta primero: python modules/publicacion.py --id 1 --tipo largo")

    if errores:
        logger.error("✗ Errores críticos:")
        for e in errores:
            logger.error(f"   → {e}")
    else:
        logger.success("✅ Sistema listo para producción")


# ============================================================
# ENTRY POINT
# ============================================================

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Agente de videos — Archivos Oscuros")
    parser.add_argument("--id",    type=int, help="ID del video a procesar o reanudar")
    parser.add_argument("--desde", type=str, choices=ORDEN_MODULOS,
                        help="Módulo desde el que reanudar: guion|voz|imagenes|animacion|edicion|publicacion")
    parser.add_argument("--solo", type=str, choices=ORDEN_MODULOS,
                        help="Ejecuta SOLO esa etapa (para orquestación nodo a nodo con n8n)")
    parser.add_argument("--test",  action="store_true", help="Verifica configuración y conexiones")
    args = parser.parse_args()

    if args.test:
        run_test()
    elif args.solo:
        run_solo(etapa=args.solo, id_video=args.id)
    else:
        run_pipeline(id_video=args.id, desde=args.desde)
