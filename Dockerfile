FROM python:3.11

RUN python3 -m venv /app/autotorrent

ENV PATH=/app/autotorrent/bin/:$PATH
ENV HOME=/app/autotorrent
WORKDIR /app/autotorrent

RUN curl -sSL https://github.com/bcicen/tinycron/releases/download/v0.4/tinycron-0.4-linux-amd64 > /usr/local/bin/tinycron && chmod +x /usr/local/bin/tinycron

COPY ./docker-entrypoint.sh /opt/docker-entrypoint.sh
ENTRYPOINT ["/opt/docker-entrypoint.sh"]
COPY . /tmp/autotorrent/
RUN pip install --no-cache-dir /tmp/autotorrent/ && rm -r /tmp/autotorrent/

## Uncomment to install from pypi
# RUN /app/autotorrent/bin/pip install autotorrent2
