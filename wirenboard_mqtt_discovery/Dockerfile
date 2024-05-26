ARG BUILD_FROM
FROM $BUILD_FROM

ENV PIP_CONSTRAINT="/tmp/constraint.txt"

COPY deps /tmp/

RUN apk add --no-cache python3 py3-pip \
  && python3 -m venv /opt/wirenboard_mqtt_discovery/.venv \
  && source /opt/wirenboard_mqtt_discovery/.venv/bin/activate \
  && pip3 install -r /tmp/requirements.txt \
  && rm -f -r /tmp/*

COPY src /opt/wirenboard_mqtt_discovery
COPY rootfs /
