# KEIN: from __future__ import annotations

from datetime import date, datetime, time
from typing import Optional, TYPE_CHECKING

from pydantic import field_validator
from sqlalchemy import Column, Date as SA_Date, Time as SA_Time
from sqlmodel import SQLModel, Field, Relationship

if TYPE_CHECKING:
    from .employee import Employee

class TimeEntry(SQLModel, table=True):
    __tablename__ = "time_entry"

    id: int | None = Field(default=None, primary_key=True)
    Start: time = Field(sa_column=Column("Start", SA_Time, nullable=False))
    Ende:  time = Field(sa_column=Column("Ende",  SA_Time, nullable=False))
    Pause: time = Field(sa_column=Column("Pause", SA_Time, nullable=False))
    Date:  date = Field(sa_column=Column("Date",  SA_Date, nullable=False))

    employee_id: int = Field(foreign_key="employee.id", index=True)
    employee: "Employee" = Relationship(back_populates="time_entries")

    @field_validator("Start", "Ende", "Pause", mode="before")
    @classmethod
    def parse_time(cls, v):
        if isinstance(v, time):
            return v
        if isinstance(v, str):
            s = v.strip().replace(" ", "")
            if ":" in s:
                parts = s.split(":")
                if len(parts) != 2:
                    raise TypeError("Invalid timeformat.")
                h, m = parts
                if len(h) == 1:
                    h = f"0{h}"
                if len(m) == 1:
                    m = f"0{m}"
                return datetime.strptime(f"{h}:{m}", "%H:%M").time()
            if s.isdigit():
                if len(s) != 4:
                    raise TypeError("Time must be datetime.time, 'HH:MM' or 'HHMM'.")
                h = int(s[:2]); m = int(s[2:])
                if not (0 <= h <= 23 and 0 <= m <= 59):
                    raise TypeError("Invalid time.")
                return time(hour=h, minute=m)
        raise TypeError("Time muss be time, 'HH:MM' or 'HHMM'.")

    @field_validator("Date", mode="before")
    @classmethod
    def parse_ddmmyyyy(cls, v):
        if isinstance(v, date):
            return v
        if isinstance(v, str):
            return datetime.strptime(v, "%d.%m.%Y").date()
        raise TypeError("Date must be a date object or 'DD.MM.YYYY' string.")

    @classmethod
    def from_input(cls, **data) -> "TimeEntry":
        return cls.model_validate(data)