# 0.3.59 - 2026-06-08
## Fixed
- **Surgical initial-value reload regression**: Changing only one initial value (for example `yearly_max` or `all_time_max`) no longer gets canceled when another sensor type from the same period restores successfully during the same reload. Restore acceptance is now tracked per `(period, type)`, so the edited Max/Min initial is applied correctly instead of being re-seeded from the current source value such as `0`.
## Added
- **Reload regression coverage**: Added restore-path tests for mixed Max/Min reloads after surgical resets, closing the gap that let this options-flow regression slip through.

# 0.3.58 - 2026-06-07
## Fixed
- **Daily max/min continuity after midnight**: When a non-cumulative source sensor still exposes yesterday's numeric value just after midnight but has not published a fresh state yet, daily Max/Min entities now fall back to the tracked `end_value` instead of becoming `unknown`. Weekly/monthly/yearly stale-state protection remains unchanged.

# 0.3.57 - 2026-05-29
## Fixed
- **Max/min unavailable reset seed is now provisional**: When a non-cumulative source sensor is unavailable at the period boundary, Max/Min entities still use the last `end_value` to stay numeric at reset time, but that carried value is now treated as a placeholder only. The first fresh source update in the new period replaces it for both `max` and `min`, so yesterday's closing value no longer survives as today's real extreme.

# 0.3.56 - 2026-05-24
## Fixed
- **Max/min restart continuity across unavailable midnight resets**: Max and Min sensors now persist and restore the period `end_value`, so after a Home Assistant restart the next daily/weekly/monthly/yearly reset can still seed from the last known reading when the source sensor has not published yet. This prevents entities from falling to `unknown` at the boundary until the source updates again.

# 0.3.55 - 2026-05-04
## Fixed
- **Stale measurement state no longer contaminates broader period resets**: Non-cumulative source sensors that keep yesterday's value after the boundary (for example an inverter-provided daily peak sensor at Monday 00:00) are no longer used to seed weekly/monthly/yearly resets until the source publishes a fresh state in the new period.

# 0.3.54 - 2026-04-30
## Fixed
- **Pytest 9 test compatibility**: Overrode the Home Assistant test plugin's autouse `enable_event_loop_debug` fixture with a local synchronous fixture so synchronous tests no longer fail setup with `PytestRemovedIn9Warning`.

# 0.3.53 - 2026-04-30
## Improved
- Refactored the coordinator, sensor restore flow, and config flow into smaller internal helpers without changing reset semantics.
- Consolidated legacy patch-style tests into canonical test modules and kept the suite at full coverage.
## Changed
- Updated the README and contribution guide to match current behavior for one-shot initial values, delta restore continuity, dead-zone handling, and the recommended test command.

# 0.3.52 - 2026-04-07
## Fixed
- **Startup ordering: delta sensors no longer drop to 0 on HA restart**. When the source sensor is unavailable at boot (common), the watchdog and state listener were running *before* RestoreEntity had restored state. This caused a false reset (`last_reset=None` → `_is_reset_due=True` → `_pending_start_reanchor` set), and the first real state change overwrote the restored `start`/`end` with the current value, wiping the delta to 0. Fix: moved startup catch-up and all listeners to a new `start_listeners()` method called *after* platform setup. The periodic watchdog timer is also deferred to `start_listeners()`.
- **Safety net in `update_restored_data()`**: accepting valid restored `start`/`end` now clears `_pending_start_reanchor` for that period, preventing stale reanchor flags from overriding restored data.
- **Watchdog leak on unload**: `async_unload()` now properly cancels the periodic watchdog timer.

# 0.3.51 - 2026-04-06
## Fixed
- **Timezone-safe restore period validation**: Restored `last_reset` values are now normalized to local time and validated using real period windows (`period_start <= ts < next_period_start`). This prevents valid restored states from being incorrectly rejected as stale, which could trigger phantom resets.
- **Delta continuity on partial restore**: If a restored Delta state has only the numeric state (missing `start_value`/`end_value` and `last_reset`), boundaries are now reconstructed from the live source value (`end = source`, `start = end - delta`) to avoid restart/reload drops to `0`.
## Added
- **Reset diagnostics in entity attributes**: Sensors now expose `last_reset_reason` and `last_reset_triggered_at` to make root-cause analysis of resets immediate (scheduler/watchdog/inline/backup/early_offset).
- **Regression coverage**: Added tests for timezone restore acceptance, Delta reconstruction without `last_reset`, and reset diagnostics attributes.

