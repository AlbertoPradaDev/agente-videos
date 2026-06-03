"""
Módulo 7A: Ensamblaje del video largo (16:9, 1080p)
Módulo 7B: Ensamblaje de los cortos verticales (9:16, 1080p)

Flujo video largo:
  Imágenes + efecto Ken Burns → sincronizar con audio → mezclar música → render final

Flujo cortos:
  Recortar imágenes a vertical → sincronizar con audio corto → subtítulos dinámicos → render

Uso directo para testear:
  python modules/edicion.py --id 1 --tipo largo
  python modules/edicion.py --id 1 --tipo cortos
"""

import json
import os
import random
import subprocess
import sys
import argparse
from pathlib import Path

from loguru import logger

sys.path.insert(0, str(Path(__file__).parent.parent))
import config
from sheets.sheets_client import obtener_produccion, obtener_cortos, guardar_produccion, guardar_corto


# ============================================================
# SELECCIÓN DE MÚSICA
# ============================================================

# Mapa de tipo de música → prefijos de archivo
MUSICA_MAP = {
    "batalla":    ["batalla_climax"],
    "epico":      ["epico_intenso_02", "epico_intenso_03", "epico_medio_01", "epico_medio_02"],
    "dramatico":  ["dramatico_medio_01", "dramatico_lento_01"],
    "reflexivo":  ["reflexivo_lento_01", "reflexivo_lento", "reflexivo_medio_01"],
}

# Qué tipo de música va en cada sección del video
MUSICA_POR_SECCION = {
    "apertura":   "epico",
    "contexto":   "dramatico",
    "desarrollo": "epico",
    "climax":     "batalla",
    "cierre":     "reflexivo",
}



def obtener_track(tipo: str) -> Path:
    """Retorna la ruta de un track de música según el tipo solicitado."""
    carpeta = config.ARTLIST_MUSIC_FOLDER
    candidatos = MUSICA_MAP.get(tipo, MUSICA_MAP["epico"])

    for nombre in candidatos:
        ruta = carpeta / f"{nombre}.mp3"
        if ruta.exists():
            return ruta

    # Si no encuentra el tipo exacto, usa cualquier track disponible
    tracks = list(carpeta.glob("*.mp3"))
    if tracks:
        return random.choice(tracks)

    raise FileNotFoundError(f"No hay tracks de música en {carpeta}")


# ============================================================
# UTILIDADES FFMPEG
# ============================================================

def run_ffmpeg(args: list, descripcion: str = ""):
    """Ejecuta un comando FFmpeg y loguea el resultado."""
    cmd = ["ffmpeg", "-y"] + args
    logger.info(f"FFmpeg: {descripcion}")
    resultado = subprocess.run(cmd, capture_output=True, text=True)
    if resultado.returncode != 0:
        logger.error(f"FFmpeg error: {resultado.stderr[-500:]}")
        raise RuntimeError(f"FFmpeg falló: {descripcion}")
    return resultado


def obtener_duracion(ruta: Path) -> float:
    """Retorna la duración en segundos de un archivo de audio o video."""
    resultado = subprocess.run([
        "ffprobe", "-v", "error", "-show_entries", "format=duration",
        "-of", "default=noprint_wrappers=1:nokey=1", str(ruta)
    ], capture_output=True, text=True)
    return float(resultado.stdout.strip())


# ============================================================
# MÓDULO 7A — VIDEO LARGO 16:9
# ============================================================

