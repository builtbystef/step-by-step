#!/bin/sh
# Bring up the Worker's desktop, then hand the container over to the Worker.
#
# Every replica gets this same script and the same DISPLAY and VNC port: each
# runs in a network and PID namespace of its own, so two Workers collide over
# neither. Nothing here is published to the host — compose gives the Worker no
# ports at all, which is what keeps the VNC server on the compose network.
set -eu

: "${DISPLAY:=:99}"
: "${VNC_PORT:=5900}"
: "${SCREEN_GEOMETRY:=1280x1024x24}"
: "${VNC_CONTROL_PASSWORD:?VNC_CONTROL_PASSWORD is required}"
: "${VNC_VIEW_PASSWORD:?VNC_VIEW_PASSWORD is required}"
export DISPLAY

Xvfb "$DISPLAY" -screen 0 "$SCREEN_GEOMETRY" -nolisten tcp &

# Wait for the display rather than racing it: the window manager and the VNC
# server both fail outright against an X server that is not up yet.
until xdpyinfo -display "$DISPLAY" >/dev/null 2>&1; do
  sleep 0.1
done

openbox --sm-disable >/dev/null 2>&1 &

# Two passwords, shared across Workers, the same values the backend proxy
# authenticates with. View-only is a VNC-server fact, not a noVNC setting.
# The file is mode 600 in /tmp; x11vnc reads it and does not take passwords
# from the process listing.
PASSWD_FILE="${VNC_PASSWD_FILE:-/tmp/x11vnc.pass}"
umask 077
{
  printf '%s\n' "$VNC_CONTROL_PASSWORD"
  printf '%s\n' "__BEGIN_VIEWONLY__"
  printf '%s\n' "$VNC_VIEW_PASSWORD"
} >"$PASSWD_FILE"

x11vnc -display "$DISPLAY" -rfbport "$VNC_PORT" -forever -shared \
  -passwdfile "$PASSWD_FILE" -quiet &

exec python -m step_by_step_worker