# 0.3.50 - 2026-04-02
## Fixed
- **Delta restore reconstructs boundaries when attributes missing**: After a Home Assistant restart, if a delta sensor's restored state lacked `start_value`/`end_value` attributes (e.g. from older states), the sensor was re-anchoring start/end to the current source value, causing a transient delta=0 in the graph. The restore path now reconstructs boundaries from the restored delta value and the current source reading (`end = source`, `start = end - delta`), preserving continuity across restarts.

# 0.3.49 - 2026-03-23
## Fixed
- **Restore accepts same-period state**: Restored data is now accepted if `last_reset` is within the same period (year, month, week, day) instead of requiring an exact match to the period start. This prevents unwanted resets to zero for yearly/monthly/weekly/daily sensors after Home Assistant restarts, ensuring continuity for all period types. Logs a warning if restore is rejected for being from a previous period.



# 0.3.48 - 2026-03-09
## Fixed
- **Initials re-applied on every restart**: Root cause — `__init__` seeded `tracked_data` with initial values, `first_refresh` enforced them as floor/ceiling, and `get_value()` perpetually returned them over real data. All three paths now removed. Initials only apply via `apply_pending_initials()` for periods without a valid restore.
- **Restore guard too strict**: `!= entry_id` rejected pre-v0.3.47 states (which have no `config_entry_id` attribute). Changed to permissive guard that only rejects when `config_entry_id` is present AND different (backward compatible).
## Added
- **`_restore_accepted` tracking**: `update_restored_data()` marks periods that received valid restored state. `apply_pending_initials()` skips those periods, ensuring initials are truly one-shot (creation only, never on restart).
- **4 regression tests**: Restart does not re-apply max/min initials, restart after reset does not re-bleed initials, restart does not recompute delta start, surgical reset blocks restore and enables initial.

# 0.3.47 - 2026-03-09
## Fixed
- **Delta race condition at reset**: Reset now uses conservative seed + re-anchor on first real sensor update, preventing stale values when source sensor also resets at midnight.
- **Seed rounding inconsistency**: `_compute_reset_seed` now applies `round(..., 4)` matching `_handle_sensor_change`, preventing floating-point drift in delta calculations.
- **Dead zone froze max/min/end**: Dead zone window now correctly updates max, min, and end values — only skips start initialization to avoid race conditions.
- **Legacy migration corruption**: Removed v0.3.40 migration code that re-applied `initial_delta` offset on every restart/reload, progressively corrupting start values.
- **Fallback seed rounding**: `_compute_reset_seed` fallback to `end_val` now rounds consistently.
- **Stale restore on delete+recreate**: Sensors now store `config_entry_id` in state attributes and skip restore when the entry ID doesn't match, preventing old values from overriding new initial values.
## Changed
- **Initial values are one-shot**: Configured initial values now only apply at entry creation (seeding). They no longer act as persistent floor/ceiling on resets, restores, or consistency checks.
- **Sensor name labels**: Changed from `Max`/`Min`/`Delta` to `(Max)`/`(Min)`/`(Delta)` for clearer display.

# 0.3.46 - 2026-03-07
## Fixed
- **Surgical reset double-reload**: Moving `CONF_RESET_HISTORY` cleanup before update listener registration prevents a second reload that overwrites initial values with stale restored data.
## Improved
- **Period field ordering**: Optional settings fields now sorted chronologically (daily → weekly → monthly → yearly → all time) regardless of selection order.

# 0.3.45 - 2026-03-01
## Fixed
- **OptionsFlow/ConfigFlow "Unknown error occurred"**: Root cause found — v0.3.41 replaced `vol.Coerce(float)` with a raw Python callable (`_coerce_localized_float`) in form schemas. HA cannot serialize raw callables for the frontend, causing the form submission to crash. Fixed by using `selector.NumberSelector(mode="box", step="any")` which HA serializes correctly and still accepts decimal input.

# 0.3.44 - 2026-03-01
## Fixed
- **Reverted OptionsFlow to v0.3.41 baseline**: Removed all normalization overengineering (`_normalize_multi_select`, `_normalize_device_id`, `_normalize_offset`, try/except wrappers) introduced in v0.3.42-v0.3.43 that caused persistent "Unknown error occurred". Restored the exact working code from v0.3.41 with only a duplicate `CONF_DEVICE_ID` guard fix.

