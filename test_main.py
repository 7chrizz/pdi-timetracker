from datetime import date, time

import pytest

from models import TimeEntry
from main import minutes_from_entry


@pytest.mark.parametrize(
    "start,end,pause,expected",
    [
        (time(9, 0), time(17, 0), time(1, 0), 420),
        (time(8, 30), time(16, 30), time(0, 30), 450),
        (time(9, 15), time(17, 15), time(0, 45), 435),
        (time(7, 0), time(15, 0), time(0, 0), 480),
        (time(12, 0), time(20, 0), time(1, 30), 390),
        (time(10, 0), time(9, 0), time(1, 0), 1320),  # 22 hours shift
    ],
)
def test_minutes_from_entry(start, end, pause, expected):
    entry = TimeEntry(Start=start, Ende=end, Pause=pause, Date=date.today())
    assert minutes_from_entry(entry) == expected
