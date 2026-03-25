"""Time range filtering for session data."""

from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass
from datetime import UTC, date, datetime, time, timedelta

from parsimony.models.session import Session


def _local_now() -> datetime:
    """Return the current local time as a timezone-aware datetime."""
    return datetime.now(tz=UTC).astimezone()


def _start_of_day(d: date) -> datetime:
    """Return midnight at the start of the given date in local timezone."""
    local_tz = _local_now().tzinfo
    return datetime.combine(d, time.min, tzinfo=local_tz)


def _end_of_day(d: date) -> datetime:
    """Return 23:59:59.999999 at the end of the given date in local timezone."""
    local_tz = _local_now().tzinfo
    return datetime.combine(d, time.max, tzinfo=local_tz)


@dataclass(frozen=True)
class TimeRange:
    """A time window for filtering sessions."""

    start: datetime
    end: datetime
    label: str

    @classmethod
    def today(cls) -> TimeRange:
        now = _local_now()
        return cls(
            start=_start_of_day(now.date()),
            end=_end_of_day(now.date()),
            label=now.strftime("%A, %b %d %Y"),
        )

    @classmethod
    def yesterday(cls) -> TimeRange:
        yesterday = _local_now().date() - timedelta(days=1)
        return cls(
            start=_start_of_day(yesterday),
            end=_end_of_day(yesterday),
            label=f"Yesterday, {yesterday.strftime('%b %d %Y')}",
        )

    @classmethod
    def this_week(cls) -> TimeRange:
        now = _local_now()
        monday = now.date() - timedelta(days=now.weekday())
        sunday = monday + timedelta(days=6)
        return cls(
            start=_start_of_day(monday),
            end=_end_of_day(sunday),
            label=f"Week of {monday.strftime('%b %d')}",
        )

    @classmethod
    def last_week(cls) -> TimeRange:
        now = _local_now()
        this_monday = now.date() - timedelta(days=now.weekday())
        last_monday = this_monday - timedelta(days=7)
        last_sunday = last_monday + timedelta(days=6)
        return cls(
            start=_start_of_day(last_monday),
            end=_end_of_day(last_sunday),
            label=f"Week of {last_monday.strftime('%b %d')}",
        )

    @classmethod
    def this_month(cls) -> TimeRange:
        now = _local_now()
        first_day = now.date().replace(day=1)
        if now.month == 12:
            last_day = date(now.year + 1, 1, 1) - timedelta(days=1)
        else:
            last_day = date(now.year, now.month + 1, 1) - timedelta(days=1)
        return cls(
            start=_start_of_day(first_day),
            end=_end_of_day(last_day),
            label=now.strftime("%B %Y"),
        )

    @classmethod
    def month(cls, year: int, month: int) -> TimeRange:
        first_day = date(year, month, 1)
        if month == 12:
            last_day = date(year + 1, 1, 1) - timedelta(days=1)
        else:
            last_day = date(year, month + 1, 1) - timedelta(days=1)
        return cls(
            start=_start_of_day(first_day),
            end=_end_of_day(last_day),
            label=first_day.strftime("%B %Y"),
        )

    @classmethod
    def last_n_days(cls, n: int) -> TimeRange:
        now = _local_now()
        start_date = now.date() - timedelta(days=n - 1)
        return cls(
            start=_start_of_day(start_date),
            end=_end_of_day(now.date()),
            label=f"Last {n} days",
        )

    @classmethod
    def all_time(cls) -> TimeRange:
        return cls(
            start=datetime.min.replace(tzinfo=UTC),
            end=datetime.max.replace(tzinfo=UTC),
            label="All time",
        )


def filter_sessions(
    sessions: Iterable[Session], time_range: TimeRange
) -> list[Session]:
    """Return only sessions whose start_time falls within the time range."""
    result: list[Session] = []
    for session in sessions:
        if session.start_time is None:
            continue
        if time_range.start <= session.start_time <= time_range.end:
            result.append(session)
    return result
