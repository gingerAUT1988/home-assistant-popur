"""Apply Popur MQTT push messages to the device state."""
import re
from datetime import datetime, timezone


def _time(value):
    # "" means "not set". Keep it: apply_message drops None, so "" is the only way to clear the value.
    return value if isinstance(value, str) and (value == "" or re.fullmatch(r"\d{2}:\d{2}", value)) else None


_ATTR_PIDS = {
    2: ("status", lambda v: v if type(v) is int and v in (0, 1, 3) else None),
    3: ("manual_mode", lambda v: v == 1),
    4: ("curious_cat", lambda v: v == 1),
    5: ("leveling", lambda v: v if isinstance(v, int) and not isinstance(v, bool) else None),
    6: ("bin_full", lambda v: v == 2),
    8: ("cycles", lambda v: v if isinstance(v, int) and not isinstance(v, bool) else None),
    11: ("total_cycles", lambda v: v if isinstance(v, int) and not isinstance(v, bool) else None),
    13: ("dnd", lambda v: v == 1),
    14: ("dnd_start", _time),
    15: ("dnd_end", _time),
    17: ("display", lambda v: v if type(v) is int and 1 <= v <= 5 else None),
    18: ("wait_time", lambda v: v if isinstance(v, int) and not isinstance(v, bool) else None),
}


def apply_message(state: dict, topic: str, payload: dict) -> dict | None:
    """Update `state` in place from one MQTT message and return the changed keys.

    Maps the sid 2 pids in _ATTR_PIDS on devsrpc/attr/<devid>, and devsrpc/online/<devid> to online.
    Returns None for all other messages and when no value changes.
    """
    try:
        _, _, devid = topic.split("/")
        device = state.get(devid)
        if device is None or not isinstance(payload, dict):
            return None
        method = payload.get("method")
        params = payload.get("params")
        found = {}
        if topic.startswith("devsrpc/online/") and method == "online" and params in (0, 1):
            found["online"] = params == 1
        elif topic.startswith("devsrpc/attr/") and method in ("properties_changed", "get_properties") and isinstance(params, list):
            for entry in params:
                if not isinstance(entry, dict) or entry.get("sid") != 2 or "value" not in entry or entry.get("code", 0) != 0:
                    continue
                mapped = _ATTR_PIDS.get(entry.get("pid"))
                if mapped and (value := mapped[1](entry["value"])) is not None:
                    found[mapped[0]] = value
        changed = {key: value for key, value in found.items() if device.get(key) != value}
        device.update(changed)
        return changed or None
    except Exception:
        return None


_TRIGGERS = {256: "automatic", 257: "side_button", 258: "app"}


def _int_field(value):
    return value if isinstance(value, int) and not isinstance(value, bool) else None


def _time_field(value):
    try:
        if isinstance(value, (str, int)) and not isinstance(value, bool):
            return datetime.fromtimestamp(int(value), timezone.utc).isoformat()
    except Exception:
        pass
    return None


def parse_cycle_done(topic: str, payload: dict, seen: dict) -> tuple[str, dict] | None:
    """Return (devid, attributes) for an eid 1 "cleaning done" event, or None.

    `seen` maps devid to the last cycle start. The device sometimes sends the
    same event two times, about 1 s apart: the copy returns None.
    """
    try:
        parts = topic.split("/")
        if len(parts) != 3 or parts[:2] != ["devsrpc", "event"] or not isinstance(payload, dict):
            return None
        devid = parts[2]
        params = payload.get("params")
        if payload.get("method") != "event_occured" or not isinstance(params, dict):
            return None
        if params.get("sid") != 2 or params.get("eid") != 1 or not isinstance(params.get("arguments"), list):
            return None
        values = {a["piid"]: a["value"] for a in params["arguments"] if isinstance(a, dict) and "piid" in a and "value" in a}
        if values.get(3) is not None and values.get(3) == seen.get(devid):
            return None
        seen[devid] = values.get(3)
        trigger = values.get(12)
        if trigger is not None:
            trigger = _TRIGGERS.get(trigger, "unknown") if isinstance(trigger, int) and not isinstance(trigger, bool) else None
        return devid, {
            "visit_start": _time_field(values.get(1)),
            "visit_duration": _int_field(values.get(2)),
            "cycle_start": _time_field(values.get(3)),
            "cycle_duration": _int_field(values.get(4)),
            "trigger": trigger,
        }
    except Exception:
        return None


def parse_firmware(topic: str, payload: dict) -> tuple[str, str] | None:
    """Return (devid, fw_ver) from an aithingsIO.info message, or None.

    The message also has the device token, MAC, IP and Wi-Fi name: read fw_ver only, never log the payload.
    """
    try:
        parts = topic.split("/")
        if len(parts) != 3 or parts[:2] != ["devsrpc", "info"] or not isinstance(payload, dict):
            return None
        params = payload.get("params")
        if payload.get("method") != "aithingsIO.info" or not isinstance(params, dict):
            return None
        fw_ver = params.get("fw_ver")
        if isinstance(fw_ver, str) and fw_ver:
            return parts[2], fw_ver
        return None
    except Exception:
        return None
