from __future__ import annotations

from datetime import date
from typing import List, Optional, Tuple

from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import selectinload
from sqlmodel import Session, SQLModel, create_engine, select

from models import Employee, TimeEntry

DB_URL = "sqlite:///timetracker.db"

MONTH_EN = [
    "",
    "January",
    "February",
    "March",
    "April",
    "May",
    "June",
    "July",
    "August",
    "September",
    "October",
    "November",
    "December",
]


def minutes_from_entry(e) -> int:
    def to_min(t):
        return t.hour * 60 + t.minute

    start = to_min(e.Start)
    end = to_min(e.Ende)
    pause = to_min(e.Pause)
    if end < start:
        end += 24 * 60
    return max(0, end - start - pause)


def fmt_hhmm(mins: int) -> str:
    return f"{mins // 60:02d}:{mins % 60:02d}"


def get_engine():
    engine = create_engine(
        DB_URL, echo=False, connect_args={"check_same_thread": False}
    )
    return engine


def _parse_ddmmyyyy_loose(s: str) -> date:
    s = s.strip()
    parts = [p for p in s.split(".") if p != ""]
    if len(parts) != 3:
        raise ValueError("Invalid format")
    d, m, y = map(int, parts)
    return date(y, m, d)


def prompt_ddmmyyyy(label: str) -> date | None:
    while True:
        s = input(f"{label} (e.g., 1.1.2025, 0=Cancel): ").strip()
        if not s or s == "0":
            return None
        try:
            return _parse_ddmmyyyy_loose(s)
        except ValueError:
            print("✗ Invalid date. Please use D.M.YYYY or DD.MM.YYYY.")


def prompt_time(label: str) -> str | None:
    while True:
        s = input(f"{label} (HH:MM or HHMM, 0=Cancel): ").strip()
        if not s or s == "0":
            return None
        t = s.replace(" ", "")
        if (":" in t and len(t.split(":")) == 2) or (t.isdigit() and len(t) in (3, 4)):
            return s
        print("✗ Invalid time. Allowed: HH:MM or HHMM.")


def fetch_employees(s: Session) -> List["Employee"]:
    return s.exec(
        select(Employee).order_by(Employee.last_name, Employee.first_name)
    ).all()


def format_employee_row(e: "Employee", idx: int) -> str:
    email = e.email or "—"
    birth = e.birth_date.strftime("%d.%m.%Y") if e.birth_date else "—"
    hire = e.hire_date.strftime("%d.%m.%Y") if e.hire_date else "—"
    return f"[{idx}] {e.first_name} {e.last_name}  (Email: {email}, Birth: {birth}, Hire: {hire})"


def prompt_index(max_n: int) -> Optional[int]:
    print("[0] Cancel")
    while True:
        choice = input("Enter number: ").strip().lower()
        if choice in {"0", "q", "quit", ""}:
            return None
        if choice.isdigit():
            idx = int(choice)
            if 1 <= idx <= max_n:
                return idx
        print("Invalid choice. Please enter a valid number.")


def pick_employee(s: Session, title: str = "Select employee") -> "Employee | None":
    employees = fetch_employees(s)
    if not employees:
        print("✗ No employees in the database.")
        return None

    print(f"\n{title}:")
    for i, e in enumerate(employees, start=1):
        print(format_employee_row(e, i))

    idx = prompt_index(len(employees))
    return None if idx is None else employees[idx - 1]


def collect_employee_input() -> Optional[Tuple[str, str, str, "date", "date"]]:
    print("\nCreate new employee (0=Cancel for any field):")
    first = input("First name: ").strip()
    if not first or first == "0":
        return None
    last = input("Last name: ").strip()
    if not last or last == "0":
        return None
    email = input("Email: ").strip()
    if not email or email == "0":
        return None

    born = prompt_ddmmyyyy("Birth date")
    if born is None:
        return None
    hire = prompt_ddmmyyyy("Hire date")
    if hire is None:
        return None

    return first, last, email, born, hire


def to_employee(
    first: str, last: str, email: str, born: "date", hire: "date"
) -> "Employee":
    return Employee(
        first_name=first,
        last_name=last,
        email=email,
        birth_date=born,
        hire_date=hire,
    )


def save_employee(s: Session, emp: "Employee") -> bool:
    try:
        s.add(emp)
        s.commit()
        s.refresh(emp)
        return True
    except IntegrityError:
        s.rollback()
        return False


def create_employee(s: Session) -> "Employee | None":
    data = collect_employee_input()
    if data is None:
        return None
    first, last, email, born, hire = data

    emp = to_employee(first, last, email, born, hire)
    if save_employee(s, emp):
        print(f"✓ Employee created: {emp.first_name} {emp.last_name} ({emp.email})")
        return emp
    else:
        print("✗ Email already in use (UNIQUE).")
        return None


def collect_time_entry_input() -> Optional[tuple[date, str, str, str]]:
    d = prompt_ddmmyyyy("Date")
    if d is None:
        return None
    start = prompt_time("Start")
    if start is None:
        return None
    end = prompt_time("End")
    if end is None:
        return None
    pause = prompt_time("Break")
    if pause is None:
        return None
    return d, start, end, pause


