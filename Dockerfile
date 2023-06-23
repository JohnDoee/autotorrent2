FROM python:3.11

RUN python3 -m venv /app/autotorrent

ENV PATH=/app/autotorrent/bin/:$PATH
ENV HOME=/app/autotorrent
WORKDIR /app/autotorrent

COPY ./docker-entrypoint.sh /opt/docker-entrypoint.sh
ENTRYPOINT ["/opt/docker-entrypoint.sh"]
COPY . /tmp/autotorrent/
RUN pip install --no-cache-dir /tmp/autotorrent/ && rm -r /tmp/autotorrent/

## Uncomment to install from pypi
# RUN /app/autotorrent/bin/pip install autotorrent2
