from homeassistant.components.select import SelectEntity
from homeassistant.const import EntityCategory
from homeassistant.exceptions import HomeAssistantError
from .api import PopurCommandError
from .const import DOMAIN
from .entity import PopurEntity

OPTIONS = ["Off", "Clock", "Cycles Today", "Funny", "Heart"]

async def async_setup_entry(hass, entry, async_add_entities):
    coordinator = hass.data[DOMAIN][entry.entry_id]
    entities = []
    for dev_id in coordinator.data:
        device_static_info = coordinator.devices_map[dev_id]
        entities.append(PopurDisplaySelect(coordinator, device_static_info))
        entities.extend([
            PopurSettingSelect(coordinator, device_static_info, "wait_time", 18, "Wait Time", "mdi:timer-sand",
                {n: f"{n} minutes" + (" (default)" if n == 5 else "") for n in range(2, 31)}),
            PopurSettingSelect(coordinator, device_static_info, "leveling", 5, "Leveling Passes", "mdi:layers-triple",
                {n: f"{n} times" + (" (default)" if n == 3 else "") for n in range(2, 6)}),
        ])
    async_add_entities(entities)

class PopurDisplaySelect(PopurEntity, SelectEntity):
    def __init__(self, coordinator, device):
        super().__init__(coordinator, device)
        self._attr_unique_id = f"{self._device_id}_display"
        self._attr_name = "Display"
        self._attr_icon = "mdi:monitor"
        self._attr_entity_category = EntityCategory.CONFIG
        self._attr_options = OPTIONS

    @property
    def current_option(self):
        value = self.coordinator.data.get(self._device_id, {}).get("display")
        if type(value) is int and 1 <= value <= len(OPTIONS):
            return OPTIONS[value - 1]
        return None

    async def async_select_option(self, option):
        try:
            await self.hass.async_add_executor_job(self.coordinator.api.set_property, self._device_id, 17, OPTIONS.index(option) + 1)
        except PopurCommandError as err:
            raise HomeAssistantError(str(err)) from err

class PopurSettingSelect(PopurEntity, SelectEntity):
    def __init__(self, coordinator, device, key, pid, name, icon, labels):
        super().__init__(coordinator, device)
        self._key = key
        self._pid = pid
        self._labels = labels
        self._attr_unique_id = f"{self._device_id}_{key}"
        self._attr_name = name
        self._attr_icon = icon
        self._attr_entity_category = EntityCategory.CONFIG
        self._attr_options = list(labels.values())

    @property
    def current_option(self):
        return self._labels.get(self.coordinator.data.get(self._device_id, {}).get(self._key))

    async def async_select_option(self, option):
        value = next(v for v, label in self._labels.items() if label == option)
        # No coordinator refresh: the device confirms the new value by push, and the HTTP cache can still hold the old one.
        try:
            await self.hass.async_add_executor_job(self.coordinator.api.set_property, self._device_id, self._pid, value)
        except PopurCommandError as err:
            raise HomeAssistantError(str(err)) from err
