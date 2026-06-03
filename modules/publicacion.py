"""
Módulo 8: Publicación automática en YouTube.

Sube el video largo y los 3 cortos al canal de Archivos Oscuros.
- Video largo: programado para las 18:30 hora de Madrid
- Cortos: programados con 2 horas de diferencia entre sí

Uso directo para testear:
  python modules/publicacion.py --id 1 --tipo largo
  python modules/publicacion.py --id 1 --tipo cortos
  python modules/publicacion.py --id 1 --tipo todo
"""

import sys
import json
import argparse
import socket
import time
from pathlib import Path
from datetime import datetime, timedelta

from loguru import logger

sys.path.insert(0, str(Path(__file__).parent.parent))
import config
from sheets.sheets_client import obtener_produccion, obtener_cortos, guardar_produccion, guardar_corto

# Google / YouTube
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from google.auth.transport.requests import Request
from googleapiclient.discovery import build
from googleapiclient.http import MediaFileUpload
import pickle
import os

SCOPES = ["https://www.googleapis.com/auth/youtube.upload"]
MAX_REINTENTOS = 5


def _subir_con_reintentos(request, descripcion: str) -> dict:
    """Ejecuta una subida resumable con reintentos automáticos ante timeouts y errores de red."""
    from googleapiclient.errors import HttpError

    respuesta = None
    reintentos = 0
    while respuesta is None:
        try:
            status, respuesta = request.next_chunk()
            if status:
                progreso = int(status.progress() * 100)
                logger.info(f"  Subiendo {descripcion}... {progreso}%")
            reintentos = 0  # reset al tener éxito
        except (TimeoutError, socket.timeout, OSError, ConnectionResetError) as e:
            reintentos += 1
            if reintentos > MAX_REINTENTOS:
                raise RuntimeError(f"Timeout tras {MAX_REINTENTOS} reintentos: {e}")
            espera = min(60, 5 * reintentos)
            logger.warning(f"  Timeout, reintentando en {espera}s ({reintentos}/{MAX_REINTENTOS})...")
            time.sleep(espera)
        except HttpError as e:
            if e.resp.status in (500, 502, 503, 504):
                reintentos += 1
                if reintentos > MAX_REINTENTOS:
                    raise
                espera = min(60, 5 * reintentos)
                logger.warning(f"  Error HTTP {e.resp.status}, reintentando en {espera}s...")
                time.sleep(espera)
            else:
                raise
    return respuesta
TOKEN_FILE = Path(__file__).parent.parent / "youtube_token.pickle"
CREDENTIALS_FILE = Path(__file__).parent.parent / "youtube_credentials.json"


# ============================================================
# AUTENTICACIÓN
# ============================================================

def obtener_servicio_youtube():
    """
    Autentica con YouTube Data API v3 usando OAuth 2.0.
    La primera vez abre el navegador para autorizar.
    Las siguientes veces usa el token guardado.
    """
    creds = None

    # Cargar token guardado si existe
    if TOKEN_FILE.exists():
        with open(TOKEN_FILE, "rb") as f:
            creds = pickle.load(f)

    # Si no hay credenciales válidas, autenticar
    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
            logger.info("Token de YouTube renovado")
        else:
            if not CREDENTIALS_FILE.exists():
                raise FileNotFoundError(
                    f"No se encontró {CREDENTIALS_FILE}\n"
                    "Descarga las credenciales OAuth desde Google Cloud Console."
                )
            flow = InstalledAppFlow.from_client_secrets_file(str(CREDENTIALS_FILE), SCOPES)
            creds = flow.run_local_server(port=0)
            logger.info("✓ Autenticación con YouTube completada")

        # Guardar token para la próxima vez
        with open(TOKEN_FILE, "wb") as f:
            pickle.dump(creds, f)

    return build("youtube", "v3", credentials=creds)


# ============================================================
# CALCULAR HORA DE PUBLICACIÓN
# ============================================================

def calcular_fecha_publicacion(dias_offset: int = 0, hora: str = None) -> str:
    """
    Calcula la fecha/hora de publicación en formato ISO 8601 UTC.
    Por defecto publica hoy a las 18:30 hora de Madrid (17:30 UTC en verano).
    """
    from zoneinfo import ZoneInfo

    tz_madrid = ZoneInfo("Europe/Madrid")
    hora_pub = hora or config.PUBLISH_TIME  # "18:30"
    h, m = map(int, hora_pub.split(":"))

    ahora = datetime.now(tz_madrid)
    fecha_pub = ahora.replace(hour=h, minute=m, second=0, microsecond=0)
    fecha_pub += timedelta(days=dias_offset)

    # Si la hora ya pasó hoy, publicar mañana
    if fecha_pub <= ahora and dias_offset == 0:
        fecha_pub += timedelta(days=1)

    # Convertir a UTC y formato ISO
    fecha_utc = fecha_pub.astimezone(ZoneInfo("UTC"))
    return fecha_utc.strftime("%Y-%m-%dT%H:%M:%S.000Z")


# ============================================================
# SUBIR VIDEO LARGO
# ============================================================