def crear_video_largo(id_video: int) -> Path:
    """
    Ensambla el video largo completo:
    1. Crea clips de cada imagen con efecto Ken Burns
    2. Une todos los clips
    3. Mezcla con audio de voz y música de fondo
    4. Render final 1080p 16:9
    """
    produccion = obtener_produccion(id_video)
    carpeta_imagenes = config.PATHS["imagenes"] / f"video_{id_video}"
    ruta_audio = Path(produccion["ruta_audio_es"])
    carpeta_output = config.PATHS["videos_largos"]
    carpeta_temp = carpeta_output / f"_temp_{id_video}"
    carpeta_temp.mkdir(parents=True, exist_ok=True)

    ruta_final = carpeta_output / f"video_{id_video}_largo.mp4"

    if ruta_final.exists():
        logger.info("Video largo ya existe, saltando")
        return ruta_final

    # 1. Obtener duración total del audio de voz
    duracion_total = obtener_duracion(ruta_audio)
    logger.info(f"Duración del audio: {duracion_total:.1f}s ({duracion_total/60:.1f} min)")

    # 2. Recopilar todas las imágenes en orden
    imagenes = sorted(carpeta_imagenes.rglob("img_*.jpg"))
    if not imagenes:
        raise FileNotFoundError(f"No hay imágenes en {carpeta_imagenes}")

    logger.info(f"Total imágenes: {len(imagenes)}")

    # 3. Calcular cuántas imágenes necesitamos para cubrir toda la duración
    SEGUNDOS_POR_IMAGEN = 60  # Cada imagen dura 60 segundos en videos largos
    total_clips_necesarios = int(duracion_total / SEGUNDOS_POR_IMAGEN) + 1

    # Ciclar imágenes si no hay suficientes
    imagenes_cicladas = []
    while len(imagenes_cicladas) < total_clips_necesarios:
        imagenes_cicladas.extend(imagenes)
    imagenes_cicladas = imagenes_cicladas[:total_clips_necesarios]

    logger.info(f"Clips necesarios: {total_clips_necesarios} ({SEGUNDOS_POR_IMAGEN}s c/u)")

    # 4. Cargar mapa de clips animados (imagen → clip animado)
    carpeta_clips_animados = config.PATHS["clips"] / f"video_{id_video}"
    mapa_animados = {}
    if carpeta_clips_animados.exists():
        for clip_animado in carpeta_clips_animados.glob("animado_*.mp4"):
            # El nombre del clip contiene el nombre de la imagen original
            # ej: animado_capitulo_01_img_01.mp4 → img de capitulo_01/img_01.jpg
            partes = clip_animado.stem.replace("animado_", "")
            mapa_animados[partes] = clip_animado
    if mapa_animados:
        logger.info(f"Clips animados disponibles: {len(mapa_animados)}")

    # 5. Crear clips — animado si existe, Ken Burns si no
    clips = []
    for idx, img in enumerate(imagenes_cicladas):
        ruta_clip = carpeta_temp / f"clip_{idx:03d}.mp4"
        clips.append(ruta_clip)

        if ruta_clip.exists():
            continue

        # Buscar si hay clip animado para esta imagen
        clave_imagen = f"{img.parent.name}_{img.stem}"
        clip_animado = mapa_animados.get(clave_imagen)

        if clip_animado and clip_animado.exists():
            # Reescalar el clip animado al tamaño del video
            run_ffmpeg([
                "-i", str(clip_animado),
                "-vf", f"scale={config.VIDEO_WIDTH}:{config.VIDEO_HEIGHT},setsar=1,format=yuv420p",
                "-c:v", "libx264", "-preset", "fast", "-crf", "23",
                "-an",
                str(ruta_clip)
            ], f"Clip animado {idx+1}/{total_clips_necesarios}")
        else:
            # Efecto Ken Burns: alterna zoom in y zoom out
            frames = int(SEGUNDOS_POR_IMAGEN * 25)
            if idx % 2 == 0:
                zoompan = f"zoompan=z='min(zoom+0.0008,1.3)':x='iw/2-(iw/zoom/2)':y='ih/2-(ih/zoom/2)':d={frames}:s={config.VIDEO_WIDTH}x{config.VIDEO_HEIGHT}:fps=25"
            else:
                zoompan = f"zoompan=z='if(lte(zoom,1.0),1.3,max(1.0,zoom-0.0008))':x='iw/2-(iw/zoom/2)':y='ih/2-(ih/zoom/2)':d={frames}:s={config.VIDEO_WIDTH}x{config.VIDEO_HEIGHT}:fps=25"

            run_ffmpeg([
                "-loop", "1", "-i", str(img),
                "-vf", f"scale=2*{config.VIDEO_WIDTH}:2*{config.VIDEO_HEIGHT},format=yuv420p,{zoompan},setsar=1",
                "-t", str(SEGUNDOS_POR_IMAGEN),
                "-c:v", "libx264", "-preset", "fast", "-crf", "23",
                str(ruta_clip)
            ], f"Ken Burns clip {idx+1}/{total_clips_necesarios}")

    # 5. Concatenar todos los clips de video
    ruta_video_sin_audio = carpeta_temp / "video_sin_audio.mp4"
    lista_clips = carpeta_temp / "lista_clips.txt"
    with open(lista_clips, "w") as f:
        for clip in clips:
            f.write(f"file '{clip.absolute()}'\n")

    run_ffmpeg([
        "-f", "concat", "-safe", "0", "-i", str(lista_clips),
        "-c", "copy", str(ruta_video_sin_audio)
    ], "Concatenando clips")

    # 6. Preparar música de fondo
    # Usamos un track épico como base y batalla para el clímax
    track_base = obtener_track("epico")
    track_climax = obtener_track("batalla")

    # Mezclar audio: voz al 100% + música al 18% con fade
    # batalla_climax entra desde el segundo 25 del track con fade in de 3s
    # Inputs: 0=video, 1=voz, 2=musica (en loop)
    # Mezcla simple: voz al 100% + música al 18%
    filter_audio = (
        f"[1:a]volume=1.0[voz];"
        f"[2:a]volume={config.MUSIC_VOLUME_BASE},aloop=loop=-1:size=2147483647[musica];"
        f"[voz][musica]amix=inputs=2:duration=first[audio_final]"
    )

    run_ffmpeg([
        "-i", str(ruta_video_sin_audio),
        "-i", str(ruta_audio),
        "-i", str(track_base),
        "-filter_complex", filter_audio,
        "-map", "0:v",
        "-map", "[audio_final]",
        "-c:v", "copy",
        "-c:a", "aac", "-b:a", "192k",
        "-t", str(duracion_total),
        str(ruta_final)
    ], "Mezclando audio con música")

    # Limpiar archivos temporales
    import shutil
    shutil.rmtree(carpeta_temp, ignore_errors=True)

    duracion_final = obtener_duracion(ruta_final)
    tamanio_mb = ruta_final.stat().st_size / (1024 * 1024)
    logger.success(f"✅ Video largo: {ruta_final.name} ({duracion_final/60:.1f} min, {tamanio_mb:.0f} MB)")

    return ruta_final


