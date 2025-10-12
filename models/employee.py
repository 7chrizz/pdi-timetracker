# Code für Employees into DB
from datetime import date
from enum import Enum
from typing import TYPE_CHECKING, List, Optional

from pydantic import EmailStr, field_validator
from sqlmodel import Field, Relationship, SQLModel

if TYPE_CHECKING:
    from .time_entry import TimeEntry


class Gender(str, Enum):
    MALE = "male"
    FEMALE = "female"
    DIVERSE = "diverse"
    UNKNOWN = "unknown"


class Employee(SQLModel, table=True):
    __tablename__ = "employee"

    id: Optional[int] = Field(default=None, primary_key=True)
    first_name: str = Field(min_length=1, max_length=100, index=True)
    last_name: str = Field(min_length=1, max_length=100, index=True)
    email: EmailStr = Field(sa_column_kwargs={"unique": True, "index": True})
    birth_date: date
    hire_date: date
    gender: Gender = Field(default=Gender.UNKNOWN)

    time_entries: List["TimeEntry"] = Relationship(back_populates="employee")

    @property
    def full_name(self) -> str:
        return f"{self.first_name} {self.last_name}"

    @property
    def age(self) -> int:
        today = date.today()
        years = today.year - self.birth_date.year
        if (today.month, today.day) < (self.birth_date.month, self.birth_date.day):
            years -= 1
        return years

    @field_validator("hire_date")
    @classmethod
    def validate_hire_after_birth(cls, v: date, info):
        birth = info.data.get("birth_date")
        if birth and v < birth:
            raise ValueError("hire date cant be earlier than birth date")
        return v