# 0.3.43 - 2026-03-01
## Fixed
- **OptionsFlow robustness overhaul**: Moved normalization helpers (`_normalize_multi_select`, `_normalize_device_id`, `_normalize_offset`) to module level. Restored `suggested_value` on DeviceSelector so previously selected device is remembered. Wrapped entire method bodies (including form construction) in `try/except` so schema-building errors are caught. Removed duplicate `CONF_DEVICE_ID` guard in `async_step_optional_settings`.

# 0.3.42 - 2026-03-01
## Fixed
- **OptionsFlow Submit Crash**: Fixed a regression in options form defaults where an indentation error could raise `UnboundLocalError` during submit, surfaced in Home Assistant UI as `Unknown error occurred`.
- **Defensive Error Handling in OptionsFlow**: Added guarded exception handling in options steps (`init` and `optional_settings`) to prevent generic hard-failures and return a controlled form error.
## Added
- **Operational Diagnostics**: Added explicit exception logging for unexpected options-flow failures so root causes are visible in Home Assistant logs.
- **User-facing Error Translation**: Added `unknown_error` translation key for config/options flows to show a clear fallback message instead of HA's generic unknown error banner.

# 0.3.41 - 2026-02-28
## Fixed
- **Localized Decimal Parsing**: Initial values now accept both dot and comma decimal separators (e.g. `52.3` and `52,3`) consistently across ConfigFlow, OptionsFlow, coordinator enforcement, and Delta sensor initialization.
- **Delta Initial Value Enforcement**: Added regression coverage to ensure `initial_delta` with comma-decimal input is parsed and applied correctly.

# 0.3.40 - 2026-02-27
## Fixed
- **Delta Legacy State Migration**: Fixed an issue where upgrading to v0.3.39 caused existing Delta sensors with an initial value to drop significantly. The integration now detects legacy states (where the start value was not offset) and automatically migrates them, restoring the correct trajectory (initial value + increments).

# 0.3.39 - 2026-02-27
## Fixed
- **Delta Initial Value Flatline**: Fixed a critical bug where Delta sensors configured with an initial value would flatline instead of incrementing. The logic was refactored from a "floor" pattern to an "offset" pattern, allowing natural increments to add on top of the initial value correctly.

# 0.3.38 - 2026-02-26
## Improved
- **Optional Settings Description**: Form now shows "Leave empty to disable enforcement", clarifying that empty fields mean no floor/ceiling is applied.
## Changed
- **CI: Daily Compatibility Workflow**: Fixed install order (test deps first, HA after with `--upgrade`) to prevent `pytest-homeassistant-custom-component` from downgrading HA. Added HA `dev` branch to matrix, auto-issue creation on scheduled failure, `fail-fast: false`, pip cache, and version display step.
- **CI: Unit & Component Workflows**: Applied consistent install order and pip cache.
- **README**: Added Delta initial value documentation, fixed HACS repository URL.

# 0.3.37 - 2026-02-26
## Fixed
- **Delta Initial Values Missing from UI**: When creating or editing an entry with only Delta type selected, the optional settings form was empty (no fields shown). Now shows `Initial Delta Value` fields for each configured period.
- **Entry Title Ignoring Delta in OptionsFlow**: When editing an entry via options, the title suffix only considered Max and Min. Selecting only Delta produced "Sensor (Max/Min)" instead of "Sensor (Delta)". Now uses the same suffix builder as ConfigFlow.
## Added
- **Initial Delta Value Support**: Delta sensors can now have an initial value configured, acting as a floor — the sensor shows the initial value until the real computed delta (end - start) exceeds it. Useful for replacing another integration mid-period.
- **NR-19**: Regression test — DeltaSensor initial_delta floor enforcement.

