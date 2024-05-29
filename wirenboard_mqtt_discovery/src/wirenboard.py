import asyncio
import json
import logging
import re

from base_connector import BaseConnector
from mappers import WirenControlType, apply_payload_for_component, WIREN_DEVICE_CLASSES, WIREN_UNITS_DICT
from wirenboard_registry import WirenBoardDeviceRegistry, WirenDevice, WirenControl

logger = logging.getLogger(__name__)


class WirenConnector(BaseConnector):
    _publish_delay_sec = 1  # Delay before publishing to ensure that we got all meta topics
    _subscribe_qos = 1
    _availability_qos = 0
    _availability_retain = True
    _config_qos = 0
    _config_retain = False
    _ignore_availability = False
    _discovery_prefix = "homeassistant"

    def __init__(self, broker_host, broker_port, username, password, client_id, topic_prefix):
        super().__init__(broker_host, broker_port, username, password, client_id)

        self._topic_prefix = topic_prefix

        self._device_meta_topic_re = re.compile(self._topic_prefix + r"/devices/([^/]*)/meta/([^/]*)")
        self._control_meta_topic_re = re.compile(self._topic_prefix + r"/devices/([^/]*)/controls/([^/]*)/meta/([^/]*)")
        self._unknown_types = []
        self._async_tasks = {}
        self._component_types = {}
        self._inverse = []

    @staticmethod
    def _on_device_meta_change(device_id, meta_name, meta_value):
        device = WirenBoardDeviceRegistry().get_device(device_id)
        if meta_name == 'name':
            device.name = meta_value
        elif meta_name == 'driver':
            device.model = meta_value
        # print(f'DEVICE: {device_id} / {meta_name} ==> {meta_value}')

    def _on_control_meta_change(self, device_id, control_id, meta_name, meta_value):
        device = WirenBoardDeviceRegistry().get_device(device_id)
        control = device.get_control(control_id)

        # print(f'CONTROL: {device_id} / {control_id} / {meta_name} ==> {meta_value}')
        if meta_name == 'error':
            # publish availability separately. do not publish all device
            if control.apply_error(False if not meta_value else True):
                self.publish_availability(device, control)
        else:
            has_changes = False

            if control.error is None:
                # We assume that there is no error by default
                control.error = False
                has_changes = True

            if meta_name == 'order':
                return  # Ignore
            elif meta_name == 'type':
                try:
                    has_changes |= control.apply_type(WirenControlType(meta_value))
                    if control.type in WIREN_DEVICE_CLASSES:
                        has_changes |= control.apply_device_class(WIREN_DEVICE_CLASSES[control.type])
                    if control.type in WIREN_UNITS_DICT:
                        has_changes |= control.apply_units(WIREN_UNITS_DICT[control.type])
                except ValueError:
                    if not meta_value in self._unknown_types:
                        logger.warning(f'Unknown type for wirenboard control: {meta_value}')
                        self._unknown_types.append(meta_value)
            elif meta_name == 'readonly':
                has_changes |= control.apply_read_only(True if meta_value == '1' else False)
            elif meta_name == 'units':
                has_changes |= control.apply_units(meta_value)
            elif meta_name == 'min':
                has_changes |= control.apply_min(int(meta_value) if meta_value else None)
            elif meta_name == 'max':
                has_changes |= control.apply_max(int(meta_value) if meta_value else None)
            if has_changes:
                self.publish_config(device, control)

    def _on_connect(self, client):
        client.subscribe(self._topic_prefix + '/devices/+/meta/+', qos=self._subscribe_qos)
        client.subscribe(self._topic_prefix + '/devices/+/controls/+/meta/+', qos=self._subscribe_qos)

    def _on_message(self, client, topic, payload, qos, properties):
        # print(f'RECV MSG: {topic}', payload)
        payload = payload.decode("utf-8")
        device_topic_match = self._device_meta_topic_re.match(topic)
        control_meta_topic_match = self._control_meta_topic_re.match(topic)
        if device_topic_match:
            self._on_device_meta_change(device_topic_match.group(1), device_topic_match.group(2), payload)
        elif control_meta_topic_match:
            self._on_control_meta_change(control_meta_topic_match.group(1), control_meta_topic_match.group(2), control_meta_topic_match.group(3), payload)

    ##################################
    # Migrated from homeassistant.py #
    ##################################

    def publish_availability(self, device: WirenDevice, control: WirenControl):
        if self._ignore_availability:
            return

        async def publish_availability():
            await asyncio.sleep(self._publish_delay_sec)
            self._publish_availability_sync(device, control)

        self._run_task(f"{device.id}_{control.id}_availability", publish_availability())

    def _publish_availability_sync(self, device: WirenDevice, control: WirenControl):
        if self._ignore_availability:
            return

        topic = self._get_availability_topic(device, control)
        payload = '1' if not control.error else '0'
        logger.info(f"[{device.debug_id}/{control.debug_id}] availability: {'online' if control.state else 'offline'}")
        self._publish(topic, payload, qos=self._availability_qos, retain=self._availability_retain)

    def publish_config(self, device: WirenDevice, control: WirenControl):
        async def do_publish_config():
            await asyncio.sleep(self._publish_delay_sec)
            self._publish_config_sync(device, control)

            # Publish availability and state every time after publishing config
            self._publish_availability_sync(device, control)

        self._run_task(f"{device.id}_{control.id}_config", do_publish_config())

    def _run_task(self, task_id, task):
        loop = asyncio.get_event_loop()
        if task_id in self._async_tasks:
            self._async_tasks[task_id].cancel()
        self._async_tasks[task_id] = loop.create_task(task)

    def _get_availability_topic(self, device: WirenDevice, control: WirenControl):
        return f"{self._get_control_topic(device, control)}/availability"

    def _get_control_topic(self, device: WirenDevice, control: WirenControl):
        return f"{self._topic_prefix}/devices/{device.id}/controls/{control.id}"

    @staticmethod
    def _normalize_id(identifier):
        return re.sub(r'[^a-z0-9_]', '_', identifier.lower())

    def _publish_config_sync(self, device: WirenDevice, control: WirenControl):
        """
        Publish discovery topic to the HA
        """

        if WirenBoardDeviceRegistry().is_local_device(device):
            device_unique_id = 'wirenboard'
            device_name = 'Wirenboard'
        else:
            device_unique_id = device.id
            device_name = device.name

        if not device_name:
            device_name = device.id

        device_unique_id = self._normalize_id(device_unique_id)

        entity_unique_id = self._normalize_id(f"{device.id}_{control.id}")
        object_id = self._normalize_id(f"{control.id}")
        entity_name = f"{device.id} {control.id}".replace("_", " ").title()

        node_id = device_unique_id

        device_model = device.model
        if not device_model:
            device_model = 'UNKNOWN'

        # common payload
        payload = {
            'device': {
                'name': device_name,
                'identifiers': device_unique_id,
                'manufacturer': 'Wirenboard',
                'model': device_model
            },
            'name': entity_name,
            'unique_id': entity_unique_id
        }

        if not self._ignore_availability:
            payload['availability_topic'] = self._get_availability_topic(device, control);
            payload['payload_available'] = "1"
            payload['payload_not_available'] = "0"

        inverse = entity_unique_id in self._inverse

        control_topic = self._get_control_topic(device, control)
        component = apply_payload_for_component(payload, device, control, control_topic, inverse=inverse)
        self._component_types[control.id] = component

        if not component:
            return

        # Topic path: <discovery_topic>/<component>/[<node_id>/]<object_id>/config
        topic = self._discovery_prefix + '/' + component + '/' + node_id + '/' + object_id + '/config'
        logger.info(f"[{device.debug_id}/{control.debug_id}] publish config to '{topic}'")
        self._publish(topic, json.dumps(payload), qos=self._config_qos, retain=self._config_retain)
