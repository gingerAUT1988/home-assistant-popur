import hashlib
import json
import requests
import time
import paho.mqtt.client as mqtt
import ssl
import logging

_LOGGER = logging.getLogger(__name__)

class PopurApi:
    def __init__(self, email, password):
        self.email = email
        # Store the hash, not the plaintext
        self.password_hash = hashlib.md5(password.encode()).hexdigest()
        self.token = None
        self.user_id = None
        self.home_id = None

    def login(self):
        """Login to Popur Cloud"""
        url = "https://cloud.popur.com.cn/uapi/auth"
        headers = {"Content-Type": "application/json", "User-Agent": "com.cloudapp.popur.app"}
        payload = {"param": self.email, "password": self.password_hash, "type": "2"}
        
        try:
            resp = requests.post(url, json=payload, headers=headers, timeout=10)
            data = resp.json()
            if data.get('code') == 200:
                self.token = data['data']['token']
                self.home_id = data['data']['defaulthomeid']
                return True
        except Exception as e:
            _LOGGER.error(f"Login error: {e}")
        return False

    def get_devices(self):
        """Get list of toilets"""
        if not self.token: self.login()
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
        url = f"https://cloud.popur.com.cn/uapi/deviceinfo/info/{device_id}"
        headers = {"Authorization": f"Bearer {self.token}", "User-Agent": "com.cloudapp.popur.app"}
        
        try:
            resp = requests.get(url, headers=headers, timeout=10)
            data = resp.json()['data']
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

    def send_command(self, device_id, cmd_type, value=None):
        """Send MQTT Command"""
        if not self.token: self.login()
        path = f"/mqtt?token={self.token}"
        broker = "cloud.popur.com.cn"
        
        payload = {}
        topic = ""

        if cmd_type == "clean":
            topic = f"devcrpc/action/{device_id}"
            payload = {"id": int(time.time()), "method": "action", "from": "remote", "params": {"did": "0", "sid": 2, "aid": 1, "in": []}}
        elif cmd_type == "manual_mode":
            topic = f"devcrpc/attr/{device_id}"
            val = 1 if value else 0
            payload = {"id": int(time.time()), "method": "set_properties", "from": "remote", "params": [{"did": "0", "pid": 3, "sid": 2, "value": val}]}

        try:
            client = mqtt.Client(transport="websockets")
            client.ws_set_options(path=path, headers={"Sec-WebSocket-Protocol": "mqtt"})
            client.tls_set_context(context=ssl.create_default_context())
            client.connect(broker, 443, 60)
            client.publish(topic, json.dumps(payload))
            time.sleep(0.5) # Allow time to send
            client.disconnect()
        except Exception as e:
            _LOGGER.error(f"MQTT Error: {e}")