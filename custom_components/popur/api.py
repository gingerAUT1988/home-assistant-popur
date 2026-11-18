import hashlib
import json
import requests
import time
import paho.mqtt.client as mqtt
import ssl
import itertools
import logging
import random
import threading

_LOGGER = logging.getLogger(__name__)

# MQTT CONNACK reason codes for a rejected token: "Bad user name or password", "Not authorized".
_AUTH_REFUSED = (134, 135)
# Minimum seconds between two logins started by the MQTT reconnect logic.
_RELOGIN_AFTER_AUTH_REFUSED = 60
_RELOGIN_AFTER_OTHER_FAILURE = 15 * 60
# Seconds to wait for the device's reply to a command.
COMMAND_TIMEOUT = 5
# False: a missing reply only logs a warning. Set to True when live tests show that the
# device replies to our own action and set_properties commands.
REQUIRE_COMMAND_REPLY = False


class PopurCommandError(Exception):
    """The command was not sent, or the device rejected it."""


def _reply_code(payload):
    """Return the result code of an action or set_properties reply, or None if it has none."""
    params = payload.get("params")
    if isinstance(params, dict):
        params = [params]
    if isinstance(params, list):
        codes = [e.get("code") for e in params if isinstance(e, dict) and "code" in e]
        if codes:
            return next((c for c in codes if c != 0), 0)
    return payload.get("code")


