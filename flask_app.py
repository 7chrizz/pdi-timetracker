import calendar
import os
from datetime import date, datetime

from dotenv import load_dotenv
from flask import Flask, flash, redirect, render_template, request, url_for
from flask_login import (
    LoginManager,
    UserMixin,
    current_user,
    login_required,
    login_user,
    logout_user,
)
from sqlmodel import Session

from main import (
    MONTH_EN,
    fetch_employee_entries,
    fetch_employees,
    fmt_hhmm,
    get_engine,
    minutes_from_entry,
    save_time_entry,
    summarize_minutes_by_month,
    to_time_entry,
    create_tables,
)
from models import Employee

app = Flask(__name__)
load_dotenv()
app.secret_key = os.getenv("SECRET_KEY", "dev")

login_manager = LoginManager()
login_manager.init_app(app)
login_manager.login_view = "login"
login_manager.login_message_category = "info"

ADMIN_USERNAME = os.getenv("ADMIN_USERNAME", "admin")
ADMIN_PASSWORD = os.getenv("ADMIN_PASSWORD", "test123")


class SimpleUser(UserMixin):
    def __init__(self, user_id: int, username: str):
        self.id = user_id
        self.username = username


SINGLE_USER = SimpleUser(1, ADMIN_USERNAME)


@login_manager.user_loader
def load_user(user_id: str):
    return SINGLE_USER if str(SINGLE_USER.id) == str(user_id) else None


engine = get_engine()
create_tables(engine)


def minutes_to_hhmm(mins: int) -> str:
    mins = max(0, int(mins or 0))
    h, m = divmod(mins, 60)
    return f"{h:02d}:{m:02d}"


def business_minutes_in_month(year: int, month: int, hours_per_day: int = 8) -> int:
    _, last_day = calendar.monthrange(year, month)
    workdays = sum(
        1 for d in range(1, last_day + 1) if date(year, month, d).weekday() < 5
    )
    return workdays * hours_per_day * 60


def mins_to_hours_txt(mins: int) -> str:
    return str(round((mins or 0) / 60.0, 1)).replace(".", ",")


def available_years(session: Session) -> list[int]:
    years = set()
    employees = fetch_employees(session)
    for employee in employees:
        rows = fetch_employee_entries(session, employee.id)
        monthly = summarize_minutes_by_month(rows)
        years.update(y for (y, _m) in monthly.keys())
    return sorted(years)


@app.route("/", methods=["GET"])
@login_required
def home():
    return redirect(url_for("report"))


@app.route("/login", methods=["GET", "POST"])
def login():
    if hasattr(current_user, "is_authenticated") and current_user.is_authenticated:
        return redirect(url_for("report"))

    if request.method == "POST":
        username = request.form.get("username", "").strip()
        password = request.form.get("password", "")

        if username == SINGLE_USER.username and password == ADMIN_PASSWORD:
            login_user(SINGLE_USER)
            next_url = request.args.get("next")
            return redirect(next_url or url_for("report"))

        else:
            flash("Invalid username or password.", "danger")

    return render_template("login.html")


@app.route("/logout", methods=["POST"])
@login_required
def logout():
    logout_user()
    flash("You have been logged out.", "info")
    return redirect(url_for("login"))


@app.route("/report", methods=["GET"])
@login_required
def report():
    selected_year = request.args.get("year", type=int) or date.today().year
    user_name = "User"

    def hours_text_from_minutes(minutes: int) -> str:
        return f"{round((minutes or 0) / 60.0, 1)}".replace(".", ",")

    with Session(engine) as session:
        available_years_list = available_years(session)

        if not available_years_list:
            return render_template(
                "report.html",
                employee_cards=[],
                available_years_list=[],
                selected_year=selected_year,
                user_name=user_name,
            )

        if selected_year not in available_years_list:
            selected_year = max(available_years_list)

        all_employees = fetch_employees(session)
        employee_cards = []

        for employee in all_employees:
            time_entries = fetch_employee_entries(session, employee.id)
            monthly_minutes_summary = summarize_minutes_by_month(time_entries)

            months_for_selected_year = sorted(
                (year, month)
                for (year, month) in monthly_minutes_summary.keys()
                if year == selected_year
            )

            month_rows = []
            total_difference_minutes = 0

            for _year, month in months_for_selected_year:
                worked_minutes = monthly_minutes_summary.get((selected_year, month), 0)
                target_minutes = business_minutes_in_month(
                    selected_year, month, hours_per_day=8
                )
                total_difference_minutes += worked_minutes - target_minutes

                month_rows.append(
                    {
                        "label": MONTH_EN[month],
                        "current_txt": hours_text_from_minutes(worked_minutes),
                        "target_txt": hours_text_from_minutes(target_minutes),
                    }
                )

            employee_cards.append(
                {
                    "id": employee.id,
                    "name": f"{employee.first_name} {employee.last_name}",
                    "months": month_rows,
                    "sum_diff_sign": "-" if total_difference_minutes < 0 else "+",
                    "sum_diff_txt": mins_to_hours_txt(abs(total_difference_minutes)),
                    "remaining_holidays": employee.holidays,
                    "sick_count": 0,
                }
            )

    return render_template(
        "report.html",
        employee_cards=employee_cards,
        available_years_list=available_years_list,
        selected_year=selected_year,
        user_name=current_user.username,
    )


@app.route("/time/record", methods=["GET"])
@login_required
def time_record():
    with Session(engine) as s:
        employees = fetch_employees(s)
    return render_template("index.html", employees=employees)


@app.route("/add_time", methods=["POST"])
@login_required
def add_time():
    employee_id = request.form.get("employee")
    date_iso = request.form.get("date")
    start = request.form.get("start")
    end_ = request.form.get("end")
    pause_min = request.form.get("pause")

    if not all([employee_id, date_iso, start, end_]):
        flash("Please enter all fields.", "error")
        return redirect(url_for("time_record"))

    d = datetime.strptime(date_iso, "%Y-%m-%d").date()
    pause_hhmm = minutes_to_hhmm(pause_min)

    te = to_time_entry(int(employee_id), d, start, end_, pause_hhmm)

    with Session(engine) as s:
        emp = s.get(Employee, int(employee_id))
        ok = save_time_entry(s, te)

        if not ok:
            flash("A similar entry already exists. Nothing saved.", "error")
            return redirect(url_for("time_record"))

        netto = fmt_hhmm(minutes_from_entry(te))
        saved_info = {
            "name": f"{emp.first_name} {emp.last_name}",
            "start": start,
            "end": end_,
            "pause": pause_min,
            "netto": netto,
        }

        employees = fetch_employees(s)

    flash("Time successfully added!", "success")
    return render_template("index.html", employees=employees, saved_info=saved_info)


if __name__ == "__main__":
    app.run(debug=True)