def subir_video_largo(id_video: int, youtube) -> str:
    """
    Sube el video largo al canal y lo programa para las 18:30.
    Retorna el ID del video en YouTube.
    """
    produccion = obtener_produccion(id_video)
    if not produccion:
        raise ValueError(f"Video {id_video} no encontrado en Google Sheets")

    ruta_video = Path(produccion.get("ruta_video_final", ""))
    if not ruta_video.exists():
        raise FileNotFoundError(f"Video no encontrado: {ruta_video}")

    titulo    = produccion.get("titulo_yt", f"Video {id_video}")
    descripcion = produccion.get("descripcion_yt", "")
    tags_str  = produccion.get("tags_yt", "")
    tags      = [t.strip() for t in tags_str.split(",") if t.strip()]

    fecha_pub = calcular_fecha_publicacion(dias_offset=0)
    logger.info(f"Subiendo video largo: {titulo}")
    logger.info(f"Programado para: {fecha_pub}")

    body = {
        "snippet": {
            "title":       titulo,
            "description": descripcion,
            "tags":        tags,
            "categoryId":  str(config.YOUTUBE_CATEGORY_ID),
            "defaultLanguage": "es",
        },
        "status": {
            "privacyStatus":          "private",   # privado hasta la hora programada
            "publishAt":              fecha_pub,
            "selfDeclaredMadeForKids": False,
        }
    }

    media = MediaFileUpload(
        str(ruta_video),
        mimetype="video/mp4",
        resumable=True,
        chunksize=10 * 1024 * 1024  # 10MB por chunk
    )

    request = youtube.videos().insert(
        part="snippet,status",
        body=body,
        media_body=media
    )

    response = _subir_con_reintentos(request, titulo[:40])
    video_id = response["id"]
    url = f"https://www.youtube.com/watch?v={video_id}"
    logger.success(f"✅ Video largo subido: {url}")

    # Guardar en Google Sheets
    guardar_produccion(id_video, {
        "youtube_id":        video_id,
        "youtube_url":       url,
        "estado_produccion": "publicado",
    })

    return video_id


# ============================================================
# SUBIR CORTOS
# ============================================================

def subir_cortos(id_video: int, youtube):
    """
    Sube los 3 cortos al canal programados con 2 horas de diferencia.
    """
    cortos = obtener_cortos(id_video)
    if not cortos:
        logger.warning("No hay cortos para subir")
        return

    for corto in cortos:
        numero = int(corto.get("numero_corto", 0))
        ruta_video = config.PATHS["cortos"] / f"video_{id_video}_corto_{numero}.mp4"

        if not ruta_video.exists():
            logger.warning(f"Corto {numero} no encontrado: {ruta_video}")
            continue

        titulo      = corto.get("titulo_corto", f"Corto {numero}")
        descripcion = corto.get("descripcion_corto", "")
        hashtags    = corto.get("hashtags", "")
        descripcion_completa = f"{descripcion}\n\n{hashtags}"

        # Cortos: publicar con 2h de diferencia (corto 1 a las 12:00, 2 a las 14:00, 3 a las 16:00)
        horas_base = [12, 14, 16]
        hora_pub_str = f"{horas_base[(numero-1) % 3]:02d}:00"
        fecha_pub = calcular_fecha_publicacion(dias_offset=0, hora=hora_pub_str)

        logger.info(f"Subiendo corto {numero}: {titulo}")
        logger.info(f"Programado para: {fecha_pub}")

        body = {
            "snippet": {
                "title":       titulo[:100],
                "description": descripcion_completa,
                "categoryId":  str(config.YOUTUBE_CATEGORY_ID),
                "defaultLanguage": "es",
            },
            "status": {
                "privacyStatus":          "private",
                "publishAt":              fecha_pub,
                "selfDeclaredMadeForKids": False,
            }
        }

        media = MediaFileUpload(
            str(ruta_video),
            mimetype="video/mp4",
            resumable=True,
            chunksize=10 * 1024 * 1024
        )

        request = youtube.videos().insert(
            part="snippet,status",
            body=body,
            media_body=media
        )

        response = _subir_con_reintentos(request, f"corto {numero}")
        video_id = response["id"]
        url = f"https://www.youtube.com/shorts/{video_id}"
        logger.success(f"✅ Corto {numero} subido: {url}")

        guardar_corto(id_video, numero, {
            "youtube_url_corto": url,
            "estado":            "publicado",
        })


# ============================================================
# ORQUESTADOR
# ============================================================

def publicar_video(id_video: int, tipo: str = "todo"):
    """
    tipo: 'largo' | 'cortos' | 'todo'
    """
    logger.info(f"Autenticando con YouTube...")
    youtube = obtener_servicio_youtube()

    if tipo in ("largo", "todo"):
        subir_video_largo(id_video, youtube)

    if tipo in ("cortos", "todo"):
        subir_cortos(id_video, youtube)

    logger.success(f"✅ Módulo 8 completado para video {id_video}")


# ============================================================
# EJECUCIÓN DIRECTA
# ============================================================

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--id",   type=int, default=1, help="ID del video")
    parser.add_argument("--tipo", type=str, default="todo", help="largo | cortos | todo")
    args = parser.parse_args()

    logger.add(str(config.PATHS["logs"] / "pipeline.log"), rotation="10 MB")
    config.crear_directorios()

    publicar_video(args.id, args.tipo)
