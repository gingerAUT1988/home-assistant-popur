from homeassistant.components.event import EventEntity
from homeassistant.core import callback
from homeassistant.helpers.dispatcher import async_dispatcher_connect
from .const import DOMAIN, SIGNAL_CYCLE_DONE
from .entity import PopurEntity

async def async_setup_entry(hass, entry, async_add_entities):
    coordinator = hass.data[DOMAIN][entry.entry_id]
    entities = []
    for dev_id in coordinator.data:
        device_static_info = coordinator.devices_map[dev_id]
        entities.append(PopurCleaningDoneEvent(coordinator, device_static_info))
    async_add_entities(entities)

class PopurCleaningDoneEvent(PopurEntity, EventEntity):
    def __init__(self, coordinator, device):
        super().__init__(coordinator, device)
        self._attr_unique_id = f"{self._device_id}_cleaning_done"
        self._attr_name = "Cleaning Done"
        self._attr_icon = "mdi:broom"
        self._attr_event_types = ["cleaning_done"]

    async def async_added_to_hass(self):
        await super().async_added_to_hass()
        self.async_on_remove(async_dispatcher_connect(self.hass, SIGNAL_CYCLE_DONE, self._handle_cycle_done))

    @callback
    def _handle_cycle_done(self, device_id, attributes):
        if device_id != self._device_id:
            return
        self._trigger_event("cleaning_done", attributes)
        self.async_write_ha_state()
