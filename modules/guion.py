"""
Módulo 2+3: Generación de guiones con Claude API.

Módulo 2: Genera el guión largo (20-23 min) en ES-LA + EN,
           prompts visuales por capítulo, título SEO, descripción y tags.

Módulo 3: Extrae los 3 momentos más impactantes del guión largo
           y genera 3 guiones cortos de 60-90 segundos.

Uso directo para testear:
  python modules/guion.py --id 1
"""

import json
import sys
import argparse
from pathlib import Path

import anthropic
from loguru import logger

sys.path.insert(0, str(Path(__file__).parent.parent))
import config
from sheets.sheets_client import (
    obtener_siguiente_tema,
    obtener_produccion,
    guardar_produccion,
    guardar_corto,
    actualizar_estado_tema,
)

# Cliente de Claude
cliente = anthropic.Anthropic(api_key=config.ANTHROPIC_API_KEY)


# ============================================================
# MÓDULO 2 — GUIÓN LARGO
# ============================================================

def generar_guion_largo(tema: dict) -> dict:
    """
    Genera el guión en dos llamadas separadas:
    1. El texto narrativo completo (sin límite de tamaño)
    2. Los metadatos y prompts visuales (JSON pequeño)
    """
    logger.info(f"Generando guión ES-LA para: {tema['tema']}")

    # --- LLAMADA 1: Solo el texto narrativo ---
    prompt_texto = f"""Eres el mejor guionista de documentales históricos del mundo hispanohablante.
Has trabajado para Netflix, National Geographic y History Channel.
Tu especialidad: convertir la historia en experiencias que hacen que la gente no pueda parar de ver.

TEMA: {tema['tema']}
CATEGORÍA: {tema.get('categoria', 'historia')}

REGLAS DE ORO — sin excepción:

1. EL PRIMER PÁRRAFO ES TODO. Si no engancha en 20 segundos, el espectador se va. Empieza con la escena más brutal, el dato más impactante o la pregunta que nadie puede ignorar. Nada de introducciones suaves.

2. HAZLO PERSONAL Y VISCERAL. No cuentes la historia desde afuera. Mete al espectador dentro. "Sientes el frío del metal en tu mano." "El olor a sangre y tierra mojada llena el aire." "Tus rodillas tiemblan pero no puedes retroceder."

3. GUERREROS, BATALLAS Y DECISIONES IMPOSIBLES. La gente quiere ver poder, violencia épica, sacrificio extremo y momentos donde todo se decide. Dales eso. Hazlo cinematográfico.

4. DATOS QUE EXPLOTAN LA MENTE. Intercala hechos históricos tan sorprendentes que la gente quiera pausar el video para contárselos a alguien. "Lo que nadie te enseñaron en la escuela."

5. TENSIÓN CONSTANTE. Cada párrafo debe terminar con una pregunta implícita o una amenaza que obliga a seguir escuchando. Nunca resuelvas demasiado rápido.

6. RITMO CINEMATOGRÁFICO. Alterna entre escenas de acción brutal (frases cortas, explosivas) y momentos de reflexión profunda (frases largas, poéticas). Como una película de acción con alma.

ESTRUCTURA (10-12 minutos de narración):

APERTURA (0-1 min): Escena in medias res. Empieza en el momento más tenso. Sin contexto previo. El espectador debe estar confundido y fascinado al mismo tiempo.

CONTEXTO (1-3 min): Ahora sitúa. Quién, dónde, cuándo. Pero hazlo épico, no académico.

DESARROLLO (3-9 min): 5-6 momentos clave con tensión creciente. Cada uno más intenso que el anterior. Incluye: traiciones, alianzas imposibles, momentos de gloria y de caída, decisiones que cambiaron la historia.

CLÍMAX (9-11 min): El momento definitivo. La batalla, la ejecución, la traición, el sacrificio. Máxima intensidad. Que el espectador sienta que está ahí.

CIERRE (11-12 min): Consecuencias impactantes. Dato final que recontextualiza todo. Pregunta filosófica que invite al comentario. CTA natural hacia el canal.

ESTILO OBLIGATORIO:
- Segunda persona visceral: "Sientes el peso del escudo." "Tus pulmones arden." "Miras a los ojos al enemigo."
- Frases de 3-5 palabras en acción. Frases largas y poéticas en reflexión.
- Español latino neutro culto, accesible, con fuerza narrativa.
- NUNCA suene a enciclopedia. SIEMPRE suene a película épica narrada.
- Usa onomatopeyas, metáforas sensoriales, imágenes brutalmente visuales.
- El oyente debe ver cada escena con los ojos cerrados.

FORMATO OBLIGATORIO:
- NUNCA uses markdown: nada de **, *, #, [], ()
- NUNCA uses guiones largos ni bullets
- NUNCA uses comillas tipográficas, usa solo comillas simples ('')
- NUNCA escribas etiquetas, marcadores, títulos de sección ni notas de producción
- El texto va directo a voz, escribe exactamente como debe sonar
- Solo texto limpio: letras, números, puntos, comas, exclamaciones, interrogaciones

Flujo continuo sin cortes visibles. SOLO el guión narrativo."""

    respuesta1 = cliente.messages.create(
        model="claude-sonnet-4-5",
        max_tokens=8000,
        messages=[{"role": "user", "content": prompt_texto}],
    )
    guion_texto = respuesta1.content[0].text.strip()
    logger.info(f"✓ Texto del guión generado ({len(guion_texto)} caracteres)")

    # --- LLAMADA 2: Metadatos y prompts visuales ---
    prompt_meta = f"""Basándote en este guión histórico, genera los metadatos para YouTube y los prompts visuales.

GUIÓN:
{guion_texto[:4000]}...

RESPONDE ÚNICAMENTE con un JSON válido:
{{
  "titulo_yt": "título SEO optimizado, máximo 60 caracteres, en español",
  "descripcion_yt": "descripción YouTube 200-300 palabras con keywords hispanohablantes y timestamps",
  "tags_yt": "tag1,tag2,tag3,tag4,tag5,tag6,tag7,tag8,tag9,tag10",
  "capitulos": [
    {{
      "numero": 1,
      "nombre": "nombre del capítulo",
      "prompts_visuales": [
        "prompt 1",
        "prompt 2",
        "prompt 3",
        "prompt 4",
        "prompt 5",
        "prompt 6",
        "prompt 7"
      ]
    }}
  ]
}}

REGLAS ESTRICTAS PARA LOS PROMPTS VISUALES:
Cada prompt es en INGLÉS y describe una escena fotorrealista e histórica para una IA generadora de imágenes.

TIPOS DE ESCENA — rota entre todos para máxima variedad:
1. PERSONAJE PRINCIPAL: primer plano épico del líder/guerrero/rey protagonista del capítulo. Cara, armadura, expresión feroz o determinada. Cicatrices, barba, casco. Muy detallado.
2. COMBATE/BATALLA: soldados chocando en combate cuerpo a cuerpo. Lanzas, espadas, escudos, sangre, polvo, caos. Ángulo bajo dramático.
3. SÍMBOLO/OBJETO ICÓNICO: el arma, estandarte, corona, mapa, pergamino, reliquia o símbolo que define el capítulo. Primer plano con iluminación dramática.
4. EJÉRCITO/FORMACIÓN: miles de guerreros en formación lista para atacar. Perspectiva aérea o frontal masiva. Banderas, armas en alto.
5. MOMENTO HISTÓRICO: la escena exacta del evento clave narrado — traición, coronación, firma, ejecución, sacrificio. Captura la emoción.
6. PAISAJE ÉPICO CON ACCIÓN: campo de batalla, fortaleza asediada, ciudad en llamas, barcos de guerra. Escala épica con personas visibles.
7. CONSECUENCIA/EMOCIÓN: supervivientes entre cadáveres, un rey mirando su reino destruido, un guerrero solitario. Silencio y peso dramático.

PROHIBICIONES ABSOLUTAS:
- NO paisajes vacíos sin personas
- NO monumentos o esculturas estáticas sin contexto humano
- NO repetir el mismo tipo de escena dos veces seguidas
- NO texto, watermarks ni elementos modernos
- SIEMPRE incluir personas, guerreros, o figuras humanas en cada prompt

Varía razas, épocas, culturas, climas (desierto, nieve, jungla, mar) según el contexto histórico del guión."""

    respuesta2 = cliente.messages.create(
        model="claude-sonnet-4-5",
        max_tokens=3000,
        messages=[{"role": "user", "content": prompt_meta}],
    )

    texto_meta = respuesta2.content[0].text.strip()
    if texto_meta.startswith("```"):
        texto_meta = texto_meta.split("```")[1]
        if texto_meta.startswith("json"):
            texto_meta = texto_meta[4:]
        texto_meta = texto_meta.strip()

    meta = json.loads(texto_meta)
    meta["guion_completo"] = guion_texto
    logger.info(f"✓ Metadatos generados — {len(meta['capitulos'])} capítulos")
    return meta


