# Max Min

[![HACS](https://img.shields.io/badge/HACS-Custom-orange.svg)](https://github.com/hacs/integration)
[![Version](https://img.shields.io/github/v/release/PacmanForever/max_min)](https://github.com/PacmanForever/max_min/releases)
[![License](https://img.shields.io/github/license/PacmanForever/max_min)](https://github.com/PacmanForever/max_min/blob/master/LICENSE)
[![Coverage](https://img.shields.io/codecov/c/github/PacmanForever/max_min)](https://codecov.io/gh/PacmanForever/max_min)
[![Unit Tests](https://github.com/PacmanForever/max-min/actions/workflows/tests_unit.yml/badge.svg)](https://github.com/PacmanForever/max-min/actions/workflows/tests_unit.yml)
[![Component Tests](https://github.com/PacmanForever/max-min/actions/workflows/tests_component.yml/badge.svg)](https://github.com/PacmanForever/max-min/actions/workflows/tests_component.yml)
[![Validate HACS](https://github.com/PacmanForever/max-min/actions/workflows/validate_hacs.yml/badge.svg)](https://github.com/PacmanForever/max-min/actions/workflows/validate_hacs.yml)
[![Validate Hassfest](https://github.com/PacmanForever/max-min/actions/workflows/validate_hassfest.yml/badge.svg)](https://github.com/PacmanForever/max-min/actions/workflows/validate_hassfest.yml)
[![Home Assistant](https://img.shields.io/badge/home%20assistant-2024.1.0+-blue)](https://www.home-assistant.io)

> **Important**  
> Beta: This integration is in beta phase. Correct functioning is not guaranteed and may contain errors; use it at your own risk.

A custom Home Assistant integration that creates max and min sensors based on a selected numeric sensor, with support for different time periods.

## Features

- **Max/Min Sensors**: Creates sensors that maintain the maximum or minimum value of a source sensor during a specified period
- **Configurable Periods**: Daily, weekly, monthly or yearly
- **Flexibility**: Create individual sensors (only max or only min) or in pairs
- **Automatic Reset**: At the end of each period, sensors reset to the current value of the source sensor
- **Real-time Updates**: Sensors update immediately when the source sensor value changes

## Installation

### HACS (recommended)

1. Open HACS in your Home Assistant instance.
2. Go to "Integrations" > "Custom repositories".
3. Add `https://github.com/PacmanForever/max-min` as a custom repository with category "Integration".
4. Search for "Max Min" and install it.
5. Restart Home Assistant.
6. Add the integration through the UI.

### Manual

1. Download the `max_min` folder from the latest release.
2. Copy it to `custom_components/max_min` in the Home Assistant configuration directory.
3. Restart Home Assistant.
4. Add the integration through the UI.

## Configuration

After installation, add the integration via the Home Assistant UI:

1. Go to Settings > Devices and services > Add integration.
2. Search for "Max Min".
3. Select the source sensor (an existing numeric sensor).
4. Choose the period: Daily, Weekly, Monthly or Yearly.
5. Select sensor types: Max, Min, or both.

### Examples of created sensors

- **Max Daily Temperature**: Shows the maximum temperature value from 00:00 to 23:59 of the current day
- **Min Weekly Humidity**: Shows the minimum humidity value from Monday 00:00 to Sunday 23:59
- **Max Monthly Pressure**: Shows the maximum pressure value from day 1 00:00 to the last day of the month 23:59
- **Min Annual Voltage**: Shows the minimum voltage value from January 1 00:00 to December 31 23:59

## How it works

1. **Sensor Selection**: The user chooses an existing numeric sensor in Home Assistant.
2. **Period Configuration**: The time cycle is defined (daily, weekly, etc.).
3. **Sensor Creation**: Max and/or min sensors are created with descriptive names.
4. **Value Accumulation**: During the period, sensors maintain the observed max/min.
5. **Automatic Reset**: At the end of the period, sensors reset to the current value of the source sensor and a new cycle begins.

### Detailed Periods

- **Daily**: From 00:00 to 23:59 of the same day. Reset at 00:00 of the next day.
- **Weekly**: From Monday 00:00 to Sunday 23:59. Reset at Monday 00:00 of the next week.
- **Monthly**: From day 1 00:00 to the last day of the month 23:59. Reset at day 1 00:00 of the next month.
- **Yearly**: From January 1 00:00 to December 31 23:59. Reset at January 1 00:00 of the next year.

## Automations

You can use these sensors in automations, for example:

- Notifications when the daily max exceeds a threshold
- Historical records of weekly mins
- Alerts for extreme monthly values

## Behavior with Home Assistant restarts

When Home Assistant restarts, the Max Min integration behaves as follows:

- **Accumulated values are lost**: The max and min values accumulated during the current period are completely lost
- **Current value is preserved**: Only the current value of the source sensor at restart time is maintained
- **Reset is reprogrammed**: The reset timer is recalculated based on the current time
- **Sensors unavailable**: If the source sensor is not available during restart, sensors will show "Unavailable"

**Important note**: This integration does not save historical values to disk, by design. If you need data persistence, consider using Home Assistant's native history functionality or external databases.

## Troubleshooting

### The sensor doesn't update
- Verify that the source sensor exists and has valid numeric values
- Check Home Assistant logs for errors

### The sensor shows "Unavailable"
- The source sensor is not available or does not have a valid numeric value
- Wait for the source sensor to reconnect

### Configuration errors
- Make sure you have selected an existing numeric sensor
- Verify that the period is correctly configured

## Contributions

Contributions are welcome! Please see [CONTRIBUTING.md](CONTRIBUTING.md) for details.

## License

This project is licensed under the GPL-3.0 License - see the [LICENSE](LICENSE) file for details.