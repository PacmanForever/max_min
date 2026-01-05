# Max Min Integration Requirements

This document outlines the specific requirements for the Max Min Home Assistant integration project.

## Integration Overview

- **Name**: Max Min
- **Domain**: max_min
- **Version**: 0.1.0
- **Home Assistant**: 2024.1.0

## Functional Requirements

### Core Features
- Create max and min sensors based on a user-selected numeric sensor
- Support for periods: daily, weekly, monthly, yearly
- Ability to create individual sensors (max only or min only) or pairs (max and min)
- Sensors maintain the max/min value during the period and reset to the current source sensor value at the end of the period
- Real-time updates when the source sensor changes
- Dynamic sensor names: "Max [Source Sensor Name] [Period]", "Min [Source Sensor Name] [Period]"

### Operating Modes
- **Normal Mode**: Sensors that accumulate max/min during the selected period
- **Automatic Reset**: At the end of each period, sensors reset to the current source sensor value
- **Individual Mode**: Create only max sensor or only min sensor
- **Pair Mode**: Create both sensors (max and min)

### Configuration
- **Source Sensor**: Selection of an existing numeric sensor in HA (entity_id with domain "sensor")
- **Period**:
  - Daily (00:00-23:59 of the same day)
  - Weekly (Monday 00:00 - Sunday 23:59)
  - Monthly (Day 1 00:00 - last day of month 23:59)
  - Yearly (January 1 00:00 - December 31 23:59)
- **Types**: Max, min, or both (multiple selector)
- **Options**: Ability to change period and types after initial configuration

### Data Collection
- **Update**: Real-time when the source sensor state changes
- **Reset**: Automatic at the end of the period (exact time calculated for HA time zone)
- **Persistence**: Values maintained during the period, not persisted between restarts
- **Validation**: Only valid numeric values (float), ignore strings or non-numeric values

### Edge Cases
- Source sensor does not exist: Show error in configuration
- Source sensor unavailable: Sensors show "unavailable"
- Initial value: Use current source sensor value
- Period change: Recalculate next reset
- HA restart: Reinitialize with current value, reschedule reset

## Technical Requirements

### Dependencies
- **Required Packages**: None (HA core only)
- **Python Version**: 3.11, 3.12
- **Platform Requirements**: Any HA supported platform

### Configuration
- **Required Parameters**: Source sensor, period, types
- **Optional Parameters**: None
- **Validation**:
  - Sensor exists and is numeric
  - Period is valid
  - At least one type selected
- **Security**: None (no credentials stored)

### Entities and Platforms
- **Sensors**:
  - Type: Numeric sensor
  - Device Class: measurement
  - Unit of Measurement: Inherited from source sensor
  - State Class: measurement
  - Unique ID: {entry_id}_max or {entry_id}_min
- **Binary Sensors**: None
- **Switches/Controls**: None
- **Weather**: None
- **Events**: None
- **Device Triggers**: None

### Architecture
- **Coordinator Pattern**: One coordinator per config entry
- **Event Listening**: async_track_state_change_event for source sensor changes
- **Time Scheduling**: async_track_time_change for periodic resets
- **State Management**: Max/min values stored in memory

## Quality Requirements

### Testing
- **Coverage Target**: >95%
- **Unit Tests**:
  - Coordinator initialization
  - Source sensor state changes
  - Resets for each period (daily, weekly, monthly, yearly)
  - Non-numeric values
  - Unavailable sensor
  - Next reset calculations
- **Component Tests**:
  - Full configuration via UI
  - Entity creation
  - HA integration
- **Edge Cases**:
  - Source sensor deleted during runtime
  - Time zone changes
  - Leap years (for yearly period)
  - Months with 28/29/30/31 days (for monthly period)
- **Integration Tests**: Tests with real HA (optional)

### Performance
- **Memory Usage**: Minimal (< 1MB per entry)
- **CPU Usage**: Low (only processes source sensor events)
- **Network Usage**: None
- **Scalability**: Support for multiple entries (each with 1-2 sensors)

### Compatibility
- **HA Versions**: 2024.1.0+
- **Python Versions**: 3.11, 3.12
- **Platforms**: Linux, Docker, HassOS, etc.
- **HACS**: Compatible with validation

## Security Requirements

- **Data Privacy**: Does not store sensitive user data
- **Network Security**: No external connections
- **Error Messages**: Does not expose system paths or internal data
- **Input Validation**: Validates all user inputs
- **State Exposure**: Does not expose internal states in logs

## Deployment Requirements

### HACS Integration
- **Category**: integration
- **Content Root**: false
- **Supported Countries**: All
- **README Rendering**: true
- **HACS Action**: Automatic validation in CI/CD

