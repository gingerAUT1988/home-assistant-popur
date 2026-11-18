from datetime import timedelta

DOMAIN = "popur"
CONF_EMAIL = "email"
CONF_PASSWORD = "password"
UPDATE_INTERVAL = timedelta(seconds=60) # Check status every minute
# Safety-net poll while the MQTT push connection is up.
PUSH_UPDATE_INTERVAL = timedelta(minutes=30)
