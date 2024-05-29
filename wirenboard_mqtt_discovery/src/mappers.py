import logging
from enum import unique, Enum

logger = logging.getLogger(__name__)


@unique
class WirenControlType(Enum):
    """
    Wirenboard controls types
    Based on https://github.com/wirenboard/homeui/blob/master/conventions.md
    """
    # generic types
    switch = "switch"
    alarm = "alarm"
    pushbutton = "pushbutton"
    range = "range"
    rgb = "rgb"
    text = "text"
    value = "value"

    # special types
    temperature = "temperature"
    rel_humidity = "rel_humidity"
    atmospheric_pressure = "atmospheric_pressure"
    rainfall = "rainfall"
    wind_speed = "wind_speed"
    power = "power"
    power_consumption = "power_consumption"
    voltage = "voltage"
    water_flow = "water_flow"
    water_consumption = "water_consumption"
    resistance = "resistance"
    concentration = "concentration"
    heat_power = "heat_power"
    heat_energy = "heat_energy"
    lux = "lux"
    sound_level = "sound_level"

    # custom types
    current = "current"

WIREN_DEVICE_CLASSES = {
    WirenControlType.temperature: 'temperature',
    WirenControlType.rel_humidity: 'humidity',
    WirenControlType.atmospheric_pressure: 'atmospheric_pressure',
    WirenControlType.rainfall: 'precipitation_intensity',
    WirenControlType.wind_speed: 'wind_speed',
    WirenControlType.power: 'power',
    WirenControlType.power_consumption: 'energy',
    WirenControlType.voltage: 'voltage',
    WirenControlType.water_flow: 'volume_flow_rate',
    WirenControlType.water_consumption: 'water',
    WirenControlType.concentration: 'carbon_dioxide',
    WirenControlType.lux: 'illuminance',
    WirenControlType.sound_level: 'sound_pressure',
}

WIREN_UNITS_DICT = {
    WirenControlType.temperature: '°C',
    WirenControlType.rel_humidity: '%',
    WirenControlType.atmospheric_pressure: 'mbar',
    WirenControlType.rainfall: 'mm/h',
    WirenControlType.wind_speed: 'm/s',
    WirenControlType.power: 'W',
    WirenControlType.power_consumption: 'kWh',
    WirenControlType.voltage: 'V',
    WirenControlType.water_flow: 'm³/h',
    WirenControlType.water_consumption: 'm³',
    WirenControlType.resistance: 'Ohm',
    WirenControlType.concentration: 'ppm',
    WirenControlType.heat_power: 'Gcal/hour',
    WirenControlType.heat_energy: 'Gcal',
    WirenControlType.lux: 'lx',
    WirenControlType.sound_level: 'dB',

    WirenControlType.current: 'A',
}

_WIREN_TO_HASS_MAPPER = {
    WirenControlType.switch: None,  # see wirenboard_to_hass_type()
    WirenControlType.alarm: 'binary_sensor',
    WirenControlType.pushbutton: 'button',
    WirenControlType.range: None,  # see wirenboard_to_hass_type()
    # WirenControlType.rgb: 'light', #TODO: add
    WirenControlType.text: 'sensor',
    WirenControlType.value: 'sensor',

    WirenControlType.temperature: 'sensor',
    WirenControlType.rel_humidity: 'sensor',
    WirenControlType.atmospheric_pressure: 'sensor',
    WirenControlType.rainfall: 'sensor',
    WirenControlType.wind_speed: 'sensor',
    WirenControlType.power: 'sensor',
    WirenControlType.power_consumption: 'sensor',
    WirenControlType.voltage: 'sensor',
    WirenControlType.water_flow: 'sensor',
    WirenControlType.water_consumption: 'sensor',
    WirenControlType.resistance: 'sensor',
    WirenControlType.concentration: 'sensor',
    WirenControlType.heat_power: 'sensor',
    WirenControlType.heat_energy: 'sensor',
    WirenControlType.lux: 'sensor',
    WirenControlType.sound_level: 'sensor',

    WirenControlType.current: 'sensor',
}


def wiren_to_hass_type(control):
    if control.type == WirenControlType.switch:
        return 'binary_sensor' if control.read_only else 'switch'
    elif control.type == WirenControlType.range:
        return 'sensor' if control.read_only else 'number'
        return 'sensor' if control.read_only else None
    elif control.type in _WIREN_TO_HASS_MAPPER:
        return _WIREN_TO_HASS_MAPPER[control.type]
    return None


_unknown_types = []


def apply_payload_for_component(payload, device, control, control_topic, inverse: bool):
    hass_entity_type = wiren_to_hass_type(control)

    if inverse:
        _payload_on = '0'
        _payload_off = '1'
    else:
        _payload_on = '1'
        _payload_off = '0'

    if hass_entity_type == 'switch':
        payload.update({
            'payload_on': _payload_on,
            'payload_off': _payload_off,
            'state_on': _payload_on,
            'state_off': _payload_off,
            'state_topic': f"{control_topic}",
            'command_topic': f"{control_topic}/on",
        })
    elif hass_entity_type == 'binary_sensor':
        payload.update({
            'payload_on': _payload_on,
            'payload_off': _payload_off,
            'state_topic': f"{control_topic}",
        })
    elif hass_entity_type == 'button':
        payload.update({
            'command_topic': f"{control_topic}",
            'payload_press': '1',
        })
    elif hass_entity_type == 'number':
        min = control.min
        if not min:
            min = 0

        max = control.max
        if not max:
            max = 10 ** 9

        payload.update({
            'min': min,
            'max': max,
            'mode': 'slider',
            'state_topic': f"{control_topic}",
            'command_topic': f"{control_topic}/on",
        })
    elif hass_entity_type == 'sensor':
        payload.update({
            'state_topic': f"{control_topic}",
        })
        if control.device_class:
            payload['device_class'] = control.device_class
        if control.units:
            payload['unit_of_measurement'] = control.units
    else:
        if not hass_entity_type in _unknown_types:
            logger.warning(f"No algorithm for hass type '{control.type.name}', hass: '{hass_entity_type}'")
            _unknown_types.append(hass_entity_type)
        return None

    return hass_entity_type
