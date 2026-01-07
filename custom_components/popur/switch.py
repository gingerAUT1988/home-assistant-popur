from homeassistant.components.switch import SwitchEntity
from .const import DOMAIN
from .entity import PopurEntity

async def async_setup_entry(hass, entry, async_add_entities):
    coordinator = hass.data[DOMAIN][entry.entry_id]
    entities = []
    for dev_id in coordinator.data:
        device_static_info = coordinator.devices_map[dev_id]
        entities.append(PopurManualSwitch(coordinator, device_static_info))
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
        await self.hass.async_add_executor_job(self.coordinator.api.send_command, self._device_id, "manual_mode", True)
        await self.coordinator.async_request_refresh()

    async def async_turn_off(self, **kwargs):
        await self.hass.async_add_executor_job(self.coordinator.api.send_command, self._device_id, "manual_mode", False)
        await self.coordinator.async_request_refresh()