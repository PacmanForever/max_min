"""Test init."""

from unittest.mock import AsyncMock, Mock, patch

import pytest

from custom_components.max_min import async_setup, async_setup_entry, async_unload_entry
from custom_components.max_min.const import DOMAIN


@pytest.fixture
def hass():
    """Mock hass for init tests."""
    hass = Mock()
    hass.data = {"custom_components": {}}
    hass.config_entries.async_forward_entry_setups = AsyncMock()
    hass.config_entries.async_unload_platforms = AsyncMock()
    return hass


@pytest.mark.asyncio
async def test_async_setup(hass):
    """Test async setup."""
    assert await async_setup(hass, {}) is True


@pytest.mark.asyncio
async def test_async_setup_entry_success(hass):
    """Test async setup entry success."""
    config_entry = Mock()
    config_entry.entry_id = "test_entry"
    config_entry.data = {"sensor_entity": "sensor.test", "period": "daily", "types": ["max", "min"]}
    config_entry.options = {}

    # Mock coordinator
    mock_coordinator = Mock()
    mock_coordinator.async_config_entry_first_refresh = AsyncMock()

    with patch("custom_components.max_min.MaxMinDataUpdateCoordinator", return_value=mock_coordinator):
        hass.config_entries.async_forward_entry_setups = AsyncMock()
        hass.data = {}

        result = await async_setup_entry(hass, config_entry)
        assert result is True
        assert DOMAIN in hass.data
        assert config_entry.entry_id in hass.data[DOMAIN]


@pytest.mark.asyncio
async def test_async_setup_entry_forward_failure(hass):
    """Test async setup entry with forward failure."""
    config_entry = Mock()
    config_entry.entry_id = "test_entry"
    config_entry.data = {"sensor_entity": "sensor.test", "period": "daily", "types": ["max", "min"]}
    config_entry.options = {}

    mock_coordinator = Mock()
    mock_coordinator.async_config_entry_first_refresh = AsyncMock()

    with patch("custom_components.max_min.MaxMinDataUpdateCoordinator", return_value=mock_coordinator):
        hass.config_entries.async_forward_entry_setups = AsyncMock(side_effect=Exception("Forward failed"))
        hass.data = {}

        # Should raise Exception
        with pytest.raises(Exception):
            await async_setup_entry(hass, config_entry)


@pytest.mark.asyncio
async def test_async_unload_entry_success(hass):
    """Test async unload entry success."""
    config_entry = Mock()
    config_entry.entry_id = "test_entry"

    hass.config_entries.async_forward_entry_unload = AsyncMock(return_value=True)
    mock_coordinator = Mock()
    mock_coordinator.async_unload = AsyncMock()
    hass.data = {DOMAIN: {"test_entry": mock_coordinator}}

    result = await async_unload_entry(hass, config_entry)
    assert result is True
    assert config_entry.entry_id not in hass.data[DOMAIN]
    mock_coordinator.async_unload.assert_called_once()


@pytest.mark.asyncio
async def test_async_unload_entry_forward_failure(hass):
    """Test async unload entry with forward failure."""
    config_entry = Mock()
    config_entry.entry_id = "test_entry"

    hass.config_entries.async_forward_entry_unload = AsyncMock(return_value=False)
    hass.data = {DOMAIN: {"test_entry": Mock()}}

    result = await async_unload_entry(hass, config_entry)
    assert result is False
    assert config_entry.entry_id in hass.data[DOMAIN]