### Release Process
- **Versioning**: Semantic versioning (MAJOR.MINOR.PATCH)
- **Changelog**: Keep a Changelog format
- **Git Tags**: v0.1.0, etc.
- **Breaking Changes**: Notified in CHANGELOG
- **Pre-releases**: For beta versions

### CI/CD
- **GitHub Actions**:
  - Unit tests (pytest)
  - Component tests (pytest)
  - HACS validation
  - Hassfest validation
  - Coverage reporting
- **Triggers**: Push/PR to main, manual dispatch
- **Python Versions**: Test with 3.11 and 3.12
- **HA Versions**: Test with stable and beta (optional)

## Maintenance Requirements

### Monitoring
- **Health Checks**: Verify sensors update when source changes
- **Error Reporting**: Logging of errors (WARNING for unavailable sensors, ERROR for exceptions)
- **Performance Monitoring**: None required (minimal resource usage)
- **User Feedback**: GitHub Issues for bugs

### Updates
- **API Changes**: Not applicable (no external APIs)
- **HA Compatibility**: Test with new HA versions (beta releases)
- **Dependency Updates**: Minimal (HA core only)
- **Security Updates**: Monitor HA vulnerabilities

### Internationalization
- **Supported Languages**: English (config and code)
- **Translation Files**: strings.json
- **Translation Coverage**: All UI strings
- **RTL Support**: Not required

### Documentation
- **README.md**: Installation, configuration, examples, troubleshooting
- **CONTRIBUTING.md**: Contributor guidelines
- **CHANGELOG.md**: Version history
- **API Docs**: Not applicable
- **User Guide**: Included in README

### Support
- **Community**: GitHub Issues for bugs and features
- **Response Time**: 24-48h for critical issues
- **Bug Fixes**: High priority
- **Feature Requests**: Evaluate based on complexity

---

## Comprehensive List of All Documented Requirements

### Functional Requirements
1. **Sensor Creation**: The integration must be able to create max and min sensors based on a user-selected numeric sensor.
2. **Supported Periods**:
   - Daily: From 00:00 to 23:59 of the same day, reset at 00:00 of the next day.
   - Weekly: From Monday 00:00 to Sunday 23:59, reset at Monday 00:00 of the next week.
   - Monthly: From day 1 00:00 to last day of month 23:59, reset at day 1 00:00 of the next month.
   - Yearly: From January 1 00:00 to December 31 23:59, reset at January 1 00:00 of the next year.
3. **Sensor Types**: Ability to create individual sensors (max only or min only) or pairs (max and min).
4. **Behavior During Period**: Sensors maintain the accumulated max/min value during the period.
5. **Reset at Period End**: At the end of the period, sensors reset to the current source sensor value.
6. **Real-time Updates**: When the source sensor changes, max/min sensors update if necessary.
7. **Sensor Names**: "Max [Source Sensor Name] [Period]" and "Min [Source Sensor Name] [Period]".
8. **Error Handling**: If source sensor does not exist or has no value, sensors show "unavailable".

### Technical Requirements
9. **Platform**: Home Assistant 2024.1.0+.
10. **Python**: Versions 3.11 and 3.12.
11. **Dependencies**: None (HA core only).
12. **Configuration**: Via HA UI with selectors for sensor, period, and types.
13. **Validation**: Source sensor must exist and be numeric.
14. **Architecture**: Uses coordinator pattern with event listening and time scheduling.
15. **Entities**: Sensors with device_class "measurement", inherited unit, state_class "measurement".

### Quality Requirements
16. **Tests**: Coverage >95%, including unit tests, component tests, and edge cases.
17. **Performance**: Minimal memory and CPU usage.
18. **Compatibility**: With all HA platforms and HACS.
19. **Security**: Does not expose sensitive data, validates inputs.

### Deployment Requirements
20. **HACS**: Compatible, category "integration", automatic validation.
21. **CI/CD**: GitHub Actions for tests, HACS and Hassfest validations.
22. **Versioning**: Semantic versioning.
23. **Documentation**: README, CONTRIBUTING, CHANGELOG, translations.

### Maintenance Requirements
24. **Monitoring**: Health checks to verify updates.
25. **Errors**: Appropriate logging (WARNING/ERROR).
26. **Updates**: Compatibility with new HA versions.
27. **Support**: GitHub Issues, quick response for critical bugs.
28. **Internationalization**: Support for English.

---

**Last Updated**: 23 de desembre del 2025
**Maintained by**: [Project maintainers]
**Related Documents**:
- `README.md`: User documentation
- `docs/HA_HACS_Integration_Creation_Guide.md`: Setup guide
- `CONTRIBUTING.md`: Contribution guidelines
- `CHANGELOG.md`: Version history