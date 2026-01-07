from homeassistant.helpers.update_coordinator import CoordinatorEntity
from .const import DOMAIN

class PopurEntity(CoordinatorEntity):
    """Base class for Popur entities."""

    def __init__(self, coordinator, device):
        super().__init__(coordinator)
        self.device = device
        self._device_id = device["devid"]
        self._attr_device_info = {
            "identifiers": {(DOMAIN, self._device_id)},
            "name": device["name"],
            "manufacturer": "Popur",
            "model": "X5",
            "sw_version": "1.0",
        }