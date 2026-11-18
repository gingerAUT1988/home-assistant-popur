import importlib.util
from pathlib import Path

_spec = importlib.util.spec_from_file_location(
    "popur_push", Path(__file__).parent.parent / "custom_components" / "popur" / "push.py"
)
push = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(push)

ATTR = "devsrpc/attr/dev1"


def make_state():
    return {"dev1": {"bin_full": False, "cycles": 0, "total_cycles": 0, "manual_mode": False, "online": False}}


def attr(*entries, method="properties_changed"):
    return {"from": "remote", "id": 0, "method": method, "params": [{"did": "0", **e} for e in entries]}


def test_pid_mapping():
    for pid, value, expected in [
        (6, 2, {"bin_full": True}),
        (8, 13, {"cycles": 13}),
        (11, 8, {"total_cycles": 8}),
        (3, 1, {"manual_mode": True}),
    ]:
        state = make_state()
        assert push.apply_message(state, ATTR, attr({"sid": 2, "pid": pid, "value": value})) == expected
        assert all(state["dev1"][k] == v for k, v in expected.items())


def test_bin_emptied():
    state = make_state()
    state["dev1"]["bin_full"] = True
    assert push.apply_message(state, ATTR, attr({"sid": 2, "pid": 6, "value": 1})) == {"bin_full": False}


def test_get_properties_reply():
    state = make_state()
    msg = attr({"sid": 2, "pid": 8, "code": 0, "value": 4}, method="get_properties")
    assert push.apply_message(state, ATTR, msg) == {"cycles": 4}


def test_online():
    state = make_state()
    assert push.apply_message(state, "devsrpc/online/dev1", {"method": "online", "params": 1}) == {"online": True}
    assert push.apply_message(state, "devsrpc/online/dev1", {"method": "online", "params": 0}) == {"online": False}


def test_unchanged_value_returns_none():
    assert push.apply_message(make_state(), ATTR, attr({"sid": 2, "pid": 8, "value": 0})) is None


def test_ignored_messages():
    state = make_state()
    before = make_state()
    for topic, payload in [
        (ATTR, attr({"sid": 1, "pid": 6, "value": 2})),
        (ATTR, attr({"sid": 2, "pid": 3, "code": 0})),
        (ATTR, attr({"sid": 2, "pid": 2, "value": 1})),
        ("devsrpc/attr/other", attr({"sid": 2, "pid": 6, "value": 2})),
        ("devsrpc/online/other", {"method": "online", "params": 1}),
        ("devsrpc/event/dev1", {"method": "event_occured", "params": {"did": "0", "sid": 2, "eid": 1, "arguments": []}}),
        (ATTR, {"method": "event_occured", "params": {"did": "0", "sid": 2, "eid": 1}}),
        (ATTR, {"method": "properties_changed", "params": {"sid": 2, "pid": 6, "value": 2}}),
        (ATTR, attr({"sid": 2, "pid": 6, "code": -2, "value": 2})),
        (ATTR, attr({"sid": 2, "pid": 8, "value": "5"})),
        (ATTR, attr({"sid": 2, "pid": 8, "value": True})),
        (ATTR, {"method": "properties_changed", "params": [1, "x", None]}),
        ("devsrpc/online/dev1", {"method": "online", "params": 2}),
        ("devsrpc/online/dev1", {"method": "online", "params": "1"}),
        (ATTR, [1, 2]),
        (ATTR, "text"),
        (ATTR, None),
        ("bad", attr({"sid": 2, "pid": 6, "value": 2})),
    ]:
        assert push.apply_message(state, topic, payload) is None
    assert state == before
