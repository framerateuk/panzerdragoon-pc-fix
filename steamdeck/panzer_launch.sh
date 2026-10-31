#!/bin/bash
# Panzer Dragoon (Sega PC, Windows 95, 1996) Steam Deck / Proton launch wrapper.
#
# Keep it beside game/ (build.py puts it there). With the folder at /home/deck/Games/PanzerDragoon:
#   Shortcut target: /home/deck/Games/PanzerDragoon/game/PANZERDG.EXE, Start In: .../game/
#   Steam > Panzer Dragoon > Properties > Launch Options:
#     /home/deck/Games/PanzerDragoon/panzer_launch.sh %command%
#
# PANZERDG.EXE is patched (patch_exe.py): no CD hunt (data, movies and the "cdaudio" device all resolve
# without a drive), settings in game/PANZERDG.INI instead of C:\windows, Esc quits, D-pad read.
# So no fake CD-ROM drive and no registry are needed.
#
# Every launch sets DLL overrides so Wine loads the wrappers sitting beside the exe:
#   winmm.dll   ogg-winmm: CD audio from Music/TrackNN.ogg
#   ddraw.dll   dgVoodoo2 2.79.3: 640x480 16-bit DirectDraw -> D3D11 -> DXVK, the 640x400 picture full screen
#
# RENDERER (set before the script path in Launch Options, default dgvoodoo):
#   dgvoodoo  ddraw from dgVoodoo2
#   wined3d   plain Wine ddraw
#   Example:  RENDERER=wined3d /home/deck/Games/PanzerDragoon/panzer_launch.sh %command%

set -u
HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
LOG="$HERE/launch.log"
RENDERER="${RENDERER:-dgvoodoo}"
log() { echo "[$(date '+%H:%M:%S')] $*" >>"$LOG"; }
: >"$LOG"
log "args: $*"
log "RENDERER=$RENDERER  STEAM_COMPAT_DATA_PATH=${STEAM_COMPAT_DATA_PATH:-unset}"

# Proton appends its own overrides after ours.
OVR="winmm=n,b"
case "$RENDERER" in
  dgvoodoo) OVR="$OVR;ddraw=n,b" ;;
  wined3d)  OVR="$OVR;ddraw=b" ;;
  *)        log "unknown RENDERER '$RENDERER', using dgvoodoo"; OVR="$OVR;ddraw=n,b" ;;
esac
export WINEDLLOVERRIDES="${OVR}${WINEDLLOVERRIDES:+;$WINEDLLOVERRIDES}"
log "WINEDLLOVERRIDES=$WINEDLLOVERRIDES"

# Debugging: if a file named PROTON_LOG exists beside this script, Proton writes steam-<appid>.log here.
if [ -e "$HERE/PROTON_LOG" ]; then
  export PROTON_LOG=1 PROTON_LOG_DIR="$HERE"
  log "PROTON_LOG on -> $HERE/steam-*.log"
fi

# Frame rate overlay: a file DXVK_HUD beside this script holding e.g. fps,gpuload.
if [ -s "$HERE/DXVK_HUD" ]; then
  export DXVK_HUD="$(tr -d ' \n' < "$HERE/DXVK_HUD")"
  log "DXVK_HUD=$DXVK_HUD"
fi

for f in PANZERDG.EXE PANZERDG.INI PANZPAL.DAT PANZ_AVI.DLL PANZ_R1.DLL WAVE_00.CMP EXOPEN.AVI winmm.dll winmm.ini ddraw.dll dgVoodoo.conf Music/Track02.ogg Music/Track16.ogg; do
  [ -e "$HERE/game/$f" ] || log "WARNING: game/$f missing"
done

log "exec: $*"
exec "$@"