# 0.3.36 - 2026-02-25
## Fixed
- **Scheduler Callbacks Not Running in Event Loop**: Timer callbacks passed to `async_track_point_in_time` were bare lambdas without `@callback` decorator, causing HA to run them in the thread-pool executor instead of the event loop. This meant `async_write_ha_state()` never propagated the reset to HA's state machine at midnight — the graph only updated when the source sensor next reported (minutes or hours later). Replaced lambdas with `@callback`-decorated inner functions.
- **Measurement Sensor Seed Fallback**: `_compute_reset_seed()` now falls back to the last recorded `end` value for ALL sensor types when the source is unavailable at reset time (e.g. UV index at night). Previously, this fallback was restricted to cumulative sensors, causing measurement entities to go unavailable and HA to render a flat stale-value line.
## Changed
- **Removed Custom `available` Overrides**: `MaxSensor`, `MinSensor`, and `DeltaSensor` no longer override the `available` property. Entities now delegate to `CoordinatorEntity.available`, showing `unknown` in HA (clean graph break) instead of `unavailable` (flat line).
- **Dead Code Cleanup**: Removed unused `import inspect` and unreachable entity notification loop from `_perform_reset`.
## Added
- **NR-16**: Regression test — measurement sensor with end_val seeds correctly when source unavailable.
- **NR-17**: Regression test — measurement sensor with no end_val yields seed=None.
- **NR-18**: Regression test — scheduler callbacks have `@callback` decorator (`_hass_callback` marker).

# 0.3.35 - 2026-02-22
## Changed
- **Reset Architecture Refactor** (consensus GPT + Claude): Unified all reset paths through a single `ensure_period_current()` entry point, eliminating 5 divergent code paths.
- **`last_reset = period_start`**: Reset timestamp now records the canonical period boundary (e.g. midnight) instead of the wall-clock moment, eliminating visual drift in `last_reset` attributes.
- **Extracted `_compute_reset_seed()`**: Seed policy (measurement vs cumulative fallback) is now a standalone pure function, independently testable.
- **Simplified `_is_reset_due()`**: Removed optional decision-path parameters (`require_offset_window`, `expected_reset_time`, `allow_missing_last_reset`), reducing combinatorial paths from 16 to 1.
## Improved
- **Backup timer simplified**: Now calls `ensure_period_current()` like all other triggers, no special `_ensure_backup_reset` method.
- **Inline reset detection**: Uses `ensure_period_current()` instead of separate `_is_reset_due()` call with custom parameters.
## Added
- **Non-regression contract** (`test_non_regression.py`): 15 mandatory scenarios covering reset timing, DST, restore edge cases, seed policy, offset, inline, surgical reset, and initial value enforcement.

# 0.3.33 - 2026-02-21
## Fixed
- **Measurement Reset Carry-over**: Reset fallback to previous `end` value is now restricted to cumulative sources only (`total` / `total_increasing`).
- **UV/Measurement Midnight Behavior**: Measurement sensors no longer reuse stale previous-period values when the source is unavailable/non-numeric at boundary time.
## Added
- **Regression Coverage**: Added/updated tests to enforce measurement vs cumulative fallback behavior during resets.

# 0.3.32 - 2026-02-20
## Fixed
- **Missed Midnight Reset Catch-up**: Added an immediate startup/reload catch-up check so overdue period resets are enforced without waiting for the next sensor update.
- **Reset Seed Robustness**: When source state is unavailable/unknown/non-numeric at reset time, the coordinator now seeds the new period from the last valid `end` value instead of leaving max/min empty.
- **Integration Visibility**: Reverted `integration_type` to `hub` so Max Min appears in the main integrations list.
## Added
- **Regression Coverage**: Added tests for startup catch-up and unavailable-source reset fallback behavior to prevent recurrence of delayed morning corrections.

# 0.3.31 - 2026-02-18
## Fixed
- **Midnight Reset Drift on Measurement Sensors**: Offset/dead-zone logic now applies only to cumulative sources (`state_class: total` / `total_increasing`). Measurement sensors (temperature, humidity, pressure, etc.) now reset exactly at period boundaries.
## Changed
- **Offset Scope Clarification**: Coordinator scheduling, inline reset gating, and watchdog offset checks now use the source sensor class to decide whether offset protection must be applied.

# 0.3.30 - 2026-02-16
## Fixed
- **Midnight Reset Reliability**: Refactored reset decision logic into a single shared path to avoid divergent behavior between scheduler, watchdog, inline and backup flows.
- **Missed Reset Recovery Latency**: Added per-period backup reset verification shortly after the scheduled reset to prevent 10-15 minute late recoveries when a timer is missed.
- **Delta Unit Restore**: Fixed Delta sensor startup restore to preserve unit and device class from last state, avoiding recurring unit-change warnings after HA restart.
## Improved
- **Reset Traceability**: Added explicit reset source tracking (`scheduler`, `watchdog`, `backup`, `inline`, `early_offset`) to simplify diagnostics in real deployments.

