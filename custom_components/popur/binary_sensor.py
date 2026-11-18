from homeassistant.components.binary_sensor import BinarySensorEntity, BinarySensorDeviceClass
from .const import DOMAIN
from .entity import PopurEntity

async def async_setup_entry(hass, entry, async_add_entities):
    coordinator = hass.data[DOMAIN][entry.entry_id]
    entities = []
    for dev_id in coordinator.data:
        device_static_info = coordinator.devices_map[dev_id]
        entities.append(PopurBinSensor(coordinator, device_static_info))
        entities.append(PopurPresenceSensor(coordinator, device_static_info))
    async_add_entities(entities)

class PopurBinSensor(PopurEntity, BinarySensorEntity):
    def __init__(self, coordinator, device):
        super().__init__(coordinator, device)
        self._attr_unique_id = f"{self._device_id}_bin_full"
        self._attr_name = "Bin Full"
        self._attr_device_class = BinarySensorDeviceClass.PROBLEM

    @property
    def is_on(self):
        return self.coordinator.data.get(self._device_id, {}).get("bin_full")

class PopurPresenceSensor(PopurEntity, BinarySensorEntity):
    def __init__(self, coordinator, device):
        super().__init__(coordinator, device)
        self._attr_unique_id = f"{self._device_id}_presence"
        self._attr_name = "Presence"
        self._attr_device_class = BinarySensorDeviceClass.OCCUPANCY

    @property
    def is_on(self):
        status = self.coordinator.data.get(self._device_id, {}).get("status")
        if status is None:
            return None
        # Status 3 is a cat or a hand; the device cannot tell them apart.
        return status == 3
