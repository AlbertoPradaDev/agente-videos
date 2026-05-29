"""
Cliente de Google Sheets para el pipeline de videos.
Maneja lectura y escritura en las tres hojas del proyecto.
"""

import sys
import os
from pathlib import Path
from datetime import datetime
from typing import Optional

import gspread
from google.oauth2.service_account import Credentials
from loguru import logger

sys.path.insert(0, str(Path(__file__).parent.parent))
import config

# Permisos necesarios para Sheets + Drive
SCOPES = [
    "https://www.googleapis.com/auth/spreadsheets",
    "https://www.googleapis.com/auth/drive",
]


def get_client() -> gspread.Client:
    """Crea y retorna un cliente autenticado de gspread."""
    creds = Credentials.from_service_account_file(
        config.GOOGLE_CREDENTIALS_PATH,
        scopes=SCOPES,
    )
    return gspread.authorize(creds)


def get_spreadsheet() -> gspread.Spreadsheet:
    """Retorna el spreadsheet principal del proyecto."""
    client = get_client()
    return client.open_by_key(config.SPREADSHEET_ID)


# ============================================================
# HOJA: temas
# ============================================================

def obtener_siguiente_tema() -> Optional[dict]:
    """
    Lee la hoja 'temas' y retorna el primer tema con estado 'pendiente'.
    Retorna None si no hay temas disponibles.
    """
    try:
        sheet = get_spreadsheet().worksheet(config.SHEET_TEMAS)
        registros = sheet.get_all_records()

        for i, fila in enumerate(registros, start=2):  # start=2 porque fila 1 es header
            if str(fila.get("estado", "")).strip().lower() == "pendiente":
                fila["_fila"] = i  # guardamos el número de fila para actualizar
                return fila

        logger.warning("No hay temas con estado 'pendiente' en Google Sheets")
        return None

    except Exception as e:
        logger.error(f"Error leyendo hoja 'temas': {e}")
        raise


def actualizar_estado_tema(fila: int, estado: str, notas: str = ""):
    """
    Actualiza el estado de un tema en la hoja 'temas'.
    estado: 'pendiente' | 'en_proceso' | 'completado' | 'error'
    """
    try:
        sheet = get_spreadsheet().worksheet(config.SHEET_TEMAS)
        # Columna E = estado (ajusta si tu hoja tiene diferente orden)
        col_estado = _get_col_index(sheet, "estado")
        col_notas  = _get_col_index(sheet, "notas")

        sheet.update_cell(fila, col_estado, estado)
        if notas:
            sheet.update_cell(fila, col_notas, notas)

        logger.info(f"Tema fila {fila} → estado: {estado}")

    except Exception as e:
        logger.error(f"Error actualizando estado tema: {e}")
        raise


# ============================================================
# HOJA: produccion
# ============================================================

def guardar_produccion(id_video: int, datos: dict):
    """
    Guarda o actualiza los datos de producción de un video.
    Si ya existe una fila con ese id, la actualiza. Si no, la crea.
    datos: diccionario con los campos de la hoja produccion
    """
    try:
        sheet = get_spreadsheet().worksheet(config.SHEET_PRODUCCION)
        registros = sheet.get_all_records()

        fila_existente = None
        for i, fila in enumerate(registros, start=2):
            if str(fila.get("id")) == str(id_video):
                fila_existente = i
                break

        datos["id"] = id_video
        datos.setdefault("fecha_creacion", datetime.now().isoformat())

        if fila_existente:
            _actualizar_fila(sheet, fila_existente, datos)
            logger.info(f"Video {id_video}: datos de producción actualizados")
        else:
            headers = sheet.row_values(1)
            nueva_fila = [str(datos.get(h, "")) for h in headers]
            sheet.append_row(nueva_fila, value_input_option="USER_ENTERED")
            logger.info(f"Video {id_video}: nueva fila de producción creada")

    except Exception as e:
        logger.error(f"Error guardando producción video {id_video}: {e}")
        raise