# 0.3.29 - 2026-02-13
## Added
- **Reset Watchdog**: New failsafe mechanism that checks every 10 minutes for missed resets (due to HA restart, high load, or errors) and triggers them automatically.
- **Chain Break Protection**: Ensures that the next reset is *always* scheduled, even if the current reset logic encounters an unexpected error (like an unavailable sensor), preventing the integration from stopping forever.
## Improved
- **Coordinator Initialization**: Cleaned up initialization logic and standardized `hass` object usage for better stability.

# 0.3.28 - 2026-02-12
## Fixed
- **Manifest Syntax**: Fixed a JSON syntax error (trailing comma) in `manifest.json` that caused validation failures.

# 0.3.27 - 2026-02-12
## Improved
- **Timezone Robustness**: Implemented strict `start_of_local_day` logic for monthly and yearly resets. This ensures resets happen precisely at user's local midnight regardless of DST transitions or timezone offsets, robustly handling the edge cases where simple time replacements could fail.
## Fixed
- **Monthly/Yearly Reset Logic**: Fixed potential offset errors in monthly and yearly reset calculations by deriving the reset time from the local calendar date rather than preserving the previous timestamp's offset.

# 0.3.26 - 2026-02-11
## Fixed
- **Reset Scheduling Accuracy**: Fixed an issue where daily and weekly resets could occur at the wrong time (e.g., 2:00 AM instead of 00:00) due to timezone miscalculations. Now uses Home Assistant's `start_of_local_day` to guarantee resets happen exactly at local midnight.
## Changed
- **Integration Visibility**: Changed integration type to "hub" so it appears in the main integrations list instead of being hidden under Helpers.

# 0.3.25 - 2026-02-10
## Fixed
- **Delta Sensor Persistence**: Fixed a major bug where Delta sensors (Daily, Weekly, Monthly, Yearly, All-time) became "Unavailable" after a Home Assistant restart. Start and end values are now correctly restored from entity attributes to ensure continuity.
- **Data Structure Consistency**: Unified the internal data skeleton to prevent missing keys during early state restoration.
- **Surgical Reset Bypass**: Fixed a critical bug where `_check_consistency()` was propagating values to periods marked for surgical reset, effectively bypassing the reset mechanism. Consistency checks now respect `reset_history` and will not overwrite sensors undergoing targeted reset.
## Added
- **Comprehensive Test Coverage**: Added 16 new regression tests covering all fixes from v0.3.22-v0.3.25 (surgical reset, floating point rounding, Delta persistence, history preservation, and initial value enforcement). Total test count: 175 tests with 97% code coverage.

# 0.3.24 - 2026-02-10
## Fixed
- **History Preservation**: Removed conservative checks that could ignore restored historical data during integration updates or reloads.
- **Robust Restoration**: Ensured that historical values are recovered even if reset metadata is missing, as long as they represent more extreme values than the current state.

# 0.3.23 - 2026-02-10
## Fixed
- **Floating Point Precision**: Added rounding (4 decimal places) to all sensor inputs to eliminate insignificant variations caused by floating point noise (e.g., 45.999999999999999).

# 0.3.22 - 2026-02-10
## Added
- **Surgical History Reset**: Changed the history reset logic to be automatic and precise. If you change an initial value (floor/ceiling) for a specific sensor, only that sensor's history will be cleared. Other sensors in the same configuration remain untouched.
## Changed
- **Automatic Reset Management**: Removed the manual "Reset historical records" checkbox as the integration now detects changes and handles resets intelligently.

# 0.3.21 - 2026-02-10
## Added
- **Reset History Option**: Added a new "Reset historical records" checkbox in the options flow. Checking this will wipe internal memory (max/min/delta) on the next restart, allowing a fresh start with new initial values.
## Fixed
- **Improved Initial Value Fallback**: Refined how initial values are retrieved from config to ensure total priority of options (UI) over original configuration.
- **Enhanced Debug Logging**: Added detailed logs to trace configuration application and potential value overrides in real-time.

# 0.3.20 - 2026-02-10
## Fixed
- **Ultimate Record Protection**: Rewrote the logic for initial values to be absolutely bulletproof. The sensors now check the configuration directly on every single state read, making it virtually impossible for any internal logic or external data restoration to override a user-configured floor/ceiling.

