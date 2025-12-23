# Testing Dependencies

This document describes the testing dependencies for the Max Min Home Assistant integration.

## Overview

Testing dependencies are packages required for development, unit testing, component testing, and CI/CD pipelines. These are separate from runtime dependencies to keep the production integration lightweight.

## File: `requirements-test.txt`

This file contains all packages needed for testing the integration.

### Current Dependencies

| Package | Version | Purpose |
|---------|---------|---------|
| `pytest` | `>=7.0.0` | Core testing framework for Python |
| `pytest-asyncio` | `>=0.21.0` | Support for testing async functions |
| `pytest-cov` | `>=4.0.0` | Code coverage reporting and measurement |
| `pytest-homeassistant-custom-component` | `>=0.13.0` | Specialized testing utilities for HA custom components |
| `freezegun` | `>=1.2.0` | Time freezing/mocking for testing time-dependent code |

### Installation

To install testing dependencies:
```bash
pip install -r requirements-test.txt
```

For development (including runtime dependencies):
```bash
pip install -r requirements.txt
pip install -r requirements-test.txt
```

## Testing Tools Explanation

### pytest
- **Purpose**: Framework for writing and running tests
- **Usage**: `pytest tests/unit/` for unit tests, `pytest tests/component/` for component tests
- **Configuration**: See `pytest.ini` for test discovery and settings

### pytest-asyncio
- **Purpose**: Enables testing of async/await functions
- **Usage**: Allows `async def test_*` functions in test files
- **Integration**: Required for testing HA async code

### pytest-cov
- **Purpose**: Measures code coverage during test runs
- **Usage**: `pytest --cov=custom_components.max_min` to generate coverage reports
- **Target**: >95% coverage required for HA Silver level

### pytest-homeassistant-custom-component
- **Purpose**: HA-specific testing utilities and fixtures
- **Usage**: Provides `hass` fixture and HA testing helpers
- **Integration**: Essential for component tests that interact with HA

### freezegun
- **Purpose**: Freezes time for testing time-dependent logic
- **Usage**: `@freeze_time("2023-01-01 12:00:00")` to mock current time
- **Application**: Testing period resets and time calculations

## Test Structure

```
tests/
├── __init__.py              # Test package
├── conftest.py              # Shared fixtures and configuration
├── unit/                    # Unit tests (isolated functions)
│   ├── test_init.py
│   ├── test_coordinator.py
│   └── test_sensor.py
└── component/               # Component tests (HA integration)
    └── test_sensor.py
```

## Running Tests

### Local Development
```bash
# Run all tests
pytest

# Run unit tests only
pytest tests/unit/

# Run component tests only
pytest tests/component/

# Run with coverage
pytest --cov=custom_components.max_min --cov-report=html
```

### CI/CD
Tests are automatically run in GitHub Actions workflows:
- `tests_unit.yml`: Unit tests with coverage
- `tests_component.yml`: Component tests with coverage

## Adding New Testing Dependencies

1. **Evaluate Need**: Ensure the package is necessary for testing
2. **Add to File**: Update `requirements-test.txt` with version constraints
3. **Update Documentation**: Add entry to this document
4. **Test CI/CD**: Ensure workflows still pass
5. **Update CHANGELOG**: Document the addition

## Best Practices

- Keep testing dependencies focused on testing needs
- Use version constraints to ensure reproducible builds
- Prefer well-maintained, actively developed packages
- Test dependency changes locally before committing
- Monitor for security vulnerabilities in dependencies

## Coverage Requirements

- **Target**: >95% code coverage
- **Measurement**: Lines, branches, and functions
- **Reporting**: HTML reports for detailed analysis
- **CI Enforcement**: Coverage checks in GitHub Actions

## Related Files
- `requirements-test.txt`: Testing dependencies list
- `pytest.ini`: Pytest configuration
- `tests/conftest.py`: Test fixtures
- `.github/workflows/tests_*.yml`: CI/CD test workflows
- `DEPENDENCIES.md`: General dependencies documentation