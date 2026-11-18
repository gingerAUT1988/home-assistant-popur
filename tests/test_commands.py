import importlib.util
import json
import threading
import time
from pathlib import Path
from types import SimpleNamespace

import pytest

_spec = importlib.util.spec_from_file_location(
    "popur_api_cmd", Path(__file__).parent.parent / "custom_components" / "popur" / "api.py"
)
api_mod = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(api_mod)


class FakePush:
    def __init__(self, api, reply=None, connected=True, rc=0):
        self.api, self.reply, self.connected, self.rc = api, reply, connected, rc
        self.sent = []

    def is_connected(self):
        return self.connected

    def publish(self, topic, data):
        msg = json.loads(data)
        self.sent.append((topic, msg))
        if self.reply:
            reply_topic, reply_payload = self.reply(topic, msg)
            self.api._handle_reply(reply_topic, reply_payload)
        return SimpleNamespace(rc=self.rc)


def make_api(monkeypatch, **kwargs):
    monkeypatch.setattr(api_mod, "COMMAND_TIMEOUT", 0.05)
    monkeypatch.setattr(api_mod, "COMMAND_GAP", 0)
    api = api_mod.PopurApi("a@b.c", "pw")
    api._push = FakePush(api, **kwargs)
    return api


def action_reply(code):
    return lambda topic, msg: ("devsrpc/action/dev1", {"id": msg["id"], "method": "action",
        "params": {"did": "0", "sid": 2, "aid": 1, "code": code, "out": [{"piid": 2, "value": 0}]}})


def set_reply(code):
    return lambda topic, msg: ("devsrpc/attr/dev1", {"id": msg["id"], "method": "set_properties",
        "params": [{"did": "0", "sid": 2, "pid": 3, "code": code}]})


def test_clean_confirmed(monkeypatch):
    api = make_api(monkeypatch, reply=action_reply(0))
    api.send_command("dev1", "clean")
    topic, msg = api._push.sent[0]
    assert topic == "devcrpc/action/dev1" and msg["params"]["aid"] == 1
    assert api._pending == {}


def test_manual_mode_confirmed(monkeypatch):
    api = make_api(monkeypatch, reply=set_reply(0))
    api.send_command("dev1", "manual_mode", True)
    assert api._push.sent[0][1]["params"][0]["value"] == 1


def test_rejected_raises(monkeypatch):
    api = make_api(monkeypatch, reply=set_reply(-4))
    with pytest.raises(api_mod.PopurCommandError, match="code -4"):
        api.send_command("dev1", "manual_mode", False)


def test_no_reply_warns_only(monkeypatch, caplog):
    api = make_api(monkeypatch)
    api.send_command("dev1", "clean")
    assert "no reply" in caplog.text
    assert api._pending == {}


def test_no_reply_raises_when_required(monkeypatch):
    api = make_api(monkeypatch)
    monkeypatch.setattr(api_mod, "REQUIRE_COMMAND_REPLY", True)
    with pytest.raises(api_mod.PopurCommandError, match="did not answer"):
        api.send_command("dev1", "clean")


def test_reply_to_other_id_is_ignored(monkeypatch, caplog):
    other = lambda topic, msg: ("devsrpc/action/dev1", {"id": 3, "method": "action", "params": {"code": -1}})
    api = make_api(monkeypatch, reply=other)
    api.send_command("dev1", "clean")  # the app's reply (id 3) must not count as ours
    assert "no reply" in caplog.text


def test_not_connected_raises(monkeypatch):
    api = make_api(monkeypatch, connected=False)
    with pytest.raises(api_mod.PopurCommandError, match="Not connected"):
        api.send_command("dev1", "clean")
    api._push = None
    with pytest.raises(api_mod.PopurCommandError, match="Not connected"):
        api.send_command("dev1", "clean")


def test_publish_failure_raises(monkeypatch):
    api = make_api(monkeypatch, rc=4)
    with pytest.raises(api_mod.PopurCommandError, match="Could not send"):
        api.send_command("dev1", "clean")
    assert api._pending == {}