# 0.3.18 - 2026-02-10
## Fixed
- **Hardened Record Enforcement**: Added defensive checks to ensure user-configured initial values (floors/ceilings) are always respected, even against cross-period consistency propagation.
- **UI Safety**: Optional setting fields (Initial values) now appear empty by default. Sending an empty field will no longer overwrite or clear existing values, preventing accidental data loss.
- **Immediate Value Application**: Configured initial values are now applied immediately to the sensor state without waiting for the next source update.

# 0.3.17 - 2026-02-10
## Fixed
- **Initial values lost on settings update**: Fixed a bug where opening the Options Flow would clear existing initial values because the form fields appeared empty. The UI now correctly remembers and suggests currently configured values.
- **Consistency vs Initial values conflict**: Improved the cross-period consistency check. Now, even if a narrower period (like Daily) has a value, it cannot override a user-configured floor/ceiling in a broader period (like Yearly). User-configured initials now have absolute priority.

# 0.3.16 - 2026-02-10
## Fixed
- **Record inconsistencies between periods**: Added a cross-period consistency check. Broad periods (like All-time) now automatically inherit more extreme records from narrower ones (like Yearly/Monthly). This ensures that if Yearly Min is -1.3, All-time Min is also at least -1.3, even if the All-time sensor was added later or had a less extreme initial value.
- **Sensor update optimization**: The integration now only triggers a Home Assistant state update if a value actually changes, reducing unnecessary database writes for Delta sensors.

# 0.3.15 - 2026-02-10
## Changed
- **Implemented `runtime_data`**: Transitioned from `hass.data[DOMAIN]` to the modern `entry.runtime_data` pattern for better performance and alignment with Home Assistant best practices.
- **Improved Source Mirroring**: All sensors (Max, Min, and Delta) now force `state_class: measurement`. This prevents Home Assistant from flagging "decrease detected" errors when periods reset, especially for cumulative sensors like rain.
- **Filtered Device Classes**: Problematic device classes (energy, water, gas) that enforce specific statistics behavior are now filtered out when mirroring, while keeping their units of measurement.
- **Integration Metadata**: Corrected `integration_type` to `"helper"` and fixed repository URLs in `manifest.json`.
- **Translations Validation**: Fixed strings.json and en.json missing required step descriptions, resolving HACS validation errors.

## Fixed
- **Daily Compatibility CI**: Updated GitHub workflows to use Python 3.13, resolving failures in the nightly compatibility checks with Home Assistant beta.
- **Test Suite Modernization**: All 151 unit and component tests updated to support the `runtime_data` architecture.

# 0.3.14 - 2026-02-09
## Fixed
- **Initial values not applied on integration reload**: `async_config_entry_first_refresh` now enforces configured initial values after initialization. Previously, when modifying initial values via Options and reloading the integration, the current sensor value would override the configured initial, making it impossible to set a floor/ceiling without waiting for a period reset.

# 0.3.13 - 2026-02-08
## Fixed
- **Delta sensors showing error on cumulative sources**: `DeltaSensor.state_class` now always returns `"measurement"` instead of mirroring the source sensor's `state_class`. Previously, Delta sensors for `total_increasing` sources (e.g. rain accumulation) inherited that class, causing HA to flag them as inconsistent when the delta reset to 0 at period boundaries.
- **Initial values ignored after period reset**: `_handle_reset` now enforces configured initial max/min values as floor/ceiling. Previously, period resets (daily/weekly/monthly/yearly) would set max/min to the current sensor value, completely ignoring the user-configured initial values.

# 0.3.12 - 2026-02-08
## Fixed
- **Inline reset respects offset**: The inline period-boundary reset (safety net for missed scheduled resets) now correctly defers to the configured offset for cumulative sensors. Previously it would fire immediately at midnight, bypassing the offset delay.
- **Early reset skipping other periods**: When a cumulative sensor triggered an early reset for one period, the code used `return` instead of `continue`, skipping all remaining periods in the loop.
- **Delta entities deleted on reload**: Delta sensor entities were incorrectly removed on every reload/restart because `expected_unique_ids` didn't include the `_delta` suffix.

