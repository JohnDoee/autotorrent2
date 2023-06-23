#!/bin/bash
if [[ -n "$PUID" && -n "$PGID" ]]; then
  groupadd -g "$PGID" autotorrent
  useradd -u "$PUID" -g "$PGID" -M -d /app/autotorrent autotorrent
  if [[ "$1" == "cron" ]]; then
    SCHEDULE="$2"
    shift 2
    echo -e '#!/bin/bash\nat2 '"$*" > /var/tmp/cron.sh
    chmod +x /var/tmp/cron.sh
    echo /usr/local/bin/tinycron "$SCHEDULE" /var/tmp/cron.sh | su autotorrent
  else
    echo at2 "$@" | su autotorrent
  fi
else
  if [[ "$1" == "cron" ]]; then
    SCHEDULE="$2"
    shift 2
    echo -e '#!/bin/bash\nat2 '"$*" > /var/tmp/cron.sh
    chmod +x /var/tmp/cron.sh
    /usr/local/bin/tinycron "$SCHEDULE" /var/tmp/cron.sh
  else
    at2 "$@"
  fi
fi
