"""
Support for the Polish Air Quality service (GIOS).

For more details about this platform, please refer to the documentation at
https://github.com/mgrom/sensor.giosaqi
"""
import asyncio
import logging
from datetime import timedelta

import aiohttp
import voluptuous as vol

from homeassistant.exceptions import PlatformNotReady
import homeassistant.helpers.config_validation as cv
from homeassistant.const import (
    ATTR_ATTRIBUTION, ATTR_TIME, ATTR_TEMPERATURE, CONF_TOKEN)
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.config_validation import PLATFORM_SCHEMA
from homeassistant.helpers.entity import Entity

REQUIREMENTS = ['giossync==0.0.3']

_LOGGER = logging.getLogger(__name__)

ATTR_NO2 = 'NO2'
ATTR_O3 = 'O3'
ATTR_PM10 = 'PM10'
ATTR_PM2_5 = 'PM2.5'
ATTR_SO2 = 'SO2'
ATTR_LAST_UPDATE = 'last_update'

KEY_TO_ATTR = {
    'PM2.5': ATTR_PM2_5,
    'PM10': ATTR_PM10,
    'O3': ATTR_O3,
    'NO2': ATTR_NO2,
    'SO2': ATTR_SO2,
}

ATTRIBUTION = 'Data provided by the Polish Air Quality service (GIOS).'

CONF_STATIONS = 'stations'

SCAN_INTERVAL = timedelta(minutes=1)

TIMEOUT = 10

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend({
    vol.Optional(CONF_STATIONS): cv.ensure_list,
})


async def async_setup_platform(hass, config, async_add_entities,
                               discovery_info=None):
    """Set up the requested Polish Air Quality service (GIOS) locations."""
    import giossync

    stations = config.get(CONF_STATIONS)

    client = giossync.GiosClient(async_get_clientsession(hass), timeout=TIMEOUT)
    dev = []
    try:
        for station in stations:
            rest_station_data = await client.get_location_data(station)
            if rest_station_data is not None:
                rest_sensors = await client.get_sensor_by_station_id(station)
                _LOGGER.debug("The following sensors were returned: %s", stations)
                for rest_sensor in rest_sensors:
                    gios_sensor = GiosSensor(client, rest_sensor, rest_station_data)
                    dev.append(gios_sensor)
    except (aiohttp.client_exceptions.ClientConnectorError,
            asyncio.TimeoutError):
        _LOGGER.exception('Failed to connect to GIOS servers.')
        raise PlatformNotReady
    async_add_entities(dev, True)


class GiosSensor(Entity):
    """Implementation of a GIOS sensor."""

    def __init__(self, client, sensor, station):
        """Initialize the sensor."""
        self._client = client
        try:
            self.uid = sensor['id']
        except (KeyError, TypeError):
            self.uid = None
        
        self.sensor = sensor
        self.station = station
        self._data = None

    @property
    def name(self):
        """Return the name of the sensor."""
        return self.station['stationName'] + ' ' + self.sensor['param']['paramCode']

    @property
    def icon(self):
        """Icon to use in the frontend, if any."""
        return 'mdi:cloud'

    @property
    def state(self):
        """Return the state of the device."""
        if self._data is not None:
            _LOGGER.debug("GIOS:Data %s", self._data)
            return round(self._data['value'],1)
        else:
            return None

    @property
    def unit_of_measurement(self):
        """Return the unit of measurement of this entity, if any."""
        return 'µg/m3'

    async def async_update(self):
        """Get the latest data and updates the states."""
        try:
            rest_sensor_data = await self._client.get_sensor_data(self.uid)
            if rest_sensor_data is not None:
                for data in rest_sensor_data['values']:
                    if data['value'] is not None:
                        self._data = data
                        break
            else:
                self._data = None
        except (aiohttp.client_exceptions.ClientConnectorError,
            asyncio.TimeoutError):
            _LOGGER.exception('Failed to connect to GIOS servers.')
            self._data = None
        _LOGGER.debug("Sensor data: %s", self._data)
        