## Improved
- **Extracted base class**: `MaxSensor`, `MinSensor`, and `DeltaSensor` now inherit from `_BaseMaxMinSensor`, eliminating ~200 lines of duplicated code (sensor.py reduced from 382 to 179 lines).
- **Extracted shared methods**: `_compute_next_reset()` and `_schedule_single_reset()` eliminate duplicated reset scheduling logic between `_schedule_resets` and `_handle_reset`.
- **Configured initial enforcement**: Configured initial max/min values are now enforced as floor/ceiling after restore, preventing stale restored values from overriding user-configured bounds.
- **Stale restore protection**: Restored data without `last_reset` is ignored when the coordinator has already initialized the period, preventing old values from bleeding into new periods.

# 0.3.11 - 2026-02-06
## Changed
- **Reverted Grace Period**: Validating user feedback, the "magic" 5-minute grace period has been removed. The integration now strictly follows the configured offset. Users must ensure their offset covers any sensor latency.

# 0.3.10 - 2026-02-06
## Improved
- **Late Reset Handling**: Added a 5-minute "grace period" after the scheduled reset. If a cumulative sensor (like rain) resets to 0 shortly *after* midnight (even if no offset is configured), the integration will now detect it and correct the Daily Max/Min values immediately.

# 0.3.9 - 2026-02-05
## Fixed
- **UI**: Fixed an issue where creating a sensor with only "Delta" type selected would show an empty "Optional Settings" form. Now it skips this step automatically.
- **UI**: Fixed naming convention. Sensors with only "Delta" type now have the "(Delta)" suffix in the title instead of the incorrect "(Max/Min)".

# 0.3.8 - 2026-02-05
## Fixed
- Fixed missing import for Delta sensor type in config flow which caused a crash.
- Added comprehensive unit tests for Delta sensor logic and Config Flow.

# 0.3.7 - 2026-02-05
## Added
- **Delta Sensor**: Enabled the "Delta" sensor option in the configuration flow. This sensor tracks the difference (end - start) over the configured period. Documentation added.

# 0.3.6 - 2026-02-05
## Fixed
- Fix: Cumulative sensors (like rain gauges) that reset to 0 shortly after midnight (within the offset window) are now correctly detected. Previously, these were ignored as "dead zone" updates, causing the daily max to not reset until the next restart.

# 0.3.5 - 2026-01-20
## Improvements
- The min/max value is now updated immediately after the daily reset. The frontend now reflects the correct value at 00:00:00 without waiting for a new update from the source sensor.

# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [0.3.4] - 2026-01-18

### Fixed
- **Reset Reliability**: Implemented `last_reset` attribute tracking to robustness of daily resets. This ensures that if the system restarts or the component reloads after the scheduled reset time, the sensor will correctly identify stale data and reset itself, preventing "delayed" resets or carrying over old values.

## [0.3.3] - 2026-01-16

### Fixed
- **UI Consistency**: The "Offset/Margin" field in the options flow is now correctly marked as optional (no asterisk), matching the behavior in the initial setup flow. This cosmetic fix ensures clearer UI for users.

## [0.3.2] - 2026-01-15

### Fixed
- **Attribute Inheritance**: improved reliability of unit of measurement and device class inheritance. Sensors now cache these attributes from the source sensor, ensuring they are preserved even if the source sensor becomes temporarily unavailable (e.g. during a restart). Restored sensors will also attempt to load these attributes from their last known state.

## [0.3.1] - 2026-01-15

### Fixed
- **Options Flow Logic**: When editing the integration options, "Initial Value" fields are now empty by default. This prevents accidental re-application of old initial values which could overwrite valid historical data on reload. Initial values are only set if explicitly provided again.
- **UI Labels**: Fixed missing translation for "Offset/Margin" in the options dialog.

## [0.3.0] - 2026-01-15

### Added
- **Offset / Margin**: New configuration option to set a time margin (in seconds) for the period reset. This helps resolve issues with unsynchronized devices or source sensors that restart just before the period end.
- **Dead Zone Logic**: Updates received within the offset window (before and after reset time) are now ignored to prevent incorrect data from polluting the next period.

## [0.2.5] - 2026-01-14

### Fixed
- **Critical**: Restored Max/Min values are now correctly preserved on restart. Previously, sensors would reset to the current source value, causing data loss (e.g., Max dropping to current value).
- Fixed entity cleanup logic to ensure stale entities are removed when options change.

