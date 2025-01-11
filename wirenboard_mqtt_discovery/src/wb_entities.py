import logging
import re
from collections import OrderedDict
from mappers import wiren_to_hass_type
from ha_entities import PrimitiveHaEntity, HaGRBLight, Ha1ChannelLight

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
        self._compile_rgb_lights(res)
        self._compile_1_channel_lights(res)
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
    def _compile_rgb_lights(ha_controls):
        switch_control = ha_controls.get('RGB Strip')
        brightness_control = ha_controls.get('RGB Strip Brightness')
        palette_control = ha_controls.get('RGB Palette')

        if not switch_control or not brightness_control or not palette_control:
            return

        light = HaGRBLight(switch_control, brightness_control, palette_control)

        ha_controls[light.ha_switch_control.id] = light
        del ha_controls[light.ha_brightness_control.id]
        del ha_controls[light.ha_palette_control.id]

    @staticmethod
    def _compile_1_channel_lights(ha_controls):
        lights = []
        brightness_re1 = re.compile(r"^(Channel \d+) Brightness$")
        brightness_re2 = re.compile(r"^Channel (\d+)$")

        for brightness_control_id, brightness_control in ha_controls.items():
            switch_control = None

            if not brightness_control.type == 'number':
                continue

            brightness_re_match1 = brightness_re1.match(brightness_control_id)
            brightness_re_match2 = brightness_re2.match(brightness_control_id)

            if brightness_re_match1:
                switch_control = ha_controls.get(brightness_re_match1.group(1))
            elif brightness_re_match2:
                switch_control = ha_controls.get('K' + brightness_re_match2.group(1))

            if not switch_control or not switch_control.type == 'switch':
                continue

            light = Ha1ChannelLight(switch_control, brightness_control)
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
        origin_units = self.meta.get('units')
        if origin_units == 'deg C':
            return '°C'

        return origin_units

    def min(self):
        return self.meta.get('min') or 0

    def max(self):
        return self.meta.get('max') or 10 ** 9

    def name(self):
        return self.id.replace("_", " ").title()
