from datetime import date

from flask import Blueprint, Response, request

from database import get_db
from services import pdf_generator, settings_store

bp = Blueprint("reports", __name__, url_prefix="/reports")


@bp.route("/kpo")
def kpo():
    db = get_db()
    year = request.args.get("year", type=int) or date.today().year

    invoices = db.execute(
        "SELECT invoices.*, clients.name AS client_name FROM invoices "
        "JOIN clients ON clients.id = invoices.client_id "
        "WHERE invoices.status != 'cancelled' AND strftime('%Y', issue_date) = ? "
        "ORDER BY issue_date, invoices.id",
        (str(year),),
    ).fetchall()

    rows = []
    total = 0
    for i, inv in enumerate(invoices, start=1):
        amount = inv["amount_rsd"] or 0
        total += amount
        rows.append({
            "redni_broj": i,
            "opis": f"{inv['issue_date']} — račun {inv['invoice_number']} — {inv['client_name']}",
            "usluge": amount,
        })

    pdf_bytes = pdf_generator.generate_kpo_pdf({
        "settings": settings_store.get_all(),
        "year": year,
        "rows": rows,
        "total": total,
    })

    return Response(
        pdf_bytes,
        mimetype="application/pdf",
        headers={"Content-Disposition": f"inline; filename=KPO_{year}.pdf"},
    )
