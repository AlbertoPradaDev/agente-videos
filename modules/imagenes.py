"""
Módulo 5: Generación de imágenes con FLUX via Replicate.

Para cada capítulo del guión genera 7 imágenes épicas históricas
usando los prompts visuales creados por Claude en el Módulo 2.

Los cortos reutilizan las mejores imágenes del video largo — sin costo extra.

Uso directo para testear:
  python modules/imagenes.py --id 1
"""

import json
import sys
import time
import argparse
import urllib.request
from pathlib import Path

import replicate
from loguru import logger

sys.path.insert(0, str(Path(__file__).parent.parent))
import config
from sheets.sheets_client import obtener_produccion, guardar_produccion


# ============================================================
# CONFIGURACIÓN
# ============================================================

IMAGENES_POR_CAPITULO = config.IMAGES_PER_CHAPTER  # 7

# Sin variaciones fijas — cada capítulo tiene sus propios 7 prompts únicos generados por Claude


# ============================================================
# GENERACIÓN DE UNA IMAGEN
# ============================================================

def generar_imagen(prompt: str, ruta_salida: Path) -> bool:
    """
    Genera una imagen con FLUX via Replicate y la guarda en ruta_salida.
    Retorna True si tuvo éxito.
    """
    prompt_completo = f"{prompt}, {config.FLUX_STYLE_SUFFIX}"

    try:
        output = replicate.run(
            config.FLUX_MODEL,
            input={
                "prompt": prompt_completo,
                "width": config.IMAGE_WIDTH,
                "height": config.IMAGE_HEIGHT,
                "num_inference_steps": 28,
                "guidance": 3.5,
                "output_format": "jpg",
                "output_quality": 90,
            }
        )

        # Replicate devuelve una URL o un objeto FileOutput
        if hasattr(output, 'url'):
            url = output.url
        elif isinstance(output, str):
            url = output
        elif isinstance(output, list):
            url = output[0] if output else None
        else:
            url = str(output)

        if not url:
            logger.error("FLUX no devolvió URL de imagen")
            return False

        # Descargar la imagen
        urllib.request.urlretrieve(url, str(ruta_salida))
        logger.info(f"  ✓ {ruta_salida.name}")
        return True

    except Exception as e:
        logger.error(f"  ✗ Error generando imagen: {e}")
        return False


# ============================================================
# GENERACIÓN POR CAPÍTULO
# ============================================================

def generar_imagenes_capitulo(
    id_video: int,
    numero_capitulo: int,
    nombre_capitulo: str,
    prompts: list[str],
) -> list[Path]:
    """
    Genera una imagen por cada prompt del capítulo.
    Cada prompt describe una escena completamente diferente.
    Retorna lista de rutas de imágenes generadas.
    """
    carpeta = config.PATHS["imagenes"] / f"video_{id_video}" / f"capitulo_{numero_capitulo:02d}"
    carpeta.mkdir(parents=True, exist_ok=True)

    rutas_generadas = []

    for idx, prompt in enumerate(prompts):
        ruta = carpeta / f"img_{idx + 1:02d}.jpg"

        if ruta.exists():
            logger.info(f"  Imagen {idx + 1} ya existe, saltando")
            rutas_generadas.append(ruta)
            continue

        exito = generar_imagen(prompt, ruta)
        if exito:
            rutas_generadas.append(ruta)
        else:
            logger.info("  Esperando 15s por rate limit...")
            time.sleep(15)
            exito = generar_imagen(prompt, ruta)
            if exito:
                rutas_generadas.append(ruta)

        time.sleep(10)  # 10s entre imágenes = máximo 6 por minuto

    logger.info(f"Capítulo {numero_capitulo} '{nombre_capitulo}': {len(rutas_generadas)}/{len(prompts)} imágenes")
    return rutas_generadas


# ============================================================
# SELECCIÓN DE THUMBNAIL
# ============================================================

def seleccionar_thumbnail(id_video: int, todas_las_imagenes: list[Path]) -> Path:
    """
    Selecciona la primera imagen del capítulo más dramático como thumbnail.
    Por ahora toma la imagen del clímax (penúltimo capítulo).
    """
    carpeta_thumb = config.PATHS["thumbnails"]
    carpeta_thumb.mkdir(parents=True, exist_ok=True)
    ruta_thumb = carpeta_thumb / f"video_{id_video}_thumb.jpg"

    if todas_las_imagenes and not ruta_thumb.exists():
        # Toma la primera imagen del penúltimo capítulo (suele ser el clímax)
        import shutil
        indice_climax = max(0, len(todas_las_imagenes) // 2)
        shutil.copy(todas_las_imagenes[indice_climax], ruta_thumb)
        logger.info(f"✓ Thumbnail seleccionado: {ruta_thumb.name}")

    return ruta_thumb


# ============================================================
# ORQUESTADOR
# ============================================================

def generar_imagenes(id_video: int):
    """
    Genera todas las imágenes del video usando los prompts visuales
    guardados en Google Sheets por el módulo de guión.
    """
    produccion = obtener_produccion(id_video)
    if not produccion:
        raise ValueError(f"Video {id_video} no encontrado en Google Sheets")

    prompts_json = produccion.get("prompts_visuales", "")
    if not prompts_json:
        raise ValueError(f"No hay prompts visuales para el video {id_video}. Ejecuta primero el módulo de guión.")

    prompts = json.loads(prompts_json)
    logger.info(f"Generando imágenes para {len(prompts)} capítulos...")

    todas_las_imagenes = []

    for capitulo in prompts:
        numero = capitulo.get("capitulo", capitulo.get("numero", 0))
        nombre = capitulo.get("nombre", f"Capítulo {numero}")

        # Soporta tanto lista de prompts (nuevo) como prompt único (legado)
        prompts_cap = capitulo.get("prompts_visuales", [])
        if not prompts_cap:
            prompt_unico = capitulo.get("prompt_visual", capitulo.get("prompt", ""))
            if prompt_unico:
                prompts_cap = [prompt_unico]

        if not prompts_cap:
            logger.warning(f"Capítulo {numero} sin prompts visuales, saltando")
            continue

        logger.info(f"Capítulo {numero}: {nombre} ({len(prompts_cap)} escenas)")
        rutas = generar_imagenes_capitulo(id_video, numero, nombre, prompts_cap)
        todas_las_imagenes.extend(rutas)

    # Seleccionar thumbnail
    ruta_thumb = seleccionar_thumbnail(id_video, todas_las_imagenes)

    # Guardar en Google Sheets
    guardar_produccion(id_video, {
        "ruta_thumbnail":    str(ruta_thumb),
        "estado_produccion": "imagenes",
    })

    logger.success(f"✅ Módulo 5 completado — {len(todas_las_imagenes)} imágenes generadas")
    return todas_las_imagenes


# ============================================================
# EJECUCIÓN DIRECTA
# ============================================================

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--id", type=int, default=1, help="ID del video a procesar")
    args = parser.parse_args()

    logger.add(str(config.PATHS["logs"] / "pipeline.log"), rotation="10 MB")
    config.crear_directorios()

    # Configurar Replicate
    import os
    os.environ["REPLICATE_API_TOKEN"] = config.REPLICATE_API_TOKEN

    generar_imagenes(args.id)