def to_time_entry(
    employee_id: int, d: date, start: str, end: str, pause: str
) -> "TimeEntry":
    return TimeEntry.from_input(
        Date=d.strftime("%d.%m.%Y"),
        Start=start,
        Ende=end,
        Pause=pause,
        employee_id=employee_id,
    )


def save_time_entry(s: Session, te: "TimeEntry") -> bool:
    exists = s.exec(
        select(TimeEntry).where(
            TimeEntry.Date == te.Date,
            TimeEntry.Start == te.Start,
            TimeEntry.employee_id == te.employee_id,
        )
    ).first()
    if exists:
        return False
    s.add(te)
    s.commit()
    return True


def add_time_entry_interactive(s: Session):
    emp = pick_employee(s, "Record time – choose employee")
    if not emp:
        return
    inputs = collect_time_entry_input()
    if inputs is None:
        return
    d, start, end, pause = inputs

    try:
        te = to_time_entry(emp.id, d, start, end, pause)
    except Exception as e:
        print(f"✗ Invalid inputs: {e}")
        return

    if save_time_entry(s, te):
        print(
            f"✓ Entry saved for {emp.first_name} {emp.last_name} on {te.Date:%d.%m.%Y}."
        )
    else:
        print("ⓘ Similar entry already exists. No insert.")


def fetch_employee_entries(s: Session, employee_id: int) -> List[TimeEntry]:
    return s.exec(
        select(TimeEntry)
        .where(TimeEntry.employee_id == employee_id)
        .options(selectinload(TimeEntry.employee))
        .order_by(TimeEntry.Date, TimeEntry.Start)
    ).all()


def summarize_minutes_by_month(rows: list[TimeEntry]) -> dict[tuple[int, int], int]:
    acc: dict[tuple[int, int], int] = {}
    for r in rows:
        ym = (r.Date.year, r.Date.month)
        acc[ym] = acc.get(ym, 0) + minutes_from_entry(r)
    return acc


def prompt_month_choice(ym_list: List[Tuple[int, int]]) -> Optional[Tuple[int, int]]:
    print("Available months:")
    print("[0] All months (monthly overview)")
    for i, (y, m) in enumerate(ym_list, start=1):
        print(f"[{i}] {MONTH_EN[m]} {y}")

    while True:
        choice = input("Choose month (number, 0/Enter=Overview): ").strip()
        if choice in {"", "0"}:
            return None
        if choice.isdigit():
            idx = int(choice)
            if 1 <= idx <= len(ym_list):
                return ym_list[idx - 1]
        print("Invalid choice.")


def print_report_for_employee(s: Session):
    emp = pick_employee(s, "Report – choose employee")
    if not emp:
        return

    rows = fetch_employee_entries(s, emp.id)
    monthly_sum = summarize_minutes_by_month(rows)
    ym_list = sorted(monthly_sum.keys())

    print("\nReport for:")
    birth = emp.birth_date.strftime("%d.%m.%Y") if emp.birth_date else "—"
    hire = emp.hire_date.strftime("%d.%m.%Y") if emp.hire_date else "—"
    email = emp.email or "—"
    print(f"  Name:      {emp.first_name} {emp.last_name}")
    print(f"  Birth:     {birth}")
    print(f"  Hire date: {hire}")
    print(f"  Email:     {email}")
    print("-" * 60)

    if not ym_list:
        print("No entries found.")
        return

    sel = prompt_month_choice(ym_list)

    if sel is None:
        print("\nMonthly overview:")
        print("-" * 60)
        for y, m in ym_list:
            print(f"{MONTH_EN[m]} {y:<4}  —  {fmt_hhmm(monthly_sum[(y, m)])}")
        print("-" * 60)
        return

    y, m = sel
    month_rows = [r for r in rows if r.Date.year == y and r.Date.month == m]

    print(f"\nPeriod: {MONTH_EN[m]} {y}")
    if not month_rows:
        print("No entries in this month.")
        return

    print("Entries:")
    for r in month_rows:
        print(
            f"[{r.id}] {r.Date:%d.%m.%Y}  "
            f"{r.Start:%H:%M}–{r.Ende:%H:%M}  "
            f"Break {r.Pause:%H:%M}  "
            f"Net {fmt_hhmm(minutes_from_entry(r))}"
        )
    print("-" * 60)
    print(f"Sum (month): {fmt_hhmm(monthly_sum[(y, m)])}")


def main():
    engine = get_engine()
    SQLModel.metadata.create_all(engine)

    with Session(engine) as s:
        while True:
            print("\n--- Menu ---")
            print("1) Create new employee")
            print("2) Record time for employee")
            print("3) Show report")
            print("4) Exit")
            choice = input("Choose [1-4]: ").strip()

            if choice == "1":
                create_employee(s)
            elif choice == "2":
                add_time_entry_interactive(s)
            elif choice == "3":
                print_report_for_employee(s)
            elif choice == "4":
                print("Bye! Have a nice day!")
                break
            else:
                print("Invalid choice.")


if __name__ == "__main__":
    main()
