from homeassistant.components.button import ButtonDeviceClass, ButtonEntity
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
        entities.append(PopurCleanButton(coordinator, device_static_info))
        entities.append(PopurResetBinButton(coordinator, device_static_info))
        entities.append(PopurRebootButton(coordinator, device_static_info))
    async_add_entities(entities)

class PopurCleanButton(PopurEntity, ButtonEntity):
    def __init__(self, coordinator, device):
        super().__init__(coordinator, device)
        self._attr_unique_id = f"{self._device_id}_clean"
        self._attr_name = "Clean"
        self._attr_icon = "mdi:robot-vacuum"

    async def async_press(self):
        try:
            await self.hass.async_add_executor_job(self.coordinator.api.send_command, self._device_id, "clean")
        except PopurCommandError as err:
            raise HomeAssistantError(str(err)) from err

class PopurResetBinButton(PopurEntity, ButtonEntity):
    """Same as the app's "bin emptied" button: the device sets Cycles Since Bin Emptied to 0."""

    def __init__(self, coordinator, device):
        super().__init__(coordinator, device)
        self._attr_unique_id = f"{self._device_id}_reset_bin"
        self._attr_name = "Reset Bin Counter"
        self._attr_icon = "mdi:delete-empty"

    async def async_press(self):
        try:
            await self.hass.async_add_executor_job(self.coordinator.api.send_command, self._device_id, "reset_bin")
        except PopurCommandError as err:
            raise HomeAssistantError(str(err)) from err

class PopurRebootButton(PopurEntity, ButtonEntity):
    def __init__(self, coordinator, device):
        super().__init__(coordinator, device)
        self._attr_unique_id = f"{self._device_id}_reboot"
        self._attr_name = "Reboot"
        self._attr_device_class = ButtonDeviceClass.RESTART
        self._attr_entity_category = EntityCategory.CONFIG

    async def async_press(self):
        try:
            await self.hass.async_add_executor_job(self.coordinator.api.send_command, self._device_id, "reboot")
        except PopurCommandError as err:
            raise HomeAssistantError(str(err)) from err
