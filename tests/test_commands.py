import importlib.util
import json
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
