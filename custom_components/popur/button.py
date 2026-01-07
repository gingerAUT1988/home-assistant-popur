from homeassistant.components.button import ButtonEntity
from .const import DOMAIN
from .entity import PopurEntity

async def async_setup_entry(hass, entry, async_add_entities):
    coordinator = hass.data[DOMAIN][entry.entry_id]
    entities = []
    for dev_id in coordinator.data:
        device_static_info = coordinator.devices_map[dev_id]
        entities.append(PopurCleanButton(coordinator, device_static_info))
    async_add_entities(entities)

class PopurCleanButton(PopurEntity, ButtonEntity):
    def __init__(self, coordinator, device):
        super().__init__(coordinator, device)
        self._attr_unique_id = f"{self._device_id}_clean"
        self._attr_name = "Clean"
        self._attr_icon = "mdi:robot-vacuum"

    async def async_press(self):
        await self.hass.async_add_executor_job(self.coordinator.api.send_command, self._device_id, "clean")