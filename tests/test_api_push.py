import importlib.util
from pathlib import Path
from types import SimpleNamespace

_spec = importlib.util.spec_from_file_location(
    "popur_api", Path(__file__).parent.parent / "custom_components" / "popur" / "api.py"
)
api_mod = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(api_mod)


class FakeClient:
    def __init__(self, *args, **kwargs):
        self.paths = []

    def ws_set_options(self, path, headers):
        self.paths.append(path)

    def tls_set_context(self, context): pass
    def reconnect_delay_set(self, **kwargs): pass
    def subscribe(self, topic): pass
    def connect_async(self, *args, **kwargs): pass
    def loop_start(self): pass


def rc(value, failure=True):
    return SimpleNamespace(value=value, is_failure=failure)


def make_api(monkeypatch):
    monkeypatch.setattr(api_mod.mqtt, "Client", FakeClient)
    clock = SimpleNamespace(now=1000.0)
    monkeypatch.setattr(api_mod.time, "monotonic", lambda: clock.now)
    api = api_mod.PopurApi("a@b.c", "pw")
    api.token = "t0"
    logins = []

    def fake_login():
        logins.append(clock.now)
        api.token = f"t{len(logins)}"
        return True

    api._login = fake_login
    events = []
    api.start_push(["dev1"], lambda t, p: None, lambda: events.append("up"), lambda: events.append("down"))
    return api, api._push, clock, logins, events


def test_connect_fail_relogins_at_most_every_15_min(monkeypatch):
    api, client, clock, logins, _ = make_api(monkeypatch)
    for _ in range(10):
        client.on_connect_fail(client, None)
        clock.now += 60
    assert len(logins) == 1
    clock.now += 15 * 60
    client.on_connect_fail(client, None)
    assert len(logins) == 2
    assert client.paths[-1] == "/mqtt?token=t2"


def test_network_drop_does_not_relogin(monkeypatch):
    api, client, clock, logins, events = make_api(monkeypatch)
    client.on_disconnect(client, None, None, rc(141), None)  # keepalive timeout
    assert logins == []
    assert events == ["down"]


def test_auth_refused_relogins_quickly(monkeypatch):
    api, client, clock, logins, _ = make_api(monkeypatch)
    client.on_connect(client, None, None, rc(135), None)
    client.on_disconnect(client, None, None, rc(135), None)
    assert len(logins) == 1  # same refusal reported twice: one login
    clock.now += 61
    client.on_connect(client, None, None, rc(134), None)
    assert len(logins) == 2


def test_clean_disconnect_is_silent(monkeypatch):
    api, client, clock, logins, events = make_api(monkeypatch)
    client.on_disconnect(client, None, None, rc(0, failure=False), None)
    assert logins == [] and events == []


def test_connect_reports_up(monkeypatch):
    api, client, clock, logins, events = make_api(monkeypatch)
    client.on_connect(client, None, None, rc(0, failure=False), None)
    assert events == ["up"]
