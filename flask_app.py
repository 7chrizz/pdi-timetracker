from datetime import datetime

from flask import Flask, flash, redirect, render_template, request, url_for
from sqlmodel import Session, SQLModel

from main import (
    fetch_employees,
    fmt_hhmm,
    get_engine,
    minutes_from_entry,
    save_time_entry,
    to_time_entry,
)
from models import Employee

app = Flask(__name__)
app.secret_key = "dev"
engine = get_engine()
SQLModel.metadata.create_all(engine)


def minutes_to_hhmm(mins: int) -> str:
    mins = max(0, int(mins or 0))
    h, m = divmod(mins, 60)
    return f"{h:02d}:{m:02d}"


@app.route("/", methods=["GET"])
def home():
    with Session(engine) as s:
        employees = fetch_employees(s)
    return render_template("index.html", employees=employees)


@app.route("/add_time", methods=["POST"])
def add_time():
    employee_id = request.form.get("employee")
    date_iso = request.form.get("date")
    start = request.form.get("start")
    end_ = request.form.get("end")
    pause_min = request.form.get("pause")

    if not all([employee_id, date_iso, start, end_]):
        flash("Please enter all fields.", "error")
        return redirect(url_for("home"))

    d = datetime.strptime(date_iso, "%Y-%m-%d").date()
    pause_hhmm = minutes_to_hhmm(pause_min)

    te = to_time_entry(int(employee_id), d, start, end_, pause_hhmm)

    with Session(engine) as s:
        emp = s.get(Employee, int(employee_id))
        ok = save_time_entry(s, te)

        if not ok:
            flash("A similar entry already exists. Nothing saved.", "error")
            return redirect(url_for("home"))

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