# ============================================================
# MÓDULO 7B — CORTOS VERTICALES 9:16
# ============================================================

def crear_corto(id_video: int, numero_corto: int, datos_corto: dict) -> Path:
    """
    Ensambla un corto vertical 9:16 con:
    - Imágenes recortadas a vertical
    - Audio de voz del corto
    - Música de fondo suave
    - Subtítulos dinámicos estilo TikTok
    """
    # El audio de los cortos lo genera el módulo de voz en esta ruta fija
    ruta_audio = config.PATHS["audio"] / f"video_{id_video}" / "cortos" / f"corto_{numero_corto}_es.mp3"
    if not ruta_audio.exists():
        raise FileNotFoundError(f"No hay audio para el corto {numero_corto}: {ruta_audio}")

    carpeta_imagenes = config.PATHS["imagenes"] / f"video_{id_video}"
    carpeta_output = config.PATHS["cortos"]
    carpeta_temp = carpeta_output / f"_temp_{id_video}_{numero_corto}"
    carpeta_temp.mkdir(parents=True, exist_ok=True)

    ruta_final = carpeta_output / f"video_{id_video}_corto_{numero_corto}.mp4"

    if ruta_final.exists():
        logger.info(f"Corto {numero_corto} ya existe, saltando")
        return ruta_final

    # Duración del audio del corto
    duracion = obtener_duracion(ruta_audio)
    logger.info(f"Corto {numero_corto}: {duracion:.1f}s")

    # Seleccionar imágenes — orden aleatorio para variedad entre cortos
    imagenes = sorted(carpeta_imagenes.rglob("img_*.jpg"))
    if not imagenes:
        raise FileNotFoundError("No hay imágenes para el corto")

    # Imagen cada 4-6 segundos, ajustando la cantidad de imágenes según duración
    DURACION_IMAGEN = 5.0  # segundos por imagen en cortos
    n_imagenes = max(3, min(10, int(duracion / DURACION_IMAGEN)))
    imagenes_mezcladas = imagenes.copy()
    random.shuffle(imagenes_mezcladas)
    imagenes_corto = imagenes_mezcladas[:n_imagenes]
    duracion_por_imagen = duracion / len(imagenes_corto)

    W = config.SHORT_WIDTH   # 1080
    H = config.SHORT_HEIGHT  # 1920

    # Transiciones xfade disponibles en FFmpeg 8 — cinematográficas y variadas
    TRANSICIONES_XFADE = [
        "coverleft",    # nueva imagen entra cubriendo desde la izquierda
        "coverright",   # nueva imagen entra cubriendo desde la derecha
        "revealleft",   # imagen actual se retira revelando la siguiente
        "zoomin",       # zoom in al cambiar
        "slideleft",    # deslizamiento izquierda
        "slideright",   # deslizamiento derecha
        "wipeleft",     # barrido izquierda
        "smoothleft",   # suave hacia izquierda
        "smoothright",  # suave hacia derecha
        "fadeblack",    # fade a negro entre clips (dramático)
    ]

    # Tipos de efecto por clip (rotamos para variedad)
    # 0=zoom repentino fijo, 1=pan izq→der, 2=pan der→izq, 3=zoom suave gradual, 4=estático
    EFECTOS = [0, 1, 2, 3, 1, 2, 0, 4, 1, 2]

    clips = []
    for idx, img in enumerate(imagenes_corto):
        ruta_clip = carpeta_temp / f"clip_{idx:02d}.mp4"
        clips.append(ruta_clip)
        efecto = EFECTOS[idx % len(EFECTOS)]
        frames = int(duracion_por_imagen * 25)

        # Escalar a vertical 9:16: encajar por altura, recortar centro horizontal
        escala_base = f"scale=-1:{H},crop={W}:{H}:(iw-{W})/2:0"

        if efecto == 0:
            # Zoom repentino fijo: imagen 12% más grande, centrada
            vf = (
                f"{escala_base},"
                f"scale={int(W*1.12)}:{int(H*1.12)},"
                f"crop={W}:{H}:{int(W*0.06)}:{int(H*0.06)},"
                f"format=yuv420p"
            )
        elif efecto == 1:
            # Pan izquierda→derecha: zoompan con movimiento horizontal usando x variable
            vf = (
                f"{escala_base},"
                f"zoompan=z=1.5:x='(iw-iw/zoom)*on/{frames}':y='(ih-ih/zoom)/2'"
                f":d={frames}:s={W}x{H}:fps=25,"
                f"format=yuv420p"
            )
        elif efecto == 2:
            # Pan derecha→izquierda: zoompan con x inverso
            vf = (
                f"{escala_base},"
                f"zoompan=z=1.5:x='(iw-iw/zoom)*(1-on/{frames})':y='(ih-ih/zoom)/2'"
                f":d={frames}:s={W}x{H}:fps=25,"
                f"format=yuv420p"
            )
        elif efecto == 3:
            # Zoom suave gradual: zoom in desde 1.0 a 1.08
            vf = (
                f"{escala_base},"
                f"zoompan=z='min(1+0.08*on/{frames},1.08)':x='iw/2-(iw/zoom/2)':y='ih/2-(ih/zoom/2)'"
                f":d={frames}:s={W}x{H}:fps=25,"
                f"format=yuv420p"
            )
        else:
            # Estático: sin movimiento
            vf = f"{escala_base},format=yuv420p"

        run_ffmpeg([
            "-loop", "1", "-i", str(img),
            "-vf", vf,
            "-t", str(duracion_por_imagen),
            "-r", "25",
            "-c:v", "libx264", "-preset", "fast", "-crf", "23",
            str(ruta_clip)
        ], f"Clip vertical {idx+1}/{len(imagenes_corto)}")

    # Concatenar clips con transiciones xfade variadas
    ruta_video_sin_audio = carpeta_temp / "video_sin_audio.mp4"

    if len(clips) == 1:
        import shutil as _shutil
        _shutil.copy(clips[0], ruta_video_sin_audio)
    else:
        duracion_transicion = 0.5
        inputs = []
        for clip in clips:
            inputs += ["-i", str(clip)]

        filtro = ""
        entrada_actual = "0:v"
        tiempo_acumulado = duracion_por_imagen - duracion_transicion

        for i in range(1, len(clips)):
            transicion = TRANSICIONES_XFADE[i % len(TRANSICIONES_XFADE)]
            salida = f"v{i}"
            filtro += (
                f"[{entrada_actual}][{i}:v]xfade=transition={transicion}"
                f":duration={duracion_transicion}:offset={tiempo_acumulado:.2f}[{salida}];"
            )
            entrada_actual = salida
            tiempo_acumulado += duracion_por_imagen - duracion_transicion

        filtro = filtro.rstrip(";")

        run_ffmpeg(
            inputs + [
                "-filter_complex", filtro,
                "-map", f"[{entrada_actual}]",
                "-c:v", "libx264", "-preset", "fast", "-crf", "23",
                str(ruta_video_sin_audio)
            ],
            "Concatenando clips con transiciones"
        )

    # Música de fondo para cortos
    track_musica = obtener_track("epico")

    # Generar subtítulos con Whisper (formato ASS con estilo embebido)
    ruta_ass = carpeta_temp / f"corto_{numero_corto}.ass"
    _generar_subtitulos(ruta_audio, ruta_ass)

    # Filtro de subtítulos: 'subtitles' con ASS ya tiene el estilo embebido, sin force_style
    ruta_ass_escaped = str(ruta_ass).replace(":", "\\:")
    subtitulos_filter = f"subtitles={ruta_ass_escaped}"

    run_ffmpeg([
        "-i", str(ruta_video_sin_audio),
        "-i", str(ruta_audio),
        "-i", str(track_musica),
        "-filter_complex",
        f"[2:a]volume={config.MUSIC_VOLUME_BASE},aloop=loop=-1:size=2147483647[musica];"
        f"[1:a][musica]amix=inputs=2:duration=first[audio_final]",
        "-map", "0:v",
        "-map", "[audio_final]",
        "-vf", subtitulos_filter,
        "-c:v", "libx264", "-preset", "fast", "-crf", "23",
        "-c:a", "aac", "-b:a", "128k",
        "-shortest",
        str(ruta_final)
    ], f"Render final corto {numero_corto}")

    import shutil
    shutil.rmtree(carpeta_temp, ignore_errors=True)

    tamanio_mb = ruta_final.stat().st_size / (1024 * 1024)
    logger.success(f"✅ Corto {numero_corto}: {ruta_final.name} ({tamanio_mb:.1f} MB)")

    return ruta_final


