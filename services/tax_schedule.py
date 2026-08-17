import calendar
from datetime import date

from services import settings_store


def ensure_tax_payments_for_current_month(db):
    today = date.today()
    _ensure_for_period(db, today.year, today.month)


def _ensure_for_period(db, year, month):
    existing = db.execute(
        "SELECT id FROM tax_payments WHERE period_year = ? AND period_month = ?",
        (year, month),
    ).fetchone()
    if existing:
        return

    period_start = date(year, month, 1).isoformat()
    resenje = db.execute(
        "SELECT * FROM tax_resenja WHERE valid_from <= ? "
        "AND (valid_to IS NULL OR valid_to >= ?) ORDER BY valid_from DESC LIMIT 1",
        (period_start, period_start),
    ).fetchone()
    if resenje is None:
        return

    due_day = int(settings_store.get("tax_due_day", "15") or 15)
    last_day = calendar.monthrange(year, month)[1]
    due_day = min(due_day, last_day)
    due_date = date(year, month, due_day).isoformat()

    amount_due = (
        resenje["pausal_tax_amount"]
        + resenje["pio_contribution"]
        + resenje["health_contribution"]
        + resenje["unemployment_contribution"]
    )

    db.execute(
        "INSERT OR IGNORE INTO tax_payments (period_year, period_month, due_date, "
        "resenje_id, pausal_tax_amount, pio_contribution, health_contribution, "
        "unemployment_contribution, amount_due) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
        (
            year,
            month,
            due_date,
            resenje["id"],
            resenje["pausal_tax_amount"],
            resenje["pio_contribution"],
            resenje["health_contribution"],
            resenje["unemployment_contribution"],
            amount_due,
        ),
    )
    db.commit()
