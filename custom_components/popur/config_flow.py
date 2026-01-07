import voluptuous as vol
from homeassistant import config_entries
from .const import DOMAIN, CONF_EMAIL, CONF_PASSWORD
from .api import PopurApi

class PopurConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    VERSION = 1

    async def async_step_user(self, user_input=None):
        errors = {}
        if user_input is not None:
            api = PopurApi(user_input[CONF_EMAIL], user_input[CONF_PASSWORD])
            success = await self.hass.async_add_executor_job(api.login)
            if success:
                return self.async_create_entry(title=user_input[CONF_EMAIL], data=user_input)
            else:
                errors["base"] = "invalid_auth"

        return self.async_show_form(
            step_id="user",
            data_schema=vol.Schema({
                vol.Required(CONF_EMAIL): str,
                vol.Required(CONF_PASSWORD): str,
            }),
            errors=errors,
        )