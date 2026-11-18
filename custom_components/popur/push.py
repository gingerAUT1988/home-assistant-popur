"""Apply Popur MQTT push messages to the device state."""

_ATTR_PIDS = {
    3: ("manual_mode", lambda v: v == 1),
    6: ("bin_full", lambda v: v == 2),
    8: ("cycles", lambda v: v if isinstance(v, int) and not isinstance(v, bool) else None),
    11: ("total_cycles", lambda v: v if isinstance(v, int) and not isinstance(v, bool) else None),
}


def apply_message(state: dict, topic: str, payload: dict) -> dict | None:
    """Update `state` in place from one MQTT message and return the changed keys.

    Maps sid 2 pid 3, 6, 8, 11 on devsrpc/attr/<devid> to manual_mode,
    bin_full, cycles, total_cycles, and devsrpc/online/<devid> to online.
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
