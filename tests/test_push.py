import importlib.util
from datetime import datetime, timezone
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
        (ATTR, attr({"sid": 2, "pid": 1, "value": 1})),
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


def test_new_pid_mapping():
    for pid, value, expected in [
        (2, 1, {"status": 1}),
        (4, 1, {"curious_cat": True}),
        (5, 3, {"leveling": 3}),
        (13, 1, {"dnd": True}),
        (14, "22:00", {"dnd_start": "22:00"}),
        (15, "07:30", {"dnd_end": "07:30"}),
        (17, 4, {"display": 4}),
        (18, 15, {"wait_time": 15}),
    ]:
        state = make_state()
        assert push.apply_message(state, ATTR, attr({"sid": 2, "pid": pid, "value": value})) == expected
        assert all(state["dev1"][k] == v for k, v in expected.items())


def test_invalid_new_values_ignored():
    state = make_state()
    before = make_state()
    for pid, value in [(2, 2), (2, True), (17, 6), (14, "7:00"), (14, 700), (18, "5")]:
        assert push.apply_message(state, ATTR, attr({"sid": 2, "pid": pid, "value": value})) is None
    assert state == before


def test_empty_time_clears():
    state = make_state()
    state["dev1"]["dnd_start"] = "22:00"
    assert push.apply_message(state, ATTR, attr({"sid": 2, "pid": 14, "value": ""})) == {"dnd_start": ""}
    assert state["dev1"]["dnd_start"] == ""


def test_presence_repeat_no_change():
    state = make_state()
    assert push.apply_message(state, ATTR, attr({"sid": 2, "pid": 2, "value": 3})) == {"status": 3}
    assert push.apply_message(state, ATTR, attr({"sid": 2, "pid": 2, "value": 3})) is None


EVENT = "devsrpc/event/dev1"


def cycle_event(piids=None):
    args = [{"piid": piid, "value": value} for piid, value in (piids or {}).items()]
    return {"method": "event_occured", "params": {"did": "0", "sid": 2, "eid": 1, "arguments": args}}


def iso(seconds):
    return datetime.fromtimestamp(seconds, timezone.utc).isoformat()


def test_cycle_done_attributes():
    seen = {}
    payload = {"method": "event_occured", "params": {"did": "0", "sid": 2, "eid": 1, "arguments": [
        {"piid": 1, "value": "1794600025"}, {"piid": 2, "value": 35}, {"piid": 3, "value": "1794600356"},
        {"piid": 4, "value": 190}, {"piid": 12, "value": 256}]}}
    assert push.parse_cycle_done(EVENT, payload, seen) == ("dev1", {
        "visit_start": iso(1794600025),
        "visit_duration": 35,
        "cycle_start": iso(1794600356),
        "cycle_duration": 190,
        "trigger": "automatic",
    })
    assert push.parse_cycle_done(EVENT, payload, seen) is None  # the device repeats the event
    payload["params"]["arguments"][2]["value"] = "1794600999"
    result = push.parse_cycle_done(EVENT, payload, seen)
    assert result is not None and result[1]["cycle_start"] == iso(1794600999)


def test_cycle_done_triggers():
    for raw, expected in [(256, "automatic"), (257, "side_button"), (258, "app"), (999, "unknown")]:
        _, attrs = push.parse_cycle_done(EVENT, cycle_event({12: raw}), {})
        assert attrs["trigger"] == expected


def test_cycle_done_rejected():
    good = cycle_event()
    for topic, payload in [
        ("devsrpc/attr/dev1", good),
        (EVENT, {**good, "method": "properties_changed"}),
        (EVENT, {**good, "params": []}),
        (EVENT, {**good, "params": {**good["params"], "eid": 2}}),
        (EVENT, {**good, "params": {**good["params"], "sid": 1}}),
        (EVENT, {**good, "params": {**good["params"], "arguments": {}}}),
        ("devsrpc/event/dev1/x", good),
        (EVENT, "text"),
    ]:
        assert push.parse_cycle_done(topic, payload, {}) is None


def test_cycle_done_missing_piids():
    assert push.parse_cycle_done(EVENT, {"method": "event_occured", "params": {"sid": 2, "eid": 1, "arguments": [
        {"piid": 2, "value": 35}, "x", {"piid": 4}]}}, {}) == ("dev1", {
        "visit_start": None, "visit_duration": 35, "cycle_start": None, "cycle_duration": None, "trigger": None})


def test_parse_firmware():
    info = {"method": "aithingsIO.info", "params": {"fw_ver": "4.1.9", "token": "x", "mac": "aa:bb"}}
    assert push.parse_firmware("devsrpc/info/dev1", info) == ("dev1", "4.1.9")
    assert push.parse_firmware("devsrpc/attr/dev1", info) is None
    assert push.parse_firmware("devsrpc/info/dev1", {**info, "params": {"token": "x"}}) is None
    assert push.parse_firmware("devsrpc/info/dev1", {**info, "params": []}) is None
