import logging

from homeassistant.const import EVENT_HOMEASSISTANT_STOP
from homeassistant.core import HomeAssistant
from homeassistant.config_entries import ConfigEntry
from .const import DOMAIN, CONF_EMAIL, CONF_PASSWORD, PUSH_UPDATE_INTERVAL, UPDATE_INTERVAL
from .api import PopurApi
from .coordinator import PopurCoordinator
from .push import apply_message

_LOGGER = logging.getLogger(__name__)

PLATFORMS = ["sensor", "binary_sensor", "switch", "button"]

async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry):
    hass.data.setdefault(DOMAIN, {})
    
    api = PopurApi(entry.data[CONF_EMAIL], entry.data[CONF_PASSWORD])
    coordinator = PopurCoordinator(hass, api)
    
    await coordinator.async_config_entry_first_refresh()
    
    hass.data[DOMAIN][entry.entry_id] = coordinator
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    def apply_push(topic, payload):
        data = {devid: dict(state) for devid, state in coordinator.data.items()}
        changed = apply_message(data, topic, payload)
        if changed:
            if coordinator.push_overlay is not None:
                coordinator.push_overlay.setdefault(topic.rsplit("/", 1)[1], {}).update(changed)
            coordinator.async_set_updated_data(data)

    def set_push_state(connected):
        # Push up: poll slowly as a safety net. Push down: poll fast again.
        # Refresh now in both cases: after a reconnect the push may have missed messages.
        coordinator.update_interval = PUSH_UPDATE_INTERVAL if connected else UPDATE_INTERVAL
        hass.async_create_task(coordinator.async_request_refresh())

    def from_paho_thread(func, *args):
        try:
            hass.loop.call_soon_threadsafe(func, *args)
        except RuntimeError:
            pass  # The event loop is closed during shutdown.

    try:
        await hass.async_add_executor_job(
            api.start_push,
            list(coordinator.data),
            lambda topic, payload: from_paho_thread(apply_push, topic, payload),
            lambda: from_paho_thread(set_push_state, True),
            lambda: from_paho_thread(set_push_state, False),
        )
    except Exception as err:
        _LOGGER.warning("Popur MQTT push not started, polling only: %s", err)
    else:
        async def stop_push(event):
            await hass.async_add_executor_job(api.stop_push)

        entry.async_on_unload(hass.bus.async_listen_once(EVENT_HOMEASSISTANT_STOP, stop_push))
    return True

async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry):
    if unloaded := await hass.config_entries.async_unload_platforms(entry, PLATFORMS):
        await hass.async_add_executor_job(hass.data[DOMAIN].pop(entry.entry_id).api.stop_push)
    return unloaded