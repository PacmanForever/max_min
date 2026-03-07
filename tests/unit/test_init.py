"""Test init."""

from unittest.mock import AsyncMock, Mock, patch, call

import pytest

from custom_components.max_min import async_setup, async_setup_entry, async_unload_entry
from custom_components.max_min.const import DOMAIN, CONF_RESET_HISTORY


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
        assert config_entry.runtime_data == mock_coordinator


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

    hass.config_entries.async_unload_platforms = AsyncMock(return_value=True)
    mock_coordinator = Mock()
    mock_coordinator.async_unload = AsyncMock()
    config_entry.runtime_data = mock_coordinator

    result = await async_unload_entry(hass, config_entry)
    assert result is True
    mock_coordinator.async_unload.assert_called_once()


@pytest.mark.asyncio
async def test_async_unload_entry_forward_failure(hass):
    """Test async unload entry with forward failure."""
    config_entry = Mock()
    config_entry.entry_id = "test_entry"

    hass.config_entries.async_unload_platforms = AsyncMock(return_value=False)
    mock_coordinator = Mock()
    config_entry.runtime_data = mock_coordinator

    result = await async_unload_entry(hass, config_entry)
    assert result is False


@pytest.mark.asyncio
async def test_async_reload_entry(hass):
    """Test async reload entry."""
    from custom_components.max_min import async_reload_entry
    
    config_entry = Mock()
    config_entry.entry_id = "test_entry"
    hass.config_entries.async_reload = AsyncMock()

    await async_reload_entry(hass, config_entry)
    hass.config_entries.async_reload.assert_called_once_with("test_entry")


@pytest.mark.asyncio
async def test_reset_history_cleaned_before_listener(hass):
    """Test that CONF_RESET_HISTORY is cleared BEFORE the update listener is registered.

    If the cleanup happens after add_update_listener, async_update_entry
    triggers a spurious reload that causes RestoreEntity to overwrite the
    surgical-reset with stale data (the classic double-reload bug).
    """
    config_entry = Mock()
    config_entry.entry_id = "test_entry"
    config_entry.data = {"sensor_entity": "sensor.test", "types": ["delta"], "periods": ["monthly"]}
    config_entry.options = {CONF_RESET_HISTORY: ["monthly_delta"]}

    mock_coordinator = Mock()
    mock_coordinator.async_config_entry_first_refresh = AsyncMock()

    # Track the order of operations
    call_order = []

    def track_update_entry(entry, **kwargs):
        call_order.append("async_update_entry")

    def track_add_update_listener(listener):
        call_order.append("add_update_listener")
        return Mock()  # unsub callable

    hass.config_entries.async_update_entry = Mock(side_effect=track_update_entry)
    config_entry.add_update_listener = Mock(side_effect=track_add_update_listener)
    config_entry.async_on_unload = Mock()

    with patch("custom_components.max_min.MaxMinDataUpdateCoordinator", return_value=mock_coordinator):
        hass.config_entries.async_forward_entry_setups = AsyncMock()
        hass.data = {}

        result = await async_setup_entry(hass, config_entry)
        assert result is True

    # The critical assertion: async_update_entry MUST come before add_update_listener
    assert "async_update_entry" in call_order, "CONF_RESET_HISTORY was not cleaned up"
    assert "add_update_listener" in call_order, "Update listener was not registered"
    assert call_order.index("async_update_entry") < call_order.index("add_update_listener"), \
        "async_update_entry must be called BEFORE add_update_listener to avoid double-reload"

    # Verify CONF_RESET_HISTORY was actually removed from options
    hass.config_entries.async_update_entry.assert_called_once()
    _, kwargs = hass.config_entries.async_update_entry.call_args
    assert CONF_RESET_HISTORY not in kwargs.get("options", {})