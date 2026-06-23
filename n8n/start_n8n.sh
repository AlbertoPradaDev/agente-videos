#!/usr/bin/env bash
#
# Arranca n8n con permiso para que los nodos "Code" puedan ejecutar el
# pipeline (modulo child_process de Node, bloqueado por defecto en n8n).
#
# Uso:
#   ./n8n/start_n8n.sh
#
# Deja esta terminal abierta mientras quieras que n8n este disponible.
# Panel: http://localhost:5678
#
set -euo pipefail

# Permite a los nodos Code usar require('child_process') para lanzar el script.
export NODE_FUNCTION_ALLOW_BUILTIN=child_process

# nvm: asegura que 'n8n' este en el PATH (Node v22 instalado via nvm).
export NVM_DIR="${NVM_DIR:-$HOME/.nvm}"
# shellcheck disable=SC1091
[ -s "$NVM_DIR/nvm.sh" ] && . "$NVM_DIR/nvm.sh" >/dev/null 2>&1 || true

echo "▶ Arrancando n8n con NODE_FUNCTION_ALLOW_BUILTIN=child_process"
echo "  Panel: http://localhost:5678   (Ctrl+C para detener)"
exec n8n start
