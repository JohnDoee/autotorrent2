#!/bin/bash
if [[ -n "$PUID" && -n "$PGID" ]]; then
  groupadd -g "$PGID" autotorrent
  useradd -u "$PUID" -g "$PGID" -M -d /app/autotorrent autotorrent
  if [[ "$1" == "cron" ]]; then
    SCHEDULE="$2"
    shift 2
    echo /usr/local/bin/tinycron "$SCHEDULE" at2 "$@" | su autotorrent
  else
    echo at2 "$@" | su autotorrent
  fi
else
  if [[ "$1" == "cron" ]]; then
    SCHEDULE="$2"
    shift 2
    /usr/local/bin/tinycron "$SCHEDULE" at2 "$@"
  else
    at2 "$@"
  fi
fi
