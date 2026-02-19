# Technical Notes & Lessons Learned

This document serves as a memory aid for AI assistants and developers to avoid recurring issues and ensure best practices are followed.

## 1. Periodic Reset Scheduling

### The Trap: `async_track_time_change`
**Do NOT** use `async_track_time_change` for scheduling resets that happen "next week", "next month", or "next year", even if you calculate the time correctly.

`async_track_time_change(hass, callback, hour=0, minute=0, second=0)` will fire **EVERY DAY** at 00:00:00, not just on the specific date you calculated. It ignores the date component of any datetime object you might have used to derive the hour/minute/second.

### The Solution: `async_track_point_in_time`
Use `async_track_point_in_time(hass, callback, datetime_obj)` when you want to schedule an event for a specific moment in the future (e.g., "Reset on Feb 1st").

**Code Pattern:**
```python
# CORRECT
reset_time = now.replace(year=now.year + 1, month=1, day=1, hour=0, minute=0, second=0, microsecond=0)
self._reset_listener = async_track_point_in_time(self.hass, self._handle_reset, reset_time)
```

**Cleanup:**
Always remember to cancel the previous listener before creating a new one to avoid memory leaks or duplicate firings.
```python
if self._reset_listener:
    self._reset_listener()
    self._reset_listener = None
```

## 2. Config Flow Aborts

### The Trap: Ignoring Return Values
Methods like `self._abort_if_unique_id_configured()` in `ConfigFlow` return a result object (dict) if they trigger an abort, or `None` if everything is fine. They do **not** raise an exception that stops flow automatically.

### The Solution
Always check and return the result.

**Code Pattern:**
```python
# CORRECT
await self.async_set_unique_id(unique_id)
abort_result = self._abort_if_unique_id_configured()
if abort_result:
    return abort_result
```

## 3. Configuration Reloading

### The Requirement
When a user changes Options (via `OptionsFlow`), the changes do not automatically apply unless you explicitly handle them.

### The Solution
1. In `async_setup_entry`, register an update listener:
   ```python
   entry.async_on_unload(entry.add_update_listener(async_reload_entry))
   ```
2. Implement the reload function:
   ```python
   async def async_reload_entry(hass: HomeAssistant, entry: ConfigEntry) -> None:
       await hass.config_entries.async_reload(entry.entry_id)
   ```

## 4. Unloading Resources

### The Requirement
When an integration is unloaded (user deletes it or HA restarts), you must clean up all listeners (timers, state listeners, etc.).

### The Solution
Implement an `async_unload` method in your coordinator or class and call it from `async_unload_entry`.

**Coordinator:**
```python
async def async_unload(self):
    if self._reset_listener:
        self._reset_listener()
```

**__init__.py:**
```python
if unload_ok:
    if entry.entry_id in hass.data[DOMAIN]:
        coordinator = hass.data[DOMAIN][entry.entry_id]
        await coordinator.async_unload()
        hass.data[DOMAIN].pop(entry.entry_id)
```

## 5. Offset Scope (Critical)

### The Trap: Applying offset to all sensor classes
Offset/dead-zone protection was introduced to absorb latency and restart artifacts from cumulative sensors near period boundaries.
If this logic is applied to normal measurement sensors (temperature/humidity/pressure), period resets are artificially delayed and can look "broken" at midnight.

### The Rule
Apply offset/dead-zone only when source `state_class` is cumulative:
- `total`
- `total_increasing`

For measurement sensors (or missing `state_class`), reset exactly at boundary time (00:00 for daily) with no offset delay.

### Where this must stay consistent
- Scheduling (`_schedule_single_reset`)
- Inline reset due-check (`_is_reset_due` path)
- Watchdog due-check
- Early reset dead-zone handling

## 6. Integration Visibility in Home Assistant UI (Critical)

### The Trap: Blindly applying generic `integration_type` guidance
For this project, changing `manifest.json` from `integration_type: "hub"` to `"helper"`
caused the integration to stop appearing alongside the rest of integrations in the main UI,
which was a user-facing regression.

### Project Rule
Keep `integration_type` as `"hub"` for Max Min.

Even if some generic Home Assistant guidance suggests `"helper"` for derived entities,
the explicit product decision for this integration is **discoverability/visibility in the
main integrations list**.

### Release Checklist Guard
Before releasing:
- Verify `custom_components/max_min/manifest.json` keeps `integration_type: "hub"`.
- If changed intentionally, document the user-visible impact in `CHANGELOG.md` and release notes.
