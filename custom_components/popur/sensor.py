from homeassistant.components.sensor import SensorEntity, SensorStateClass
from .const import DOMAIN
from .entity import PopurEntity

async def async_setup_entry(hass, entry, async_add_entities):
    coordinator = hass.data[DOMAIN][entry.entry_id]
    entities = []
    # Loop through all devices found in the coordinator data
    for dev_id, device_data in coordinator.data.items():
        # The coordinator data structure is {dev_id: {status...}, ...}
        # We need the static device info stored in coordinator.devices_map
        device_static_info = coordinator.devices_map[dev_id]
        entities.append(PopurCyclesSensor(coordinator, device_static_info))
    async_add_entities(entities)

class PopurCyclesSensor(PopurEntity, SensorEntity):
    def __init__(self, coordinator, device):
        super().__init__(coordinator, device)
        self._attr_unique_id = f"{self._device_id}_cycles"
        self._attr_name = "Cycles" # Simple name, HA prefixes device name automatically
        self._attr_native_unit_of_measurement = "cycles"
        self._attr_state_class = SensorStateClass.TOTAL
        self._attr_icon = "mdi:counter"

    @property
    def native_value(self):
        # Safely get data from coordinator
        return self.coordinator.data.get(self._device_id, {}).get("cycles")