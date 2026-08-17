from datetime import date

from flask import Blueprint, render_template

from database import get_db
from services import limit_calculations, tax_schedule

bp = Blueprint("dashboard", __name__)


@bp.route("/")
def index():
    db = get_db()
    tax_schedule.ensure_tax_payments_for_current_month(db)

    limits = limit_calculations.get_dashboard_limits(db)

    upcoming_payments = db.execute(
        "SELECT * FROM tax_payments WHERE status = 'unpaid' ORDER BY due_date ASC LIMIT 5"
    ).fetchall()

    invoice_stats = db.execute(
        "SELECT COUNT(*) AS cnt, COALESCE(SUM(amount_rsd), 0) AS total_rsd "
        "FROM invoices WHERE status != 'cancelled' "
        "AND strftime('%Y', issue_date) = strftime('%Y', 'now')"
    ).fetchone()

    unpaid_count = db.execute(
        "SELECT COUNT(*) AS cnt FROM tax_payments WHERE status = 'unpaid'"
    ).fetchone()["cnt"]

    return render_template(
        "dashboard.html",
        limits=limits,
        upcoming_payments=upcoming_payments,
        today=date.today().isoformat(),
        invoice_stats=invoice_stats,
        unpaid_count=unpaid_count,
    )