class PopurApi:
    def __init__(self, email, password):
        self.email = email.strip()
        
        # 1. Clean input
        clean_pass = password.strip()
        
        # 2. Check if it is ALREADY a Hash
        is_hash = (len(clean_pass) == 32 and all(c in '0123456789abcdefABCDEF' for c in clean_pass))
        
        if is_hash:
            _LOGGER.info("Popur: Detected MD5 hash provided directly.")
            self.password_hash = clean_pass
        else:
            _LOGGER.info("Popur: Hashing plain-text password.")
            self.password_hash = hashlib.md5(clean_pass.encode()).hexdigest()
            
        self.token = None
        self.user_id = None
        self.home_id = None
        self._push = None
        self._login_lock = threading.Lock()
        self._last_relogin = None
        # The app uses small ids (2, 3, 4...). Start far above them so that replies do not mix.
        self._ids = itertools.count(random.randint(100_000, 900_000))
        self._pending = {}
        self._pending_lock = threading.Lock()

    def login(self):
        """Login to Popur Cloud. Thread-safe: the poll, commands and the MQTT thread can call it."""
        with self._login_lock:
            return self._login()

    def _login(self):
        url = "https://cloud.popur.com.cn/uapi/auth"
        headers = {"Content-Type": "application/json", "User-Agent": "com.cloudapp.popur.app"}
        payload = {"param": self.email, "password": self.password_hash, "type": "2"}
        
        try:
            resp = requests.post(url, json=payload, headers=headers, timeout=10)
            data = resp.json()
            
            if data.get('code') == 200:
                self.token = data['data']['token']
                # FIX: These fields are nested inside 'user' dictionary
                user_data = data['data'].get('user', {})
                self.user_id = user_data.get('_id')
                self.home_id = user_data.get('defaulthomeid')
                return True
            else:
                _LOGGER.error(f"Popur Login Failed: {data}")
        except Exception as e:
            _LOGGER.error(f"Popur Connection Error: {e}")
        return False

    def get_devices(self):
        """Get list of toilets"""
        if not self.token: self.login()
        if not self.token or not self.home_id: return [] 
        
        url = f"https://cloud.popur.com.cn/uapi/home_details/{self.home_id}"
        headers = {"Authorization": f"Bearer {self.token}", "User-Agent": "com.cloudapp.popur.app"}
        
        try:
            resp = requests.get(url, headers=headers, timeout=10)
            data = resp.json()
            return data['data']['devicelist']
        except Exception as e:
            _LOGGER.error(f"Device discovery error: {e}")
            return []

    def get_device_status(self, device_id):
        """Get status of a specific toilet"""
        if not self.token: self.login()
        if not self.token: return None

        url = f"https://cloud.popur.com.cn/uapi/deviceinfo/info/{device_id}"
        headers = {"Authorization": f"Bearer {self.token}", "User-Agent": "com.cloudapp.popur.app"}
        
        try:
            resp = requests.get(url, headers=headers, timeout=10)
            data = resp.json().get('data', {})
            
            return {
                "bin_full": True if data.get('rubbish') == 2 else False,
                "cycles": data.get('worknum', 0),
                "total_cycles": data.get('lastworknum', 0),
                "manual_mode": True if str(data.get('manualmode')) == "1" else False,
                "online": True if str(data.get('isonline')) == "1" else False
            }
        except Exception as e:
            _LOGGER.error(f"Status fetch error: {e}")
            return None

    def start_push(self, device_ids, callback, on_connected=None, on_disconnected=None):
        """Open the persistent MQTT connection.

        callback(topic, payload), on_connected() and on_disconnected() run in the paho thread.
        on_connected runs after each successful connect. on_disconnected runs after each
        unexpected disconnect.
        """
        if not device_ids: return
        if not self.token: self.login()
        client = mqtt.Client(mqtt.CallbackAPIVersion.VERSION2, transport="websockets")
        def use_token():
            client.ws_set_options(path=f"/mqtt?token={self.token}", headers={"Sec-WebSocket-Protocol": "mqtt"})

        use_token()
        client.tls_set_context(context=ssl.create_default_context())
        client.reconnect_delay_set(min_delay=1, max_delay=120)

        def on_connect(client, userdata, flags, reason_code, properties):
            if reason_code.is_failure:
                _LOGGER.warning(f"Popur MQTT connect refused: {reason_code}")
                if reason_code.value in _AUTH_REFUSED:
                    renew_token(_RELOGIN_AFTER_AUTH_REFUSED)
                return
            for device_id in device_ids:
                client.subscribe(f"+/+/{device_id}")
            if on_connected:
                on_connected()

        def renew_token(min_interval):
            # Each login issues a new token. Do not log in on every reconnect try.
            now = time.monotonic()
            if self._last_relogin is not None and now - self._last_relogin < min_interval:
                return
            self._last_relogin = now
            if self.login():
                use_token()

        def on_disconnect(client, userdata, flags, reason_code, properties):
            if not reason_code.is_failure:
                return  # stop_push() closed the connection.
            if reason_code.value in _AUTH_REFUSED:
                renew_token(_RELOGIN_AFTER_AUTH_REFUSED)
            if on_disconnected:
                on_disconnected()

        def on_connect_fail(client, userdata):
            # The cause is unknown here (network down or token rejected at the WebSocket handshake).
            renew_token(_RELOGIN_AFTER_OTHER_FAILURE)

        def on_message(client, userdata, msg):
            try:
                payload = json.loads(msg.payload)
                self._handle_reply(msg.topic, payload)
                callback(msg.topic, payload)
            # RuntimeError: the event loop is closed during shutdown.
            except (ValueError, RuntimeError):
                pass

        client.on_connect = on_connect
        client.on_disconnect = on_disconnect
        client.on_connect_fail = on_connect_fail
        client.on_message = on_message
        client.connect_async("cloud.popur.com.cn", 443, keepalive=30)
        client.loop_start()
        self._push = client

    def stop_push(self):
        """Close the MQTT connection and wait for the paho thread. Safe to call two times."""
        client, self._push = self._push, None
        if client:
            client.disconnect()
            client.loop_stop()

    def _handle_reply(self, topic, payload):
        """Record the result of a pending command. Runs in the paho thread."""
        if not isinstance(payload, dict) or not topic.startswith(("devsrpc/action/", "devsrpc/attr/")):
            return
        if payload.get("method") not in ("action", "set_properties"):
            return
        with self._pending_lock:
            pending = self._pending.get(payload.get("id"))
        if pending is not None:
            pending["code"] = _reply_code(payload)
            pending["event"].set()

    def send_command(self, device_id, cmd_type, value=None):
        """Send a command on the push connection and wait for the device's reply.

        Raises PopurCommandError when push is not connected, the publish fails, or the
        device replies with an error code.
        """
        msg_id = next(self._ids)
        if cmd_type == "clean":
            topic = f"devcrpc/action/{device_id}"
            payload = {"id": msg_id, "method": "action", "from": "remote", "params": {"did": "0", "sid": 2, "aid": 1, "in": []}}
        elif cmd_type == "manual_mode":
            topic = f"devcrpc/attr/{device_id}"
            payload = {"id": msg_id, "method": "set_properties", "from": "remote", "params": [{"did": "0", "pid": 3, "sid": 2, "value": 1 if value else 0}]}
        else:
            raise ValueError(f"Unknown command: {cmd_type}")

        push = self._push
        if not push or not push.is_connected():
            raise PopurCommandError("Not connected to the Popur cloud. Try again in a minute.")

        pending = {"event": threading.Event(), "code": None}
        with self._pending_lock:
            self._pending[msg_id] = pending
        try:
            if push.publish(topic, json.dumps(payload)).rc != mqtt.MQTT_ERR_SUCCESS:
                raise PopurCommandError("Could not send the command to the Popur cloud.")
            replied = pending["event"].wait(COMMAND_TIMEOUT)
        finally:
            with self._pending_lock:
                self._pending.pop(msg_id, None)

        if not replied:
            if REQUIRE_COMMAND_REPLY:
                raise PopurCommandError(f"The device did not answer the {cmd_type} command.")
            _LOGGER.warning(f"Popur: no reply to {cmd_type} command id {msg_id} within {COMMAND_TIMEOUT} s")
            return
        if pending["code"] not in (0, None):
            raise PopurCommandError(f"The device rejected the {cmd_type} command (code {pending['code']}).")
        _LOGGER.debug(f"Popur: {cmd_type} command id {msg_id} confirmed")
