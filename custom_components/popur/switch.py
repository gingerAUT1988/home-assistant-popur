from homeassistant.components.switch import SwitchEntity
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
        entities.append(PopurManualSwitch(coordinator, device_static_info))
        entities.extend([
            PopurSettingSwitch(coordinator, device_static_info, "curious_cat", 4, "Curious Cat", "mdi:cat"),
            PopurSettingSwitch(coordinator, device_static_info, "dnd", 13, "Do Not Disturb", "mdi:sleep"),
        ])
    async_add_entities(entities)

class PopurManualSwitch(PopurEntity, SwitchEntity):
    def __init__(self, coordinator, device):
        super().__init__(coordinator, device)
        self._attr_unique_id = f"{self._device_id}_manual_mode"
        self._attr_name = "Manual Mode"
        self._attr_icon = "mdi:hand-back-right"

    @property
    def is_on(self):
        return self.coordinator.data.get(self._device_id, {}).get("manual_mode")

    async def async_turn_on(self, **kwargs):
        await self._set(True)

    async def async_turn_off(self, **kwargs):
        await self._set(False)

    async def _set(self, value):
        try:
            await self.hass.async_add_executor_job(self.coordinator.api.send_command, self._device_id, "manual_mode", value)
        except PopurCommandError as err:
            raise HomeAssistantError(str(err)) from err
        # No coordinator refresh: the device confirms the new value by push.

class PopurSettingSwitch(PopurEntity, SwitchEntity):
    def __init__(self, coordinator, device, key, pid, name, icon):
        super().__init__(coordinator, device)
        self._key = key
        self._pid = pid
        self._attr_unique_id = f"{self._device_id}_{key}"
        self._attr_name = name
        self._attr_icon = icon
        self._attr_entity_category = EntityCategory.CONFIG

    @property
    def is_on(self):
        return self.coordinator.data.get(self._device_id, {}).get(self._key)

    async def async_turn_on(self, **kwargs):
        await self._set(1)

    async def async_turn_off(self, **kwargs):
        await self._set(0)

    async def _set(self, value):
        try:
            await self.hass.async_add_executor_job(self.coordinator.api.set_property, self._device_id, self._pid, value)
        except PopurCommandError as err:
            raise HomeAssistantError(str(err)) from err
