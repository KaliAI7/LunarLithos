#!/usr/bin/env bash
# Detecta el display de la sesion VNC y ejecuta test.py (Analog Finder).
# Uso: ./run_vnc.sh            (usa test.py)
#      ./run_vnc.sh otro.py    (usa otro script)

set -u

PROJECT_DIR="$HOME/Desktop/UTD/NASA"
VENV="$PROJECT_DIR/venv_vision_310"
SCRIPT="${1:-test.py}"

# ---------------------------------------------------------------
# Prueba si un display responde
# ---------------------------------------------------------------
display_ok() {
    local d="$1"
    if command -v xdpyinfo >/dev/null 2>&1; then
        DISPLAY="$d" xdpyinfo >/dev/null 2>&1
    elif command -v xset >/dev/null 2>&1; then
        DISPLAY="$d" xset q >/dev/null 2>&1
    else
        # Sin herramientas de prueba: acepta si existe el socket X
        local n="${d#:}"; n="${n%%.*}"
        [ -S "/tmp/.X11-unix/X${n}" ]
    fi
}

# Xauthority: necesaria en algunas sesiones VNC
if [ -z "${XAUTHORITY:-}" ] && [ -f "$HOME/.Xauthority" ]; then
    export XAUTHORITY="$HOME/.Xauthority"
fi

FOUND=""

# 1) Usar DISPLAY si ya esta definido y funciona (terminal dentro de VNC)
if [ -n "${DISPLAY:-}" ] && display_ok "$DISPLAY"; then
    FOUND="$DISPLAY"
fi

# 2) Buscar procesos de servidor VNC y leer su display
if [ -z "$FOUND" ]; then
    CANDIDATES=$(ps -eo args 2>/dev/null \
        | grep -E 'Xvnc|Xtigervnc|Xtightvnc|x11vnc|x0vncserver' \
        | grep -v grep \
        | grep -oE '(^|[ =])(:[0-9]+)' \
        | tr -d ' =' | sort -u)
    for d in $CANDIDATES; do
        if display_ok "$d"; then FOUND="$d"; break; fi
    done
fi

# 3) Buscar sockets X abiertos en /tmp/.X11-unix
if [ -z "$FOUND" ]; then
    for sock in /tmp/.X11-unix/X*; do
        [ -S "$sock" ] || continue
        d=":${sock##*/X}"
        if display_ok "$d"; then FOUND="$d"; break; fi
    done
fi

# 4) Ultimo recurso: probar :0 al :9
if [ -z "$FOUND" ]; then
    for n in 0 1 2 3 4 5 6 7 8 9; do
        if display_ok ":$n"; then FOUND=":$n"; break; fi
    done
fi

if [ -z "$FOUND" ]; then
    echo "[ERROR] No se encontro ningun display X activo."
    echo "        Ejecuta este script desde una terminal DENTRO de la sesion VNC."
    echo "        Pistas:  ps aux | grep -i vnc    y    ls /tmp/.X11-unix"
    exit 1
fi

export DISPLAY="$FOUND"
echo "[INFO] Display detectado: $DISPLAY"

# ---------------------------------------------------------------
# Ajustes para que Qt/OpenCV abran la ventana bajo VNC
# ---------------------------------------------------------------
export QT_QPA_PLATFORM=xcb
export QT_X11_NO_MITSHM=1
export QT_QPA_PLATFORM_PLUGIN_PATH=""   # evita usar el plugin Qt de cv2 si choca

# ---------------------------------------------------------------
# Entorno virtual y ejecucion
# ---------------------------------------------------------------
if [ ! -f "$VENV/bin/activate" ]; then
    echo "[ERROR] No existe el entorno virtual: $VENV"
    exit 1
fi
# shellcheck disable=SC1091
source "$VENV/bin/activate"

cd "$PROJECT_DIR" || exit 1

if [ ! -f "$SCRIPT" ]; then
    echo "[ERROR] No existe $PROJECT_DIR/$SCRIPT"
    exit 1
fi

echo "[INFO] Ejecutando $SCRIPT ..."
exec python "$SCRIPT"
