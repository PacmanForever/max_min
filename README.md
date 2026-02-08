# Max Min

[![HACS](https://img.shields.io/badge/HACS-Custom-orange.svg)](https://github.com/hacs/integration)
[![Version](https://img.shields.io/github/v/release/PacmanForever/max_min)](https://github.com/PacmanForever/max_min/releases)
[![License: GPL v3](https://img.shields.io/badge/License-GPLv3-blue.svg)](https://www.gnu.org/licenses/gpl-3.0)
[![Unit Tests](https://github.com/PacmanForever/max_min/actions/workflows/tests_unit.yml/badge.svg)](https://github.com/PacmanForever/max_min/actions/workflows/tests_unit.yml)
[![Component Tests](https://github.com/PacmanForever/max_min/actions/workflows/tests_component.yml/badge.svg)](https://github.com/PacmanForever/max_min/actions/workflows/tests_component.yml)
[![Validate HACS](https://github.com/PacmanForever/max_min/actions/workflows/validate_hacs.yml/badge.svg)](https://github.com/PacmanForever/max_min/actions/workflows/validate_hacs.yml)
[![Validate Hassfest](https://github.com/PacmanForever/max_min/actions/workflows/validate_hassfest.yml/badge.svg)](https://github.com/PacmanForever/max_min/actions/workflows/validate_hassfest.yml)
[![Home Assistant](https://img.shields.io/badge/home%20assistant-2024.1.0+-blue)](https://www.home-assistant.io)

> **Important**  
> Beta: This integration is in beta phase. Correct functioning is not guaranteed and may contain errors; use it at your own risk.

A custom Home Assistant integration that creates max and min sensors based on a selected numeric sensor, with support for different time periods.

## Features

- **Max/Min/Delta Sensors**: Creates sensors that maintain the maximum, minimum or delta (change) value of a source sensor during a specified period
- **Configurable Periods**: Daily, weekly, monthly, yearly or all time (never resets)
- **Flexibility**: Create individual sensors (only max, only min, or delta) or any combination
- **Automatic Reset**: At the end of each period, sensors reset to the current value of the source sensor (Max/Min) or zero (Delta)
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
4. Choose the period: Daily, Weekly, Monthly, Yearly or All time.
5. Select sensor types: Max, Min, or both.
6. (Optional) Select a device to link the new sensors to.
7. (Optional) Set an Offset/Margin in seconds (default 0).
8. (Optional) Set initial values for max and/or min to start with existing values.

**Note**: When you link sensors to a device, Home Assistant will show a screen at the end of the setup asking you to assign an area. This is standard Home Assistant behavior; if the device already has an area, it will be pre-selected.

## Offset / Margin

You can configure an **offset** (in seconds) to handle synchronization delays or sensor restarts near the end of a period.

- **How it works**: If you set an offset of e.g. 10 seconds, the period reset will be delayed by 10 seconds (e.g., at 00:00:10).
- **Dead Zone**: Updates received during the window `[Reset Time - Offset]` to `[Reset Time + Offset]` will be ignored.
- **Why use it?**: This prevents data from the previous period (arriving late) from counting towards the new period, and prevents values from near-instantaneous restarts just before midnight from overwriting the day's true min/max.

## Use Case Examples

- **Max Daily Temperature**: Shows the maximum temperature value from 00:00 to 23:59 of the current day.
- **Min Weekly Humidity**: Shows the minimum humidity value from Monday 00:00 to Sunday 23:59.
- **Max Monthly Pressure**: Shows the maximum pressure value from day 1 00:00 to the last day of the month 23:59.
- **Delta Daily Rain**: Shows the accumulated rain (end − start) during the current day.
- **Min All-time Voltage**: Shows the absolute minimum voltage ever recorded (never resets).

## Initial Values

You can set initial values for the max and min sensors when configuring the integration. This is useful for migrating from other integrations or when you want to start with known baseline values.

- **Initial Max**: Set a starting maximum value. The sensor will only update if the source sensor exceeds this value. This value is enforced as a floor — restored values below it will be raised back to the configured initial.
- **Initial Min**: Set a starting minimum value. The sensor will only update if the source sensor goes below this value. This value is enforced as a ceiling — restored values above it will be lowered back to the configured initial.

If no initial values are set, the sensors will start with the first value received from the source sensor.

## How it works

1. **Sensor Selection**: The user chooses an existing numeric sensor in Home Assistant.
2. **Period Configuration**: The time cycle is defined (daily, weekly, monthly, yearly, or all time).
3. **Type Selection**: Max, Min, Delta, or any combination.
4. **Sensor Creation**: Sensors are created with descriptive names (e.g., "Temperature Daily Max").
5. **Value Accumulation**: During the period, Max/Min sensors maintain the observed extremes; Delta tracks end − start.
6. **Automatic Reset**: At the end of the period, sensors reset to the current value of the source sensor and a new cycle begins. "All time" sensors never reset.

### Detailed Periods

- **Daily**: From 00:00 to 23:59 of the same day. Reset at 00:00 of the next day.
- **Weekly**: From Monday 00:00 to Sunday 23:59. Reset at Monday 00:00 of the next week.
- **Monthly**: From day 1 00:00 to the last day of the month 23:59. Reset at day 1 00:00 of the next month.
- **Yearly**: From January 1 00:00 to December 31 23:59. Reset at January 1 00:00 of the next year.
- **All time**: Never resets. Tracks the absolute max/min/delta since the sensor was created.

### Sensor Types

- **Max**: Tracks the highest value observed during the period.
- **Min**: Tracks the lowest value observed during the period.
- **Delta**: Tracks the change (end − start) during the period. Useful for cumulative sensors like rain gauges or energy meters.

## Automations

You can use these sensors in automations, for example:

- Notifications when the daily max exceeds a threshold
- Historical records of weekly mins
- Alerts for extreme monthly values

## Behavior with Home Assistant restarts

When Home Assistant restarts, the Max Min integration restores its state:

- **State restoration**: Max and Min sensors use Home Assistant's `RestoreEntity` to recover the last known value and `last_reset` timestamp on startup.
- **Stale data protection**: If the restored data belongs to a previous period (based on `last_reset`), it is discarded and the sensor starts fresh with the current source value.
- **Reset is reprogrammed**: The reset timer is recalculated based on the current time.
- **Inline reset safety net**: If a sensor update arrives after a period boundary but before the scheduled reset fires, the integration detects the stale `last_reset` and resets inline.
- **Sensors unavailable**: If the source sensor is not available during restart, sensors will show "Unavailable".
- **Delta sensors**: Delta values (start/end) are not restored; they reinitialize from the current source value after restart.

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