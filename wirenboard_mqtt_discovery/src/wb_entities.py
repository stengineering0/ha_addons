import logging
import re
from mappers import wiren_to_hass_type
from ha_entities import HaEntity

logger = logging.getLogger(__name__)

_unknown_types = []

class WbEntity:
    meta = None

    @staticmethod
    def _normalize_id(id):
        return re.sub(r'[^a-z0-9_]', '_', id.lower())

    def __init__(self, id):
        self.id = id
        self.ha_id = self._normalize_id(id)

    def __str__(self) -> str:
        return f'{type(self).__name__} [{self.id}] {self.meta}'

class WbDevice(WbEntity):
    def __init__(self, id):
        super().__init__(id)
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
        res = []

        for control_id in self.controls:
            control = self.controls[control_id]
            ha_type = wiren_to_hass_type(control)

            if not ha_type:
                continue

            res.append(HaEntity.klass(ha_type)(control))
        return res

class WbControl(WbEntity):
    def __init__(self, id, device_id):
        super().__init__(id)
        self.device_id = device_id

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
        return f"{self.device_id} {self.id}".replace("_", " ").title()

    def unique_id(self):
         return self._normalize_id(f"{self.device_id}_{self.id}")


#     def apply_units(self, units):
#         if units == 'MiB':
#             has_changes = self.apply_units('MB')
#             has_changes |= self.apply_device_class('data_size')
#             return has_changes
#

#         if WirenBoardDeviceRegistry().is_local_device(device):
#             device_unique_id = 'wirenboard'
#             device_name = 'Wirenboard'

# class WirenBoardDeviceRegistry:
#     _devices = {}
#
#     local_device_id = 'wirenboard'
#     local_device_name = 'Wirenboard'
#     _local_devices = ('wb-adc', 'wbrules', 'wb-gpio', 'power_status', 'network', 'system', 'hwmon', 'buzzer', 'alarms')
#
#     def is_local_device(self, device):
#         return device.id in self._local_devices