def obtener_produccion(id_video: int) -> Optional[dict]:
    """Lee los datos de producción de un video por su ID."""
    try:
        sheet = get_spreadsheet().worksheet(config.SHEET_PRODUCCION)
        registros = sheet.get_all_records()
        for fila in registros:
            if str(fila.get("id")) == str(id_video):
                return fila
        return None
    except Exception as e:
        logger.error(f"Error leyendo producción video {id_video}: {e}")
        raise


# ============================================================
# HOJA: cortos
# ============================================================

def guardar_corto(id_video_padre: int, numero_corto: int, datos: dict):
    """
    Guarda los datos de un corto en la hoja 'cortos'.
    numero_corto: 1, 2 o 3
    """
    try:
        sheet = get_spreadsheet().worksheet(config.SHEET_CORTOS)
        registros = sheet.get_all_records()

        fila_existente = None
        for i, fila in enumerate(registros, start=2):
            if (str(fila.get("id_video_padre")) == str(id_video_padre) and
                    str(fila.get("numero_corto")) == str(numero_corto)):
                fila_existente = i
                break

        datos["id_video_padre"] = id_video_padre
        datos["numero_corto"] = numero_corto
        datos.setdefault("estado", "pendiente")

        if fila_existente:
            _actualizar_fila(sheet, fila_existente, datos)
        else:
            headers = sheet.row_values(1)
            nueva_fila = [str(datos.get(h, "")) for h in headers]
            sheet.append_row(nueva_fila, value_input_option="USER_ENTERED")

        logger.info(f"Corto {numero_corto} del video {id_video_padre} guardado")

    except Exception as e:
        logger.error(f"Error guardando corto: {e}")
        raise


def obtener_cortos(id_video_padre: int) -> list[dict]:
    """Retorna los 3 cortos de un video padre."""
    try:
        sheet = get_spreadsheet().worksheet(config.SHEET_CORTOS)
        registros = sheet.get_all_records()
        return [f for f in registros if str(f.get("id_video_padre")) == str(id_video_padre)]
    except Exception as e:
        logger.error(f"Error leyendo cortos del video {id_video_padre}: {e}")
        raise


# ============================================================
# UTILIDADES INTERNAS
# ============================================================

def _get_col_index(sheet: gspread.Worksheet, nombre_col: str) -> int:
    """Retorna el índice (1-based) de una columna por su nombre en el header."""
    headers = sheet.row_values(1)
    try:
        return headers.index(nombre_col) + 1
    except ValueError:
        raise ValueError(f"Columna '{nombre_col}' no encontrada en la hoja '{sheet.title}'")


def _actualizar_fila(sheet: gspread.Worksheet, numero_fila: int, datos: dict):
    """Actualiza campos específicos de una fila existente."""
    headers = sheet.row_values(1)
    for col_nombre, valor in datos.items():
        if col_nombre in headers:
            col_idx = headers.index(col_nombre) + 1
            sheet.update_cell(numero_fila, col_idx, str(valor))


# ============================================================
# TEST DE CONEXIÓN
# ============================================================

def test_conexion():
    """Verifica que la conexión a Google Sheets funciona correctamente."""
    try:
        sheet = get_spreadsheet()
        hojas = [ws.title for ws in sheet.worksheets()]
        logger.info(f"✓ Conexión exitosa. Hojas encontradas: {hojas}")

        requeridas = [config.SHEET_TEMAS, config.SHEET_PRODUCCION, config.SHEET_CORTOS]
        faltantes = [h for h in requeridas if h not in hojas]
        if faltantes:
            logger.warning(f"⚠️  Hojas faltantes en el Spreadsheet: {faltantes}")
            logger.warning("Créalas manualmente con los nombres exactos: temas, produccion, cortos")
        else:
            logger.info("✓ Las tres hojas requeridas existen")

        return True
    except Exception as e:
        logger.error(f"✗ Error de conexión: {e}")
        return False


if __name__ == "__main__":
    # Ejecuta: python sheets/sheets_client.py
    from loguru import logger
    logger.add(str(config.PATHS["logs"] / "pipeline.log"), rotation="10 MB")
    test_conexion()
