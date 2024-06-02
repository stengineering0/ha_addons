import logging
import re
from collections import OrderedDict
from mappers import wiren_to_hass_type
from ha_entities import PrimitiveHaEntity, HaBrightnessLight

logger = logging.getLogger(__name__)

_unknown_types = []

class WbEntity:
    meta = None

    @staticmethod
    def _normalize_id(id):
        return re.sub(r'[^a-z0-9_]', '_', id.lower())

    def __init__(self, id):
        self.id = id

    def __str__(self) -> str:
        return f'{type(self).__name__} [{self.id}] {self.meta}'

class WbDevice(WbEntity):
    def __init__(self, id):
        super().__init__(id)
        self.ha_id = self._normalize_id(id)
        self._controls = {}

    @property
    def controls(self):
        return self._controls

    def config_payload(self):
        return {
            'name': self.name(),
            'identifiers': self.ha_id,
            'manufacturer': 'Wirenboard',
            'model': self.driver()
        }

    def name(self):
        return self.meta.get('title', {}).get('en') or self.driver()

    def driver(self):
        return self.meta.get('driver') or 'UNKNOWN'

    def ha_controls(self):
        res = self._basic_ha_controls(self.controls)
        self._compile_brightness_lights(res)
        return res

    @staticmethod
    def _basic_ha_controls(wb_controls):
        res = OrderedDict()
        for control_id in wb_controls:
            control = wb_controls[control_id]
            ha_type = wiren_to_hass_type(control)

            if not ha_type:
                continue

            res[control.id] = PrimitiveHaEntity.klass(ha_type)(control)
        return res

    @staticmethod
    def _compile_brightness_lights(ha_controls):
        lights = []
        brightness_re = re.compile(r"^(Channel \d+) Brightness$")

        for brightness_control_id, brightness_control in ha_controls.items():
            if not brightness_control.type == 'number':
                continue

            brightness_re_match = brightness_re.match(brightness_control_id)
            if not brightness_re_match:
                continue

            switch_control = ha_controls.get(brightness_re_match.group(1))
            if not switch_control or not switch_control.type == 'switch':
                continue

            light = HaBrightnessLight(switch_control, brightness_control)
            lights.append(light)

        for light in lights:
            ha_controls[light.ha_switch_control.id] = light
            del ha_controls[light.ha_brightness_control.id]

class WbControl(WbEntity):
    availability_published = False

    def __init__(self, id, device_id):
        super().__init__(id)
        self.device_id = device_id
        self.ha_id = self._normalize_id(f"{device_id}_{id}")

    def type(self):
        return self.meta.get('type')

    def readonly(self):
        return self.meta.get('readonly')

    def units(self):
        return self.meta.get('units')

    def min(self):
        return self.meta.get('min') or 0

    def max(self):
        return self.meta.get('max') or 10 ** 9

    def name(self):
        return self.id.replace("_", " ").title()