def test_ids_are_unique(monkeypatch):
    api = make_api(monkeypatch, reply=action_reply(0))
    api.send_command("dev1", "clean")
    api.send_command("dev1", "clean")
    ids = [m["id"] for _, m in api._push.sent]
    assert ids[0] != ids[1] and ids[0] >= 100_000


def reboot_reply(code):
    return lambda topic, msg: ("devsrpc/event/dev1", {"id": msg["id"], "method": "aithingsIO.reboot",
        "params": [{"code": code}]})


def test_set_property_confirmed(monkeypatch):
    api = make_api(monkeypatch, reply=set_reply(0))
    api.set_property("dev1", 4, 1)
    topic, msg = api._push.sent[0]
    assert topic == "devcrpc/attr/dev1"
    assert msg["method"] == "set_properties"
    assert msg["params"] == [{"did": "0", "pid": 4, "sid": 2, "value": 1}]
    assert api._pending == {}


def test_set_property_rejected_raises(monkeypatch):
    api = make_api(monkeypatch, reply=set_reply(-4))
    with pytest.raises(api_mod.PopurCommandError, match="code -4"):
        api.set_property("dev1", 4, 1)


def test_set_property_string_value(monkeypatch):
    api = make_api(monkeypatch, reply=set_reply(0))
    api.set_property("dev1", 14, "22:00")
    assert api._push.sent[0][1]["params"] == [{"did": "0", "pid": 14, "sid": 2, "value": "22:00"}]


def test_reboot_confirmed(monkeypatch):
    api = make_api(monkeypatch, reply=reboot_reply(0))
    api.send_command("dev1", "reboot")
    topic, msg = api._push.sent[0]
    assert topic == "devcrpc/event/dev1"
    assert msg["method"] == "aithingsIO.reboot"
    assert msg["params"] == [{"did": "0"}]
    assert api._pending == {}


def test_reboot_rejected_raises(monkeypatch):
    api = make_api(monkeypatch, reply=reboot_reply(-1))
    with pytest.raises(api_mod.PopurCommandError, match="code -1"):
        api.send_command("dev1", "reboot")


def test_event_occured_is_not_a_reply(monkeypatch, caplog):
    event = lambda topic, msg: ("devsrpc/event/dev1", {"id": msg["id"], "method": "event_occured",
        "params": {"did": "0", "sid": 2, "eid": 1, "arguments": []}})
    api = make_api(monkeypatch, reply=event)
    api.send_command("dev1", "reboot")
    assert "no reply" in caplog.text


def test_commands_keep_a_minimum_gap(monkeypatch):
    api = make_api(monkeypatch, reply=set_reply(0))
    monkeypatch.setattr(api_mod, "COMMAND_GAP", 0.2)
    times = []
    publish = api._push.publish
    api._push.publish = lambda topic, data: (times.append(time.monotonic()), publish(topic, data))[1]
    api.set_property("dev1", 4, 1)
    api.set_property("dev1", 13, 1)
    assert times[1] - times[0] >= 0.19


def test_replaced_write_is_not_sent(monkeypatch):
    api = make_api(monkeypatch, reply=set_reply(0))
    started, release = threading.Event(), threading.Event()
    publish = api._push.publish

    def slow_publish(topic, data):
        started.set()
        release.wait(1)
        return publish(topic, data)

    api._push.publish = slow_publish
    first = threading.Thread(target=api.set_property, args=("dev1", 4, 1))
    first.start()
    started.wait(1)
    # Two writes of pid 18 queue behind the first command: only the newest one is sent.
    second = threading.Thread(target=api.set_property, args=("dev1", 18, 3))
    second.start()
    time.sleep(0.05)
    third = threading.Thread(target=api.set_property, args=("dev1", 18, 7))
    third.start()
    time.sleep(0.05)
    release.set()
    for t in (first, second, third):
        t.join(2)
    values = [(m["params"][0]["pid"], m["params"][0]["value"]) for _, m in api._push.sent]
    assert values == [(4, 1), (18, 7)]
