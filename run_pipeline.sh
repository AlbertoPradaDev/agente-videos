#!/usr/bin/env bash
#
# Wrapper para ejecutar el pipeline de videos desde n8n (o cron, o a mano).
# n8n invoca este script con un PATH mínimo, así que aquí fijamos todo lo
# necesario: directorio del proyecto, PATH con ffmpeg (Homebrew) y el venv.
#
# Uso:
#   ./run_pipeline.sh                      # siguiente tema pendiente
#   ./run_pipeline.sh --id 6 --desde edicion
#
set -euo pipefail

PROJECT_DIR="/Users/cex/Documents/Workspace/tools/agente_videos"
cd "$PROJECT_DIR"

# ffmpeg/ffprobe viven en Homebrew; n8n no los tiene en su PATH por defecto.
export PATH="/opt/homebrew/bin:/usr/local/bin:/usr/bin:/bin:$PATH"

PYTHON="$PROJECT_DIR/venv_311/bin/python3"
LOG_DIR="$PROJECT_DIR/logs"
mkdir -p "$LOG_DIR"
STAMP="$(date +%Y%m%d_%H%M%S)"
LOG_FILE="$LOG_DIR/n8n_run_$STAMP.log"

echo "▶ Pipeline iniciado $(date '+%Y-%m-%d %H:%M:%S')  args: $*"

# tee para ver la salida en n8n y guardarla en disco. PIPESTATUS preserva el
# código de salida real de python (si falla, n8n marca el workflow como error).
"$PYTHON" main.py "$@" 2>&1 | tee "$LOG_FILE"
CODE="${PIPESTATUS[0]}"

echo "■ Pipeline terminado con código $CODE  (log: $LOG_FILE)"
exit "$CODE"
