

# 0.3.19 - 2026-02-10
## Fixed
- **Record Enforcement**: Hardened the logic that ensures user-configured initial values (floors/ceilings) are always respected. Added defensive checks in both data processing and state reporting to prevent calculated or restored values from overriding explicitly set boundaries.

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