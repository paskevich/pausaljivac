import calendar
from datetime import date

from services import settings_store


def ensure_tax_payments_for_current_month(db):
    """Backfills any missing monthly payments up to and including the current
    due month, so gaps from not opening the app for a while get caught up."""
    today = date.today()

    earliest = db.execute("SELECT MIN(valid_from) AS d FROM tax_resenja").fetchone()["d"]
    if earliest is None:
        return

    earliest_date = date.fromisoformat(earliest)
    due_year, due_month = earliest_date.year, earliest_date.month + 1
    if due_month > 12:
        due_year, due_month = due_year + 1, 1

    while (due_year, due_month) <= (today.year, today.month):
        _ensure_for_due_month(db, due_year, due_month)
        due_month += 1
        if due_month > 12:
            due_year, due_month = due_year + 1, 1


def _ensure_for_due_month(db, due_year, due_month):
    # By law the akontacija due by the due_day of due_year/due_month pays for
    # the *previous* calendar month, not the month the due date falls in.
    if due_month == 1:
        period_year, period_month = due_year - 1, 12
    else:
        period_year, period_month = due_year, due_month - 1

    existing = db.execute(
        "SELECT id FROM tax_payments WHERE period_year = ? AND period_month = ?",
        (period_year, period_month),
    ).fetchone()
    if existing:
        return

    period_start = date(period_year, period_month, 1).isoformat()
    resenje = db.execute(
        "SELECT * FROM tax_resenja WHERE valid_from <= ? "
        "AND (valid_to IS NULL OR valid_to >= ?) ORDER BY valid_from DESC LIMIT 1",
        (period_start, period_start),
    ).fetchone()
    if resenje is None:
        return

    due_day = int(settings_store.get("tax_due_day", "15") or 15)
    last_day = calendar.monthrange(due_year, due_month)[1]
    due_day = min(due_day, last_day)
    due_date = date(due_year, due_month, due_day).isoformat()

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
            period_year,
            period_month,
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
