# Max Min

[![HACS](https://img.shields.io/badge/HACS-Custom-orange.svg)](https://github.com/hacs/integration)
[![Version](https://img.shields.io/github/v/release/PacmanForever/max_min)](https://github.com/PacmanForever/max_min/releases)
[![License: GPL v3](https://img.shields.io/badge/License-GPLv3-blue.svg)](https://www.gnu.org/licenses/gpl-3.0)
[![Unit Tests](https://github.com/PacmanForever/max_min/actions/workflows/tests_unit.yml/badge.svg)](https://github.com/PacmanForever/max_min/actions/workflows/tests_unit.yml)
[![Component Tests](https://github.com/PacmanForever/max_min/actions/workflows/tests_component.yml/badge.svg)](https://github.com/PacmanForever/max_min/actions/workflows/tests_component.yml)
[![Validate HACS](https://github.com/PacmanForever/max_min/actions/workflows/validate_hacs.yml/badge.svg)](https://github.com/PacmanForever/max_min/actions/workflows/validate_hacs.yml)
[![Validate Hassfest](https://github.com/PacmanForever/max_min/actions/workflows/validate_hassfest.yml/badge.svg)](https://github.com/PacmanForever/max_min/actions/workflows/validate_hassfest.yml)
[![Home Assistant](https://img.shields.io/badge/home%20assistant-2024.4.0+-blue)](https://www.home-assistant.io)

> **Important**  
> Beta: This integration is in beta phase. Correct functioning is not guaranteed and may contain errors; use it at your own risk.

A custom Home Assistant integration that creates max and min sensors based on a selected numeric sensor, with support for different time periods.

## Features

- **Max/Min/Delta Sensors**: Creates sensors that maintain the maximum, minimum or delta (change) value of a source sensor during a specified period
- **Configurable Periods**: Daily, weekly, monthly, yearly or all time (never resets)
- **Flexibility**: Create individual sensors (only max, only min, or delta) or any combination
- **Automatic Reset**: At the end of each period, sensors start a new cycle from a fresh seed derived from the current source value, preserving continuity for Max, Min and Delta tracking
- **Real-time Updates**: Sensors update immediately when the source sensor value changes

## Installation

### HACS (recommended)

1. Open HACS in your Home Assistant instance.
2. Go to "Integrations" > "Custom repositories".
3. Add `https://github.com/PacmanForever/max_min` as a custom repository with category "Integration".
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
5. Select sensor types: Max, Min, Delta, or any combination.
6. (Optional) Select a device to link the new sensors to.
7. (Optional) Set an Offset/Margin in seconds (default 0, for cumulative sources).
8. (Optional) Set initial values for Max, Min and/or Delta sensors.

**Note**: When you link sensors to a device, Home Assistant will show a screen at the end of the setup asking you to assign an area. This is standard Home Assistant behavior; if the device already has an area, it will be pre-selected.

## Offset / Margin

You can configure an **offset** (in seconds) to handle synchronization delays or sensor restarts near the end of a period.

This offset/dead-zone behavior is applied to **cumulative sources** (`state_class: total` / `total_increasing`).
For standard measurement sensors, resets happen at the exact period boundary.

- **How it works (cumulative only)**: If you set an offset of e.g. 10 seconds, the period reset for cumulative sources will be delayed by 10 seconds (e.g., at 00:00:10).
- **Dead Zone (cumulative only)**: Updates received during the window `[Reset Time - Offset]` to `[Reset Time + Offset]` are handled conservatively. The integration avoids anchoring a new start value too early, while still protecting max/min/end tracking around the boundary.
- **Why use it?**: This prevents data from the previous period (arriving late) from counting towards the new period, and prevents values from near-instantaneous restarts just before midnight from overwriting the day's true min/max.

## Reliability

To ensure data consistency even in edge cases, Max Min implements several fail-safe mechanisms:

- **Watchdog**: A background monitoring system runs every 10 minutes to verify that resets occurred correctly. If Home Assistant was down or restarting exactly at 00:00 (or the reset time), the watchdog detects the missed reset and enforces it immediately.
- **Chain Break Protection**: The scheduling logic is designed to be "unbreakable". Even if an error occurs (e.g., source sensor is unavailable/unknown exactly at the reset moment), the scheduler guarantees that the *next* reset is programmed, ensuring the sensor never gets stuck.
- **Timezone Precision**: Resets use Home Assistant's local timezone logic (`start_of_local_day`) to handle Daylight Saving Time (DST) transitions flawlessly.

## Use Case Examples

- **Max Daily Temperature**: Shows the maximum temperature value from 00:00 to 23:59 of the current day.
- **Min Weekly Humidity**: Shows the minimum humidity value from Monday 00:00 to Sunday 23:59.
- **Max Monthly Pressure**: Shows the maximum pressure value from day 1 00:00 to the last day of the month 23:59.
- **Delta Daily Rain**: Shows the accumulated rain (end − start) during the current day.
- **Min All-time Voltage**: Shows the absolute minimum voltage ever recorded (never resets).

## Initial Values

You can set initial values for Max, Min and Delta sensors when configuring the integration. This is useful for migrating from other integrations or when you want to start with known baseline values.

- **Initial Max**: Sets the initial max value for a new period when there is no valid restored state yet.
- **Initial Min**: Sets the initial min value for a new period when there is no valid restored state yet.
- **Initial Delta**: Sets the initial delta seed for a new period when there is no valid restored state yet.

Initial values are a one-time seed. They are applied on creation, or after a deliberate per-period reset in options, but they are not re-enforced on every restart or reload. If a valid state from the current period is restored, that restored state wins.

If no initial values are set, the sensors will start with the first value received from the source sensor. Leave the fields empty to disable seeding.

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

- **State restoration**: Max, Min and Delta sensors use Home Assistant's `RestoreEntity` data to recover the last known value and period metadata on startup.
- **Stale data protection**: If the restored data belongs to a previous period (based on `last_reset`), it is discarded and the sensor starts fresh with the current source value.
- **Reset is reprogrammed**: The reset timer is recalculated based on the current time.
- **Inline reset safety net**: If a sensor update arrives after a period boundary but before the scheduled reset fires, the integration detects the stale `last_reset` and resets inline.
- **Startup continuity**: If the source sensor is temporarily unavailable during restart, previously restored values remain in place and live tracking resumes when the source recovers.
- **Delta sensors**: Delta boundaries are restored when available. If an older state is missing `start_value`/`end_value`, the integration reconstructs them from the restored delta and the live source value to preserve continuity.

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