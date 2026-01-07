import logging
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator
from .const import DOMAIN, UPDATE_INTERVAL

_LOGGER = logging.getLogger(__name__)

class PopurCoordinator(DataUpdateCoordinator):
    def __init__(self, hass, api):
        super().__init__(hass, _LOGGER, name="Popur Devices", update_interval=UPDATE_INTERVAL)
        self.api = api
        self.devices_map = {} # Store static device info here

    async def _async_update_data(self):
        # 1. Discover devices if we haven't yet
        if not self.devices_map:
            devices_list = await self.hass.async_add_executor_job(self.api.get_devices)
            for dev in devices_list:
                self.devices_map[dev['devid']] = dev
        
        # 2. Fetch status for all known devices
        data = {}
        for dev_id in self.devices_map:
            status = await self.hass.async_add_executor_job(self.api.get_device_status, dev_id)
            if status:
                data[dev_id] = status
        
        return data