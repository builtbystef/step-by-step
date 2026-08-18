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
export DISPLAY

Xvfb "$DISPLAY" -screen 0 "$SCREEN_GEOMETRY" -nolisten tcp &

# Wait for the display rather than racing it: the window manager and the VNC
# server both fail outright against an X server that is not up yet.
until xdpyinfo -display "$DISPLAY" >/dev/null 2>&1; do
  sleep 0.1
done

openbox --sm-disable >/dev/null 2>&1 &

# No password: the server is unreachable from anywhere but this compose
# network, and the view-only and control credentials the backend proxy
# authenticates with are 5yu03g's, along with the proxy that uses them.
x11vnc -display "$DISPLAY" -rfbport "$VNC_PORT" -forever -shared -nopw -quiet &

exec python -m step_by_step_worker
