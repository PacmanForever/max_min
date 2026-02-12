import pytest
from datetime import datetime, timedelta, timezone
from homeassistant.util import dt as dt_util
try:
    from zoneinfo import ZoneInfo
except ImportError:
    from backports.zoneinfo import ZoneInfo

from custom_components.max_min.coordinator import MaxMinDataUpdateCoordinator
from custom_components.max_min.const import PERIOD_DAILY, PERIOD_MONTHLY, PERIOD_YEARLY

# Dummy class to access static methods if they were instance methods, 
# but they are static so we can use the class directly.
Coordinator = MaxMinDataUpdateCoordinator

def test_daily_reset_utc():
    """Test daily reset calculation in UTC."""
    dt_util.set_default_time_zone(timezone.utc)
    now = datetime(2023, 10, 15, 12, 0, 0, tzinfo=timezone.utc)
    
    next_reset = Coordinator._compute_next_reset(now, PERIOD_DAILY)
    
    assert next_reset == datetime(2023, 10, 16, 0, 0, 0, tzinfo=timezone.utc)

def test_daily_reset_cet():
    """Test daily reset calculation in CET (UTC+1)."""
    cet = ZoneInfo("Europe/Madrid")
    try:
        dt_util.set_default_time_zone(cet)
        
        # 12:00 UTC = 13:00 CET (no daylight saving in Oct?? Wait, Oct 15 IS DST? No, change is late Oct)
        # 15 Oct is CEST (UTC+2)
        # Let's use winter: Jan 15 (UTC+1)
        
        now = datetime(2023, 1, 15, 13, 0, 0, tzinfo=cet) # 13:00 CET
        
        next_reset = Coordinator._compute_next_reset(now, PERIOD_DAILY)
        
        # Next reset should be Jan 16 00:00 CET
        assert next_reset.tzinfo == cet
        assert next_reset.year == 2023
        assert next_reset.month == 1
        assert next_reset.day == 16
        assert next_reset.hour == 0
        assert next_reset.minute == 0
        
        # In UTC this would be Jan 15 23:00
        assert next_reset.astimezone(timezone.utc) == datetime(2023, 1, 15, 23, 0, 0, tzinfo=timezone.utc)
    finally:
        dt_util.set_default_time_zone(timezone.utc)

def test_monthly_reset_uses_local_midnight():
    """Test monthly reset uses local midnight, not just replace(hour=0)."""
    cet = ZoneInfo("Europe/Madrid")
    try:
        dt_util.set_default_time_zone(cet)
        
        now = datetime(2023, 1, 15, 12, 0, 0, tzinfo=cet)
        
        next_reset = Coordinator._compute_next_reset(now, PERIOD_MONTHLY)
        
        # Should be Feb 1st, 00:00 CET
        assert next_reset.tzinfo == cet
        assert next_reset.month == 2
        assert next_reset.day == 1
        assert next_reset.hour == 0
    finally:
        dt_util.set_default_time_zone(timezone.utc)

def test_yearly_reset_uses_local_midnight():
    """Test yearly reset uses local midnight."""
    cet = ZoneInfo("Europe/Madrid")
    try:
        dt_util.set_default_time_zone(cet)
        
        now = datetime(2023, 6, 15, 12, 0, 0, tzinfo=cet)
        
        next_reset = Coordinator._compute_next_reset(now, PERIOD_YEARLY)
        
        # Should be Jan 1st 2024, 00:00 CET
        assert next_reset.tzinfo == cet
        assert next_reset.year == 2024
        assert next_reset.month == 1
        assert next_reset.day == 1
        assert next_reset.hour == 0
    finally:
        dt_util.set_default_time_zone(timezone.utc)
