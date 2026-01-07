from homeassistant.core import HomeAssistant
from homeassistant.config_entries import ConfigEntry
from .const import DOMAIN, CONF_EMAIL, CONF_PASSWORD
from .api import PopurApi
from .coordinator import PopurCoordinator

PLATFORMS = ["sensor", "binary_sensor", "switch", "button"]

async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry):
    hass.data.setdefault(DOMAIN, {})
    
    api = PopurApi(entry.data[CONF_EMAIL], entry.data[CONF_PASSWORD])
    coordinator = PopurCoordinator(hass, api)
    
    await coordinator.async_config_entry_first_refresh()
    
    hass.data[DOMAIN][entry.entry_id] = coordinator
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    return True

async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry):
    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)