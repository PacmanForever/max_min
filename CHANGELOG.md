

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