def _generar_subtitulos(ruta_audio: Path, ruta_ass: Path):
    """Genera subtítulos en formato ASS con estilo embebido usando Whisper."""
    try:
        import whisper
        logger.info("Generando subtítulos con Whisper...")
        modelo = whisper.load_model("base")
        resultado = modelo.transcribe(str(ruta_audio), language="es")

        # Cabecera ASS con estilo: texto blanco, negrita, centrado en pantalla
        cabecera = (
            "[Script Info]\n"
            "ScriptType: v4.00+\n"
            "PlayResX: 1080\n"
            "PlayResY: 1920\n\n"
            "[V4+ Styles]\n"
            "Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding\n"
            # FontSize 36 — bien legible en móvil
            # Alignment 5 = centro horizontal, centro vertical (mitad de pantalla)
            # Outline 4, Shadow 2 para máxima legibilidad sobre cualquier imagen
            "Style: Default,Arial,52,&H00FFFFFF,&H000000FF,&H00000000,&H64000000,1,0,0,0,100,100,0,0,1,4,2,5,60,60,960,1\n\n"
            "[Events]\n"
            "Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text\n"
        )

        with open(ruta_ass, "w", encoding="utf-8") as f:
            f.write(cabecera)
            for segmento in resultado["segments"]:
                texto = segmento["text"].strip()
                if not texto:
                    continue
                dur_seg = segmento["end"] - segmento["start"]
                palabras = texto.split()
                # Dividir en bloques de máx 4 palabras para subtítulos dinámicos
                MAX_PALABRAS = 4
                bloques = [palabras[i:i+MAX_PALABRAS] for i in range(0, len(palabras), MAX_PALABRAS)]
                dur_bloque = dur_seg / len(bloques)
                for j, bloque in enumerate(bloques):
                    t_ini = segmento["start"] + j * dur_bloque
                    t_fin = t_ini + dur_bloque
                    inicio = _segundos_a_ass(t_ini)
                    fin = _segundos_a_ass(t_fin)
                    linea = " ".join(bloque).upper()  # MAYÚSCULAS estilo TikTok
                    f.write(f"Dialogue: 0,{inicio},{fin},Default,,0,0,0,,{linea}\n")

        logger.info(f"✓ Subtítulos generados: {ruta_ass.name}")
    except Exception as e:
        logger.warning(f"Whisper no disponible, corto sin subtítulos: {e}")
        # Crear ASS vacío para que FFmpeg no falle
        ruta_ass.write_text(
            "[Script Info]\nScriptType: v4.00+\nPlayResX: 1080\nPlayResY: 1920\n\n[V4+ Styles]\nFormat: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding\nStyle: Default,Arial,42,&H00FFFFFF,&H000000FF,&H00000000,&H64000000,1,0,0,0,100,100,0,0,1,4,2,5,60,60,960,1\n\n[Events]\nFormat: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text\n"
        )


