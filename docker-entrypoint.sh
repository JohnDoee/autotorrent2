#!/bin/bash
if [[ -n "$PUID" && -n "$PGID" ]]; then
  groupadd -g "$PGID" autotorrent
  useradd -u "$PUID" -g "$PGID" -M -d /app/autotorrent autotorrent
  echo at2 "$@" | su autotorrent
else
  at2 "$@"
fi
