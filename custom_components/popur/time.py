import datetime

from homeassistant.components.time import TimeEntity
from homeassistant.const import EntityCategory
from homeassistant.exceptions import HomeAssistantError
from .api import PopurCommandError
from .const import DOMAIN
from .entity import PopurEntity

async def async_setup_entry(hass, entry, async_add_entities):
    coordinator = hass.data[DOMAIN][entry.entry_id]
    entities = []
    for dev_id in coordinator.data:
        device_static_info = coordinator.devices_map[dev_id]
        entities.extend([
            PopurSettingTime(coordinator, device_static_info, "dnd_start", 14, "Do Not Disturb Start", "mdi:sleep"),
            PopurSettingTime(coordinator, device_static_info, "dnd_end", 15, "Do Not Disturb End", "mdi:sleep-off"),
        ])
    async_add_entities(entities)

class PopurSettingTime(PopurEntity, TimeEntity):
    def __init__(self, coordinator, device, key, pid, name, icon):
        super().__init__(coordinator, device)
        self._key = key
        self._pid = pid
        self._attr_unique_id = f"{self._device_id}_{key}"
        self._attr_name = name
        self._attr_icon = icon
        self._attr_entity_category = EntityCategory.CONFIG

    @property
    def native_value(self):
        value = self.coordinator.data.get(self._device_id, {}).get(self._key)
        if not value:
            return None
        try:
            hour, minute = value.split(":")
            return datetime.time(int(hour), int(minute))
        except (ValueError, AttributeError):
            return None

    async def async_set_value(self, value):
        try:
            await self.hass.async_add_executor_job(self.coordinator.api.set_property, self._device_id, self._pid, value.strftime("%H:%M"))
        except PopurCommandError as err:
            raise HomeAssistantError(str(err)) from err