## [0.2.5] - 2026-01-14

### Fixed
- **Critical Data Loss on Restart**: Fixed an issue where Max/Min sensors would reset to the *current* source value on restart, losing historical data for the current period. This caused Max values to drop and Min values to rise incorrectly. Implemented `RestoreEntity` to preserve states across restarts.
- **Entity Cleanup**: Fixed stale entities remaining after changing options (e.g., removing a period or type).

## [0.2.4] - 2026-01-14

### Changed
- **Config Flow Validation**: "Basic Settings" and "Optional Settings" steps now correctly enforce required fields.
- **UI Tweaks**: "Device" selection moved to the "Optional Settings" step to reduce clutter.

## [0.2.0] - 2026-01-14

### Added
- **Multi-period support**: Now you can select multiple periods (Daily, Weekly, Monthly, Yearly, All Time) for a single source sensor. This creates multiple entities automatically (e.g., "Sensor Daily Max", "Sensor Weekly Max").

### Changed
- **Breaking Change**: Configuration schema updated. `period` (single selection) replaced with `periods` (multiple selection).
- Codebase refactored to support list-based period management in Coordinator and Config Flow.

## [0.1.13] - 2026-01-14

### Fixed
- Fix default values in Options Flow.

## [0.1.5] - 2026-01-14

### Changed
- Improved Config Flow experience:
  - Split the creation process into two steps: "Basic Settings" and "Optional Settings".
  - Initial Min/Max values and Device selection are now in the second step.
- Improved Options Flow layout:
  - Added a collapsible "Optional settings" section for Initial Min/Max and Device selection.
  - Ensures optional fields are clearly separated from main settings.

## [0.1.4] - 2026-01-14

### Added
- Added "All time" period option for sensors that never reset.

### Changed
- Improved Config Flow layout:
  - Moved "Device" selection to the bottom of the form.
  - Grouped "Initial Min Value", "Initial Max Value", and "Device" under a logical "Options" section.
  - Added "(Optional)" suffix to optional field labels for clarity.
  - Renamed Options Flow title to "Max/Min sensor/s options".
- When removing a device from the configuration, the sensors are now correctly unlinked from said device.

## [0.1.3] - 2026-01-14

### Changed
- Improved sensor attribute inheritance: New sensors now copy `unit_of_measurement`, `device_class`, and `state_class` from the source entity.
- Updated sensor naming convention for better friendly names and entity IDs (e.g., "Sensor Name Daily Max").
- UI Improvements:
  - "New sensors" inputs in Options Flow now start empty instead of pre-filled.
  - Reordered checkboxes: "Minimum" now appears before "Maximum".
  - Renamed "New sensors" label to "Sensors" for consistency.
  - Linked Device field is now editable in Options Flow and renamed to "Device to link (optional)".
- Tests updated to maintain >95% coverage with new features.

## [0.1.2] - 2026-01-13

### Fixed
- Fixed bug where configured "Initial Max/Min" values were overwritten by the current sensor state on startup.
- Fixed an issue where the Max value could decrease if the source sensor value dropped (logic error).
- Fixed a listener leak in `coordinator.py` where sensor update listeners were not properly cleaned up on reload.

### Changed
- Improved integration titles: New instances will be named "Sensor Name - Period" (e.g., "Outside Temperature - Daily") instead of the generic "Max Min".

## [0.1.1] - 2026-01-13

### Changed
- Updated configuration dialog labels to be more descriptive.
- Reordered configuration fields to show "Initial min value" before "Initial max value".
- Added `translations/en.json` for proper localization.

### Added
- Added tests for configuration schema order and translation strings.
- Added validation to prevent `min` value being greater than `max` value in configuration.

## [0.1.0] - 2026-01-13

### Added
- Initial release of Max Min integration
- Support for max and min sensors based on selected numeric sensor
- Configurable periods: daily, weekly, monthly, yearly
- Individual or paired sensor creation
- Automatic reset at period end
- Real-time updates when source sensor changes
- HACS compatibility
- Comprehensive test suite with >95% coverage
- English documentation

### Changed
- Improved Config Flow UI labels and titles.
- Prevent modifying the period in options flow to avoid unique ID conflicts.

### Fixed
- Fixed `TypeError` when scheduling reset due to incorrect timezone handling.

### Changed

### Deprecated

### Removed

### Fixed

### Security