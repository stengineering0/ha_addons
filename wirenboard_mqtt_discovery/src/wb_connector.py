import asyncio
import json
import logging
import re

from base_connector import BaseConnector
from wb_entities import WbDevice, WbControl

logger = logging.getLogger(__name__)


class WbConnector(BaseConnector):
    _discovery_prefix = "homeassistant"

    _subscribe_qos = 1

    _publish_delay_sec = 1  # Delay before publishing to ensure that we got all device controls
    _config_qos = 0
    _config_retain = False

    def __init__(self, broker_host, broker_port, username, password, client_id):
        super().__init__(broker_host, broker_port, username, password, client_id)

        self._devices = {}

        self._device_meta_topic_re = re.compile(r"/devices/([^/]*)/meta")
        self._control_meta_topic_re = re.compile(r"/devices/([^/]*)/controls/([^/]*)/meta")
        self._async_tasks = {}

    def _on_connect(self, client):
        client.subscribe('/devices/+/meta', qos=self._subscribe_qos)

    def _on_message(self, client, topic, payload, qos, properties):
        # print(f'RECV MSG: {topic}', payload)
        payload = payload.decode("utf-8")
        device_topic_match = self._device_meta_topic_re.match(topic)
        control_meta_topic_match = self._control_meta_topic_re.match(topic)
        if device_topic_match:
            self._on_device_meta_change(client, device_topic_match.group(1), payload)
        elif control_meta_topic_match:
            self._on_control_meta_change(control_meta_topic_match.group(1), control_meta_topic_match.group(2), payload)

    def _on_device_meta_change(self, client, device_id, meta):
        # print(f'DEVICE: {device_id} / {meta}')
        if device_id not in self._devices:
            self._devices[device_id] = WbDevice(device_id)
            client.subscribe('/devices/' + device_id + '/controls/+/meta', qos=self._subscribe_qos)

        self._devices[device_id].meta = json.loads(meta)

    def _on_control_meta_change(self, device_id, control_id, meta):
        # print(f'CONTROL: {device_id} / {control_id} / {meta}')
        if device_id not in self._devices:
            return

        device = self._devices[device_id]

        if control_id not in device.controls:
            device.controls[control_id] = WbControl(control_id, device_id)

        device.controls[control_id].meta = json.loads(meta)

        self.publish_config(device_id)

    def publish_config(self, device_id):
        async def do_publish_config():
            await asyncio.sleep(self._publish_delay_sec)
            self._publish_config_sync(device_id)

        self._run_task(f"{device_id}_config", do_publish_config())

    def _run_task(self, task_id, task):
        loop = asyncio.get_event_loop()
        if task_id in self._async_tasks:
            self._async_tasks[task_id].cancel()
        self._async_tasks[task_id] = loop.create_task(task)

    def _publish_config_sync(self, device_id):
        """
        Publish discovery topic to the HA
        """

        if device_id not in self._devices:
            return

        device = self._devices[device_id]
        device_payload = device.config_payload()


        for control in device.ha_controls():
            control_payload = control.config_payload()
            control_payload['device'] = device_payload

            # Topic path: <discovery_topic>/<component>/[<node_id>/]<object_id>/config
            topic = self._discovery_prefix + '/' + control.type + '/' + device.ha_id + '/' + control.ha_id + '/config'

            logger.info(f"[{device.id}/{control.id}] publish config to '{topic}'")
            self._publish(topic, json.dumps(control_payload), qos=self._config_qos, retain=self._config_retain)