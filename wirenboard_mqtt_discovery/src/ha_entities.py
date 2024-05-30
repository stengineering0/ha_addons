from mappers import WirenControlType, WIREN_DEVICE_CLASSES, WIREN_UNITS_DICT

class HaEntity:
    def __init__(self, wb_entity):
        self.wb_entity = wb_entity
        self.wb_type = WirenControlType(wb_entity.type())

    @staticmethod
    def klass(type):
        if type == 'binary_sensor':
            return HaBinarySensor
        elif type == 'button':
            return HaButton
        elif type == 'sensor':
            return HaSensor
        elif type == 'switch':
            return HaSwitch
        elif type == 'number':
            return HaNumber

    def  _get_control_topic(self):
        return f"/devices/{self.wb_entity.device_id}/controls/{self.wb_entity.id}"

    def device_class(self):
        return WIREN_DEVICE_CLASSES.get(self.wb_type)

    def units(self):
        return WIREN_UNITS_DICT.get(self.wb_type) or self.wb_entity.units()

    def config_payload(self):
        payload = {
            'name': self.wb_entity.name(),
            'unique_id': self.wb_entity.unique_id(),
            # 'availability_topic': f"{self._get_control_topic()}/error",
            # 'availability_template': '{{ iif(value == None, "1", "0") }}',
            # 'payload_available': '',
            # 'payload_not_available': 'r'
        }
        payload.update(self.custom_payload())

        return payload

    @property
    def ha_id(self):
        return self.wb_entity.ha_id

    @property
    def id(self):
        return self.wb_entity.id

class HaBinarySensor(HaEntity):
    type = 'binary_sensor'

    def custom_payload(self):
        return {
            'payload_on': '1',
            'payload_off': '0',
            'state_topic': self._get_control_topic(),
        }

class HaButton(HaEntity):
    type = 'button'

    def custom_payload(self):
        return {
            'command_topic': self._get_control_topic(),
            'payload_press': '1',
        }

class HaSensor(HaEntity):
    type = 'sensor'

    def custom_payload(self):
        return {
            'device_class': self.device_class(),
            'unit_of_measurement': self.units(),
            'state_topic': self._get_control_topic(),
        }

class HaSwitch(HaEntity):
    type = 'switch'

    def custom_payload(self):
        return {
            'payload_on': '1',
            'payload_off': '0',
            'state_on': '1',
            'state_off': '0',
            'state_topic': self._get_control_topic(),
            'command_topic': f"{self._get_control_topic()}/on",
        }

class HaNumber(HaEntity):
    type = 'number'

    def custom_payload(self):
        return {
            'min': self.wb_entity.min(),
            'max': self.wb_entity.max(),
            'mode': 'slider',
            'state_topic': self._get_control_topic(),
            'command_topic': f"{self._get_control_topic()}/on",
        }