def _segundos_a_srt(segundos: float) -> str:
    """Convierte segundos a formato SRT: HH:MM:SS,mmm"""
    h = int(segundos // 3600)
    m = int((segundos % 3600) // 60)
    s = int(segundos % 60)
    ms = int((segundos % 1) * 1000)
    return f"{h:02d}:{m:02d}:{s:02d},{ms:03d}"


def _segundos_a_ass(segundos: float) -> str:
    """Convierte segundos a formato ASS: H:MM:SS.cc"""
    h = int(segundos // 3600)
    m = int((segundos % 3600) // 60)
    s = int(segundos % 60)
    cs = int((segundos % 1) * 100)  # centisegundos
    return f"{h}:{m:02d}:{s:02d}.{cs:02d}"


# ============================================================
# ORQUESTADOR
# ============================================================

def ensamblar_video(id_video: int, tipo: str = "largo"):
    """
    tipo: 'largo' | 'cortos' | 'todo'
    """
    if tipo in ("largo", "todo"):
        logger.info("Ensamblando video largo...")
        ruta = crear_video_largo(id_video)
        guardar_produccion(id_video, {
            "ruta_video_final":  str(ruta),
            "estado_produccion": "video",
        })

    if tipo in ("cortos", "todo"):
        logger.info("Ensamblando cortos...")
        cortos = obtener_cortos(id_video)
        for corto in cortos:
            numero = int(corto.get("numero_corto", 0))
            try:
                ruta = crear_corto(id_video, numero, corto)
                guardar_corto(id_video, numero, {
                    "ruta_video_corto": str(ruta),
                    "estado": "listo",
                })
            except Exception as e:
                logger.error(f"Error en corto {numero}: {e}")


# ============================================================
# EJECUCIÓN DIRECTA
# ============================================================

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--id",   type=int, default=1)
    parser.add_argument("--tipo", type=str, default="largo", choices=["largo", "cortos", "todo"])
    args = parser.parse_args()

    logger.add(str(config.PATHS["logs"] / "pipeline.log"), rotation="10 MB")
    config.crear_directorios()

    ensamblar_video(args.id, args.tipo)
