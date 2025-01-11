import asyncio
import json
import logging
import re

from json.decoder import JSONDecodeError

from base_connector import BaseConnector
from wb_entities import WbDevice, WbControl

logger = logging.getLogger(__name__)

class WbConnector(BaseConnector):
    _discovery_prefix = "homeassistant"
    _discovery_node_id = "wirenboard"

    _async_delay_sec = 1  # Delay before publishing to ensure that we got all device controls
    _cleanup_discovery_delay_sec = 5

    _subscribe_qos = 1

    _config_qos = 1
    _config_retain = True

    _availability_qos = 1
    _availability_retain = True

    @property
    def discovery_topic(self):
        return f'{self._discovery_prefix}/+/{self._discovery_node_id}/+/config'

    def __init__(self, broker_host, broker_port, username, password, client_id):
        super().__init__(broker_host, broker_port, username, password, client_id)

        self._devices = {}
        self._config_topics = {}

        topic_id_pattern = r"([-:\w\s()]+)"
        self._device_meta_topic_re = re.compile(r"/devices/" + topic_id_pattern + r"/meta")
        self._control_meta_topic_re = re.compile(r"/devices/" + topic_id_pattern + r"/controls/" + topic_id_pattern + r"/meta$")
        self._control_meta_error_topic_re = re.compile(r"/devices/" + topic_id_pattern + r"/controls/" + topic_id_pattern + r"/meta/error")
        self._discovery_topic_re = re.compile(self._discovery_prefix + r"/" + topic_id_pattern + r"/" + self._discovery_node_id + r"/" + topic_id_pattern + r"/config")
        self._async_tasks = {}

    def _on_connect(self, client):
        self._on_device_meta_change(client, 'buzzer', {'driver': 'system', 'title': {'en': 'WB Buzzer'}})
        self._on_device_meta_change(client, 'alarms', {'driver': 'system', 'title': {'en': 'WB Alarms'}})
        self._on_device_meta_change(client, 'hwmon', {'driver': 'system', 'title': {'en': 'WB HW Monitor'}})
        self._on_device_meta_change(client, 'metrics', {'driver': 'system', 'title': {'en': 'WB Metrics'}})
        self._on_device_meta_change(client, 'system', {'driver': 'system', 'title': {'en': 'WB System'}})
        self._on_device_meta_change(client, 'network', {'driver': 'system', 'title': {'en': 'WB Network'}})
        self._on_device_meta_change(client, 'power_status', {'driver': 'system', 'title': {'en': 'WB Power Status'}})
        self._on_device_meta_change(client, 'knx', {'driver': 'system', 'title': {'en': 'KNX'}})

        client.subscribe(self.discovery_topic, qos=self._subscribe_qos)
        self.subscribe_to_devices(client)

    def _on_message(self, client, topic, payload, qos, properties):
        # print(f'RECV MSG: {topic}', payload)
        payload = payload.decode("utf-8")
        discovery_topic_match = self._discovery_topic_re.match(topic)
        device_topic_match = self._device_meta_topic_re.match(topic)
        control_meta_topic_match = self._control_meta_topic_re.match(topic)
        control_meta_error_topic_match = self._control_meta_error_topic_re.match(topic)

        try:
            if discovery_topic_match:
                self._on_discovery_topic_change(client, discovery_topic_match.group(0))
            elif device_topic_match:
                self._on_device_meta_change(client, device_topic_match.group(1), json.loads(payload))
            elif control_meta_topic_match:
                self._on_control_meta_change(client, control_meta_topic_match.group(1), control_meta_topic_match.group(2), json.loads(payload))
            elif control_meta_error_topic_match:
                self._on_control_meta_error_change(control_meta_error_topic_match.group(1), control_meta_error_topic_match.group(2), payload)
            else:
                logger.warning(f"Mallformed topic: ({topic})")
        except JSONDecodeError as e:
            logger.warning(f'Mallformed JSON payload: {topic}, {payload}, {e}')

    def _on_discovery_topic_change(self, client, topic):
        # print(f'DISCOVERY: {topic}')
        if topic not in self._config_topics:
            self._config_topics[topic] = False
        self.subscribe_to_devices(client)

    def _on_device_meta_change(self, client, device_id, meta):
        # print(f'DEVICE: {device_id} / {meta}')
        if device_id not in self._devices:
            self._devices[device_id] = WbDevice(device_id)
            client.subscribe('/devices/' + device_id + '/controls/+/meta', qos=self._subscribe_qos)

        self._devices[device_id].meta = meta

    def _on_control_meta_change(self, client, device_id, control_id, meta):
        # print(f'CONTROL: {device_id} / {control_id} / {meta}')
        if device_id not in self._devices:
            logger.warning(f"Control '{control_id}' without device '{device_id}'.")
            return

        device = self._devices[device_id]

        if control_id not in device.controls:
            device.controls[control_id] = WbControl(control_id, device_id)
            client.subscribe('/devices/' + device_id + '/controls/' + control_id + '/meta/error', qos=self._subscribe_qos)

        device.controls[control_id].meta = meta

        self.publish_config(device_id)

    def _on_control_meta_error_change(self, device_id, control_id, meta):
        # print(f'ERROR: {device_id} / {control_id} / {meta}')
        if device_id not in self._devices:
            logger.warning(f"Error for '{control_id}' without device '{device_id}'.")
            return

        device = self._devices[device_id]

        if control_id not in device.controls:
            logger.warning(f"Error without device {device_id} / {control_id}'.")
            return

        self._publish_availability_sync(device_id, control_id, True if not meta else False)
        device.controls[control_id].availability_published = True

    def subscribe_to_devices(self, client):
        async def do_subscribe_to_devices():
            await asyncio.sleep(self._async_delay_sec)
            self._subscribe_to_devices_sync(client)

        self._run_task("_subscribe_to_devices_", do_subscribe_to_devices())

    def publish_config(self, device_id):
        async def do_publish_config():
            await asyncio.sleep(self._async_delay_sec)
            self._publish_config_sync(device_id)

        self._run_task(f"{device_id}_config", do_publish_config())

    def cleanup_discovery(self):
        async def do_cleanup_discovery():
            await asyncio.sleep(self._cleanup_discovery_delay_sec)
            self._cleanup_discovery_sync()

        self._run_task("_cleanup_discovery_", do_cleanup_discovery())

    def _run_task(self, task_id, task):
        loop = asyncio.get_event_loop()
        if task_id in self._async_tasks:
            self._async_tasks[task_id].cancel()
        self._async_tasks[task_id] = loop.create_task(task)

    def _subscribe_to_devices_sync(self, client):
        client.unsubscribe(self.discovery_topic)
        client.subscribe('/devices/+/meta', qos=self._subscribe_qos)

    def _publish_config_sync(self, device_id):
        if device_id not in self._devices:
            return

        device = self._devices[device_id]
        device_payload = device.config_payload()

        for control_id, control in device.ha_controls().items():
            for wb_entity in control.wb_entities:
                if not wb_entity.availability_published:
                    self._publish_availability_sync(device_id, wb_entity.id, True)

            control_payload = control.config_payload()
            control_payload['device'] = device_payload

            # Topic path: <discovery_topic>/<component>/[<node_id>/]<object_id>/config
            topic = self._discovery_prefix + '/' + control.type + '/' + self._discovery_node_id + '/' + control.ha_id + '/config'

            logger.info(f"[{device_id}/{control_id}] publish config to '{topic}'")
            self._publish(topic, json.dumps(control_payload), qos=self._config_qos, retain=self._config_retain)
            self._config_topics[topic] = True
        self.cleanup_discovery()

    def _cleanup_discovery_sync(self):
        for topic, presence in self._config_topics.items():
            if not presence:
                self._publish(topic, None, qos=self._config_qos, retain=self._config_retain)
                del self._config_topics[topic]

    def _publish_availability_sync(self, device_id, control_id, availability):
        payload = '1' if availability else '0'
        topic = '/devices/' + device_id + '/controls/' + control_id + '/availability'

        logger.info(f"[{device_id}/{control_id}] availability: {'online' if availability else 'offline'}")
        self._publish(topic, payload, qos=self._availability_qos, retain=self._availability_retain)
