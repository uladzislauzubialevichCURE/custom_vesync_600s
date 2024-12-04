"""Support for VeSync humidifiers."""
from __future__ import annotations

from collections.abc import Mapping
import logging
from typing import Any

from homeassistant.components.humidifier import HumidifierEntity
from homeassistant.components.humidifier.const import (
    MODE_AUTO,
    MODE_NORMAL,
    MODE_SLEEP,
    HumidifierEntityFeature,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.dispatcher import async_dispatcher_connect
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .common import VeSyncDevice
from .const import (
    DOMAIN,
    VS_DISCOVERY,
    VS_HUMIDIFIERS,
    VS_MODE_AUTO,
    VS_MODE_HUMIDITY,
    VS_MODE_MANUAL,
    VS_MODE_SLEEP,
)

_LOGGER = logging.getLogger(__name__)

MAX_HUMIDITY = 80
MIN_HUMIDITY = 30

VS_TO_HA_MODE_MAP = {
    VS_MODE_AUTO: MODE_AUTO,
    VS_MODE_HUMIDITY: MODE_AUTO,
    VS_MODE_MANUAL: MODE_NORMAL,
    VS_MODE_SLEEP: MODE_SLEEP,
}

HA_TO_VS_MODE_MAP = {v: k for k, v in VS_TO_HA_MODE_MAP.items()}

async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up the VeSync humidifier platform."""
    coordinator = hass.data[DOMAIN][config_entry.entry_id]["coordinator"]

    @callback
    def discover(devices):
        """Add new devices to platform."""
        _setup_entities(devices, async_add_entities, coordinator)

    config_entry.async_on_unload(
        async_dispatcher_connect(hass, VS_DISCOVERY.format(VS_HUMIDIFIERS), discover)
    )

    _setup_entities(
        hass.data[DOMAIN][config_entry.entry_id][VS_HUMIDIFIERS],
        async_add_entities,
        coordinator,
    )

@callback
def _setup_entities(devices, async_add_entities, coordinator):
    """Check if device is online and add entity."""
    entities = []
    for dev in devices:
        if dev.device_type in ["LEH-S601S-WUS"]:
            entities.append(VeSyncHumidifier600SHA(dev, coordinator))
    async_add_entities(entities, update_before_add=True)

class VeSyncHumidifier600SHA(VeSyncDevice, HumidifierEntity):
   """Representation of a VeSync 600S humidifier."""

   _attr_max_humidity = MAX_HUMIDITY
   _attr_min_humidity = MIN_HUMIDITY

   def __init__(self, humidifier, coordinator) -> None:
       """Initialize the VeSync 600S humidifier."""
       super().__init__(humidifier, coordinator)
       self.smarthumidifier = humidifier

   @property
   def supported_features(self) -> int:
       """Return supported features."""
       return HumidifierEntityFeature.MODES

   @property
   def available_modes(self) -> list[str]:
       """Return available modes."""
       modes = []
       if "mist_modes" in self.smarthumidifier._config_dict:
           modes = self.smarthumidifier._config_dict["mist_modes"]
       return modes

   @property
   def target_humidity(self) -> int:
       """Return the target humidity."""
       return self.smarthumidifier.details.get("target_humidity", 45)

   @property
   def mode(self) -> str | None:
       """Return current mode."""
       current_mode = self.smarthumidifier.details.get("mode", "manual")
       if current_mode == "humidity":
           return MODE_AUTO
       elif current_mode == "sleep":
           return MODE_SLEEP
       return MODE_NORMAL

   @property
   def is_on(self) -> bool:
       """Return True if humidifier is on."""
       return self.smarthumidifier.device_status == "on"

   @property
   def unique_info(self) -> str:
       """Return unique info for this device."""
       return self.smarthumidifier.uuid

   @property
   def extra_state_attributes(self) -> Mapping[str, Any]:
       """Return the state attributes of the humidifier."""
       attr = {}
       details = self.smarthumidifier.details
       attr.update({
           "mist_level": details.get("mist_level", 1),
           "mist_virtual_level": details.get("mist_virtual_level", 1),
           "water_lacks": details.get("water_lacks", False),
           "water_tank_lifted": details.get("water_tank_lifted", False),
           "filter_life_percentage": details.get("filter_life_percentage", 100),
           "temperature": details.get("temperature", 0),
           "display": details.get("display", True),
           "humidity": details.get("humidity", 0),
           "drying_mode": details.get("drying_mode", {})
       })
       return attr

   async def async_set_humidity(self, humidity: int) -> None:
       """Set the target humidity."""
       result = await self.hass.async_add_executor_job(
           self.smarthumidifier.set_target_humidity, humidity
       )
       if result:
           self.async_write_ha_state()

   async def async_set_mode(self, mode: str) -> None:
       """Set humidifier mode."""
       vs_mode = mode.lower()
       if vs_mode == MODE_AUTO:
           vs_mode = "humidity"
       result = await self.hass.async_add_executor_job(
           self.smarthumidifier.set_humidity_mode, vs_mode
       )
       if result:
           self.async_write_ha_state()

   async def async_turn_on(self, **kwargs: Any) -> None:
       """Turn the humidifier on."""
       result = await self.hass.async_add_executor_job(
           self.smarthumidifier.turn_on
       )
       if result:
           self.async_write_ha_state()

   async def async_turn_off(self, **kwargs: Any) -> None:
       """Turn the humidifier off."""
       result = await self.hass.async_add_executor_job(
           self.smarthumidifier.turn_off
       )
       if result:
           self.async_write_ha_state()

   async def async_set_mist_level(self, level: int) -> None:
       """Set the mist level (1-9)."""
       if 1 <= level <= 9:
           result = await self.hass.async_add_executor_job(
               self.smarthumidifier.set_virtual_level, level
           )
           if result:
               self.async_write_ha_state()

   async def async_set_display(self, display: bool) -> None:
       """Turn the display on or off."""
       result = await self.hass.async_add_executor_job(
           self.smarthumidifier.set_display, display
       )
       if result:
           self.async_write_ha_state()

   async def async_set_drying_mode(self, enabled: bool, level: int = 1) -> None:
       """Set the drying mode."""
       result = await self.hass.async_add_executor_job(
           self.smarthumidifier.set_drying_mode,
           {
               "autoDryingSwitch": 1 if enabled else 0,
               "dryingLevel": level
           }
       )
       if result:
           self.async_write_ha_state()
