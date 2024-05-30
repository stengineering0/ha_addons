import logging
from enum import unique, Enum

logger = logging.getLogger(__name__)


@unique
class WirenControlType(Enum):
    """
    Wirenboard controls types
    Based on https://github.com/wirenboard/conventions/blob/main/README.md
    """
    # generic types
    switch = "switch"
    alarm = "alarm"
    pushbutton = "pushbutton"
    range = "range"
    # rgb = "rgb"
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
}

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
}

_unknown_types = []

def wiren_to_hass_type(wb_control):
    try:
        wb_control_type = WirenControlType(wb_control.type())

        if wb_control_type == WirenControlType.switch:
            return 'binary_sensor' if wb_control.readonly() else 'switch'
        elif wb_control_type == WirenControlType.range:
            return 'sensor' if wb_control.readonly() else 'number'
        else:
            return _WIREN_TO_HASS_MAPPER[wb_control_type]
    except ValueError:
        if not wb_control.type() in _unknown_types:
            logger.warning(f"Unknown WB type '{wb_control.type()}'")
            _unknown_types.append(wb_control.type())