# Traducción EN desactivada — canal solo en español por ahora
# def generar_guion_ingles(...)  # reservado para expansión futura


# ============================================================
# MÓDULO 3 — GUIONES CORTOS
# ============================================================

def generar_guiones_cortos(id_video: int, guion_completo: str, titulo: str) -> list:
    """
    Analiza el guión largo e identifica los 3 momentos más impactantes.
    Genera 3 guiones de 60-90 segundos para redes sociales.
    Retorna una lista de 3 diccionarios con los datos de cada corto.
    """
    logger.info("Generando 3 guiones cortos...")

    prompt = f"""Eres especialista en contenido viral para TikTok, Instagram Reels y YouTube Shorts.

Analiza este guión de video histórico y extrae los 3 momentos más impactantes para convertirlos en videos cortos virales de 60-90 segundos.

TÍTULO DEL VIDEO: {titulo}

GUIÓN COMPLETO:
{guion_completo[:6000]}

REGLAS PARA CADA CORTO:
- Los primeros 3 segundos deben enganchar BRUTALMENTE (dato impactante, pregunta imposible, afirmación polémica)
- Duración: entre 30 y 60 segundos según la relevancia del momento. Si el momento es muy impactante ve a 60 segundos. Si es un dato puntual o anécdota épica, 30-40 segundos es suficiente.
- Ritmo rápido, frases cortas, mucha energía
- Enfócate en momentos de acción, guerreros, batallas, traiciones, datos impactantes — lo que más engancha visualmente
- Termina con CTA: "La historia completa en {config.CHANNEL_NAME} en YouTube"
- Cada corto debe poder entenderse SIN haber visto el video largo
- Español latino neutro
- NUNCA uses markdown, asteriscos, corchetes ni caracteres especiales

RESPONDE ÚNICAMENTE con un JSON válido:
{{
  "cortos": [
    {{
      "numero": 1,
      "gancho": "la primera frase brutal que abre el corto",
      "guion": "guión completo del corto de 60-90 segundos",
      "titulo": "título para redes sociales, máximo 50 caracteres",
      "descripcion": "descripción corta para redes, 2-3 líneas",
      "hashtags": "#historia #vikingos #curiosidades (10-15 hashtags relevantes)"
    }},
    {{
      "numero": 2,
      ...
    }},
    {{
      "numero": 3,
      ...
    }}
  ]
}}"""

    respuesta = cliente.messages.create(
        model="claude-opus-4-5",
        max_tokens=4000,
        messages=[{"role": "user", "content": prompt}],
    )

    texto = respuesta.content[0].text.strip()

    if texto.startswith("```"):
        texto = texto.split("```")[1]
        if texto.startswith("json"):
            texto = texto[4:]
        texto = texto.strip()

    datos = json.loads(texto)
    cortos = datos["cortos"]
    logger.info(f"✓ {len(cortos)} guiones cortos generados")

    # Guardar cada corto en Google Sheets
    for corto in cortos:
        guardar_corto(id_video, corto["numero"], {
            "guion_corto":      corto["guion"],
            "titulo_corto":     corto["titulo"],
            "descripcion_corto": corto["descripcion"],
            "hashtags":         corto["hashtags"],
            "estado":           "guion_listo",
        })

    return cortos


