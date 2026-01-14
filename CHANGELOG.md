# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

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