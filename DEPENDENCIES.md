# Runtime Dependencies

This document describes the runtime dependencies for the Max Min Home Assistant integration.

## Overview

The Max Min integration is designed to be lightweight and only uses Home Assistant core libraries. This ensures compatibility, security, and minimal resource usage.

## No External Dependencies

This integration **does not require any external Python packages** beyond what is included in Home Assistant core. All functionality is implemented using:

- Home Assistant core APIs
- Standard Python library modules
- Built-in async utilities

## Why No Dependencies?

- **Security**: Fewer dependencies mean fewer potential security vulnerabilities
- **Compatibility**: No version conflicts with other integrations
- **Maintenance**: No need to track and update external packages
- **Performance**: Faster installation and loading
- **Reliability**: Less chance of dependency-related failures

## Home Assistant Core Usage

The integration uses the following HA core components:

- `homeassistant.core`: Core HA functionality
- `homeassistant.config_entries`: Configuration entry management
- `homeassistant.helpers`: Utility functions (coordinator, entity, event tracking)
- `homeassistant.components.sensor`: Sensor entity base classes
- `homeassistant.util`: Time and utility functions

## Installation

Since there are no external dependencies, the integration installs instantly and has no additional requirements beyond Home Assistant itself.

## File: `requirements.txt`

The `requirements.txt` file is intentionally empty, as documented in the file header.

## Related Files

- `TESTING-DEPENDENCIES.md`: Testing dependencies documentation
- `requirements-test.txt`: Testing dependencies list
- `REQUIREMENTS.md`: Complete project requirements