# ============================================================
# ORQUESTADOR DEL MÓDULO
# ============================================================

def generar_guion_completo(id_video: int, tema: dict):
    """
    Ejecuta el flujo completo: guión ES → guión EN → 3 cortos → guarda en Sheets.
    Si ya existe el guión en Sheets, lo salta (reanudación inteligente).
    """
    # Verificar si ya existe guión (reanudación)
    produccion = obtener_produccion(id_video)
    if produccion and produccion.get("guion_es"):
        logger.info(f"Video {id_video}: guión ya existe, saltando generación")
        return

    try:
        # 1. Guión largo en español
        datos_es = generar_guion_largo(tema)

        # 2. Preparar prompts visuales como JSON string
        prompts = [
            {"capitulo": c["numero"], "nombre": c["nombre"], "prompt": c["prompt_visual"]}
            for c in datos_es["capitulos"]
        ]

        # 3. Guardar en Google Sheets (guion_en queda vacío para uso futuro)
        guardar_produccion(id_video, {
            "guion_es":         datos_es["guion_completo"],
            "prompts_visuales": json.dumps(prompts, ensure_ascii=False),
            "titulo_yt":        datos_es["titulo_yt"],
            "descripcion_yt":   datos_es["descripcion_yt"],
            "tags_yt":          datos_es["tags_yt"],
            "estado_produccion": "guion",
        })

        # 5. Guardar guión ES en archivo local también (útil para revisar)
        ruta_guion = config.PATHS["guiones"] / f"video_{id_video}_es.txt"
        ruta_guion.write_text(datos_es["guion_completo"], encoding="utf-8")
        logger.info(f"Guión guardado en: {ruta_guion}")

        # 6. Guiones cortos (Módulo 3)
        generar_guiones_cortos(id_video, datos_es["guion_completo"], datos_es["titulo_yt"])

        logger.success(f"✅ Módulos 2+3 completados para video {id_video}")

    except json.JSONDecodeError as e:
        logger.error(f"Claude no devolvió JSON válido: {e}")
        raise
    except Exception as e:
        logger.error(f"Error generando guión: {e}")
        raise


# ============================================================
# EJECUCIÓN DIRECTA PARA TESTEAR
# ============================================================

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--id", type=int, help="ID del tema a procesar")
    args = parser.parse_args()

    logger.add(str(config.PATHS["logs"] / "pipeline.log"), rotation="10 MB")
    config.crear_directorios()

    if args.id:
        produccion = obtener_produccion(args.id)
        if not produccion:
            logger.error(f"No se encontró el video {args.id} en la hoja produccion")
            sys.exit(1)
        tema = {"id": args.id, "tema": produccion.get("titulo_yt", f"Video {args.id}"), "categoria": "historia"}
    else:
        tema = obtener_siguiente_tema()
        if not tema:
            logger.error("No hay temas pendientes en Google Sheets")
            sys.exit(1)

    generar_guion_completo(tema["id"], tema)
