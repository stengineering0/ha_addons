from mappers import WirenControlType, WIREN_DEVICE_CLASSES, WIREN_STATE_CLASSES, WIREN_UNITS_DICT

class HaEntity:
    @staticmethod
    def  get_control_topic(wb_entity):
        return f"/devices/{wb_entity.device_id}/controls/{wb_entity.id}"

    @property
    def ha_id(self):
        return self.main_wb_entity.ha_id

    @property
    def id(self):
        return self.main_wb_entity.id

    @classmethod
    def availability_payload(cls, wb_entity):
        return {
            'topic': f"{cls.get_control_topic(wb_entity)}/availability",
            'payload_available': '1',
            'payload_not_available': '0'
        }

    def config_payload(self):
        payload = {
            'name': self.main_wb_entity.name(),
            'unique_id': self.main_wb_entity.ha_id,
            'availability': list(map(self.availability_payload, self.wb_entities))
        }
        payload.update(self.custom_payload())
        filtered_payload = {k: v for k, v in payload.items() if v is not None}
        return filtered_payload


class PrimitiveHaEntity(HaEntity):
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
        elif type == 'text':
            return HaText

    def __init__(self, wb_entity):
        self.main_wb_entity = wb_entity

    @property
    def wb_entities(self):
        return [self.main_wb_entity]

    def  get_main_control_topic(self):
        return self.get_control_topic(self.main_wb_entity)

class HaBinarySensor(PrimitiveHaEntity):
    type = 'binary_sensor'

    def custom_payload(self):
        return {
            'payload_on': '1',
            'payload_off': '0',
            'state_topic': self.get_main_control_topic(),
        }

class HaButton(PrimitiveHaEntity):
    type = 'button'

    def custom_payload(self):
        return {
            'command_topic': self.get_main_control_topic(),
            'payload_press': '1',
        }

class HaSensor(PrimitiveHaEntity):
    type = 'sensor'

    def __init__(self, wb_entity):
        super().__init__(wb_entity)
        self.wb_type = WirenControlType(wb_entity.type())

    def device_class(self):
        origin_units = self.main_wb_entity.units()

        if self.wb_type == WirenControlType.value:
            if origin_units == '°C':
                return 'temperature'
            elif origin_units == 'ppb':
                return 'volatile_organic_compounds_parts'

        return WIREN_DEVICE_CLASSES.get(self.wb_type)

    def state_class(self):
        return WIREN_STATE_CLASSES.get(self.wb_type)

    def units(self):
        return WIREN_UNITS_DICT.get(self.wb_type) or self.main_wb_entity.units()

    def precision(self):
        if self.device_class() == 'temperature':
            return 1

    def precision_template(self):
        precision = self.precision()
        if precision is not None:
            return f"{{{{ float(value) | round({precision}) }}}}"

    def custom_payload(self):
        return {
            'device_class': self.device_class(),
            'state_class': self.state_class(),
            'unit_of_measurement': self.units(),
            'suggested_display_precision': self.precision(),
            'value_template': self.precision_template(),
            'state_topic': self.get_main_control_topic(),
        }

class HaSwitch(PrimitiveHaEntity):
    type = 'switch'

    def custom_payload(self):
        return {
            'payload_on': '1',
            'payload_off': '0',
            'state_on': '1',
            'state_off': '0',
            'state_topic': self.get_main_control_topic(),
            'command_topic': f"{self.get_main_control_topic()}/on",
        }

class HaNumber(PrimitiveHaEntity):
    type = 'number'

    def custom_payload(self):
        return {
            'min': self.main_wb_entity.min(),
            'max': self.main_wb_entity.max(),
            'mode': 'slider',
            'state_topic': self.get_main_control_topic(),
            'command_topic': f"{self.get_main_control_topic()}/on",
        }

class HaText(PrimitiveHaEntity):
    type = 'text'

    def custom_payload(self):
        return {
            'state_topic': self.get_main_control_topic(),
            'command_topic': f"{self.get_main_control_topic()}/on",
        }

class HaBrightnessLight(HaEntity):
    type = 'light'

    def __init__(self, ha_switch_control, ha_brightness_control):
        self.ha_switch_control = ha_switch_control
        self.ha_brightness_control = ha_brightness_control

    @property
    def main_wb_entity(self):
        return self.ha_switch_control.main_wb_entity

    @property
    def wb_entities(self):
        return [self.ha_switch_control.main_wb_entity, self.ha_brightness_control.main_wb_entity]

    def custom_payload(self):
        return {
            'state_topic': self.ha_switch_control.get_main_control_topic(),
            'command_topic': f"{self.ha_switch_control.get_main_control_topic()}/on",
            'brightness_state_topic': self.ha_brightness_control.get_main_control_topic(),
            'brightness_command_topic': f"{self.ha_brightness_control.get_main_control_topic()}/on",
            'brightness_scale': self.ha_brightness_control.main_wb_entity.max(),
            'payload_on': '1',
            'payload_off': '0'
        }
