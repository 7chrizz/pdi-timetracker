from collections import defaultdict
from datetime import date, datetime
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import selectinload
from sqlmodel import SQLModel, create_engine, Session, select
from models import Employee, TimeEntry

DB_URL = "sqlite:///timetracker.db"

MONTH_EN = [
    "",
    "January", "February", "March", "April", "May", "June",
    "July", "August", "September", "October", "November", "December"
]

def minutes_from_entry(e) -> int:
    def to_min(t): return t.hour * 60 + t.minute
    start = to_min(e.Start)
    end = to_min(e.Ende)
    pause = to_min(e.Pause)
    if end < start:
        end += 24 * 60
    return max(0, end - start - pause)

def fmt_hhmm(mins: int) -> str:
    return f"{mins // 60:02d}:{mins % 60:02d}"


def get_engine():
    engine = create_engine(DB_URL, echo=False, connect_args={"check_same_thread": False})
    with engine.connect() as conn:
        conn.exec_driver_sql("PRAGMA foreign_keys = ON;")
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


def pick_employee_interactive(s: Session, title: str = "Select employee") -> Employee | None:
    employees = s.exec(
        select(Employee).order_by(Employee.last_name, Employee.first_name)
    ).all()
    if not employees:
        print("✗ No employees in the database.")
        return None

    print(f"\n{title}:")
    for i, e in enumerate(employees, start=1):
        print(
            f"[{i}] {e.first_name} {e.last_name}  "
            f"(Email: {e.email}, Birth: {e.birth_date:%d.%m.%Y}, Hire: {e.hire_date:%d.%m.%Y})"
        )
    print("[0] Cancel")

    while True:
        choice = input("Enter number: ").strip()
        if choice == "0" or choice.lower() in {"q", "quit"}:
            return None
        if choice.isdigit():
            idx = int(choice)
            if 1 <= idx <= len(employees):
                return employees[idx - 1]
        print("Invalid choice. Please enter a valid number.")


def create_employee_interactive(s: Session) -> Employee | None:
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

    emp = Employee(first_name=first, last_name=last, email=email, birth_date=born, hire_date=hire)
    s.add(emp)
    try:
        s.commit()
        s.refresh(emp)
        print(f"✓ Employee created: {emp.first_name} {emp.last_name} ({emp.email})")
        return emp
    except IntegrityError:
        s.rollback()
        print("✗ Email already in use (UNIQUE).")
        return None


def add_time_entry_interactive(s: Session):
    emp = pick_employee_interactive(s, "Record time – choose employee")
    if not emp:
        return

    d = prompt_ddmmyyyy("Date")
    if d is None:
        return
    start = prompt_time("Start")
    if start is None:
        return
    end = prompt_time("End")
    if end is None:
        return
    pause = prompt_time("Break")
    if pause is None:
        return

    try:
        te = TimeEntry.from_input(
            Date=d.strftime("%d.%m.%Y"),
            Start=start,
            Ende=end,
            Pause=pause,
            employee_id=emp.id
        )
    except Exception as e:
        print(f"✗ Invalid inputs: {e}")
        return

    exists = s.exec(
        select(TimeEntry).where(
            TimeEntry.Date == te.Date,
            TimeEntry.Start == te.Start,
            TimeEntry.employee_id == emp.id,
        )
    ).first()
    if exists:
        print("ⓘ Similar entry already exists. No insert.")
        return

    s.add(te)
    s.commit()
    print(f"✓ Entry saved for {emp.first_name} {emp.last_name} on {te.Date:%d.%m.%Y}.")


def print_report_for_employee(s: Session):
    emp = pick_employee_interactive(s, "Report – choose employee")
    if not emp:
        return

    all_rows = s.exec(
        select(TimeEntry)
        .where(TimeEntry.employee_id == emp.id)
        .options(selectinload(TimeEntry.employee))
        .order_by(TimeEntry.Date, TimeEntry.Start)
    ).all()

    monthly_sum = defaultdict(int)
    for r in all_rows:
        ym = (r.Date.year, r.Date.month)
        monthly_sum[ym] += minutes_from_entry(r)

    ym_list = sorted(monthly_sum.keys())

    print("\nReport for:")
    print(f"  Name:      {emp.first_name} {emp.last_name}")
    print(f"  Birth:     {emp.birth_date:%d.%m.%Y}")
    print(f"  Hire date: {emp.hire_date:%d.%m.%Y}")
    print(f"  Email:     {emp.email}")
    print("-" * 60)

    if not ym_list:
        print("No entries found.")
        return

    # Month selection
    print("Available months:")
    print("[0] All months (monthly overview)")
    for i, (y, m) in enumerate(ym_list, start=1):
        print(f"[{i}] {MONTH_EN[m]} {y}")

    sel = None
    while True:
        choice = input("Choose month (number, 0/Enter=Overview): ").strip()
        if choice == "" or choice == "0":
            sel = None
            break
        if choice.isdigit():
            idx = int(choice)
            if 1 <= idx <= len(ym_list):
                sel = ym_list[idx - 1]  # (year, month)
                break
        print("Invalid choice.")

    if sel is None:
        print("\nMonthly overview:")
        print("-" * 60)
        for (y, m) in ym_list:
            print(f"{MONTH_EN[m]} {y:<4}  —  {fmt_hhmm(monthly_sum[(y, m)])}")
        print("-" * 60)
        return

    y, m = sel
    rows = [r for r in all_rows if r.Date.year == y and r.Date.month == m]

    print(f"\nPeriod: {MONTH_EN[m]} {y}")
    if not rows:
        print("No entries in this month.")
        return

    print("Entries:")
    for r in rows:
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
                create_employee_interactive(s)
            elif choice == "2":
                add_time_entry_interactive(s)
            elif choice == "3":
                print_report_for_employee(s)
            elif choice == "4":
                print("Bye!")
                break
            else:
                print("Invalid choice.")

if __name__ == "__main__":
    main()
