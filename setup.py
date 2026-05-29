"""
Script de configuración inicial del proyecto.
Ejecuta esto una sola vez después de clonar el repositorio.

Uso: python setup.py
"""

import shutil
import subprocess
import sys
from pathlib import Path


def main():
    print("\n🎬 AGENTE DE VIDEOS HISTÓRICOS — Setup inicial\n")
    base = Path(__file__).parent

    # 1. Crear .env desde template
    env_file = base / ".env"
    env_example = base / ".env.example"
    if not env_file.exists():
        shutil.copy(env_example, env_file)
        print("✓ .env creado desde .env.example")
        print("  → Ábrelo y rellena tus API keys antes de continuar\n")
    else:
        print("✓ .env ya existe (no sobreescrito)\n")

    # 2. Crear carpeta output/musica con README
    musica_dir = base / "output" / "musica"
    musica_dir.mkdir(parents=True, exist_ok=True)
    readme = musica_dir / "INSTRUCCIONES.txt"
    if not readme.exists():
        readme.write_text(
            "Coloca aquí tus archivos .mp3 descargados de Artlist.\n"
            "Nombra los archivos descriptivamente, ej:\n"
            "  epico_batalla_01.mp3\n"
            "  dramatico_lento_02.mp3\n"
            "  reflectivo_orquestal_03.mp3\n"
        )

    # 3. Verificar FFmpeg
    if shutil.which("ffmpeg"):
        result = subprocess.run(["ffmpeg", "-version"], capture_output=True, text=True)
        version = result.stdout.split("\n")[0]
        print(f"✓ FFmpeg encontrado: {version}")
    else:
        print("⚠️  FFmpeg NO encontrado.")
        print("   Mac:    brew install ffmpeg")
        print("   Ubuntu: sudo apt install ffmpeg\n")

    # 4. Verificar Python version
    v = sys.version_info
    if v.major == 3 and v.minor >= 11:
        print(f"✓ Python {v.major}.{v.minor}.{v.micro}")
    else:
        print(f"⚠️  Python {v.major}.{v.minor} detectado. Se recomienda Python 3.11+")

    print("\n📋 PRÓXIMOS PASOS:")
    print("  1. Edita .env con tus API keys")
    print("  2. pip install -r requirements.txt")
    print("  3. Sigue la guía de Google Sheets (ver instrucciones en README)")
    print("  4. python main.py --test")
    print("  5. Añade temas a tu Google Sheet y ejecuta: python main.py\n")


if __name__ == "__main__":
    main()
