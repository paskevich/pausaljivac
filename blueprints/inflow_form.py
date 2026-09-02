import io
import logging
import re
import uuid
from datetime import date

from flask import Blueprint, flash, redirect, render_template, request, send_file, url_for

import config
from database import get_db
from services import inflow_form, settings_store

bp = Blueprint("inflow_form", __name__, url_prefix="/bank-forms")
logger = logging.getLogger(__name__)


def _display_date(iso_date):
    if not iso_date:
        return ""
    return date.fromisoformat(iso_date).strftime("%d/%m/%Y")


@bp.route("/fill", methods=["GET", "POST"])
def upload():
    if request.method == "POST":
        file = request.files.get("file")
        if not file or file.filename == "":
            flash("Выберите PDF-бланк от банка.", "error")
            return redirect(url_for("inflow_form.upload"))

        pdf_bytes = file.read()
        try:
            parsed = inflow_form.parse_blank_form(pdf_bytes)
        except Exception:
            logger.exception("Failed to parse uploaded bank form %r", file.filename)
            flash("Не удалось прочитать PDF. Проверьте, что это корректный файл.", "error")
            return redirect(url_for("inflow_form.upload"))

        config.TMP_DIR.mkdir(parents=True, exist_ok=True)
        token = uuid.uuid4().hex
        (config.TMP_DIR / f"{token}.pdf").write_bytes(pdf_bytes)

        db = get_db()
        invoice = None
        if parsed["invoice_number"]:
            invoice = db.execute(
                "SELECT invoices.*, clients.name AS client_name FROM invoices "
                "JOIN clients ON clients.id = invoices.client_id "
                "WHERE invoice_number = ?",
                (parsed["invoice_number"],),
            ).fetchone()

        # The bank doesn't always print the invoice number on its own form
        # (e.g. a transfer referencing a withdrawal request instead of an
        # invoice) — fall back to matching on currency + amount, which the
        # bank always fills in, when that pins down exactly one invoice.
        if invoice is None and parsed["currency"] and parsed["amount_display"]:
            try:
                parsed_amount = float(parsed["amount_display"].replace(",", ""))
            except ValueError:
                parsed_amount = None
            if parsed_amount is not None:
                candidates = db.execute(
                    "SELECT invoices.*, clients.name AS client_name FROM invoices "
                    "JOIN clients ON clients.id = invoices.client_id "
                    "WHERE invoices.currency = ? AND ABS(invoices.amount - ?) < 0.005 "
                    "AND invoices.id NOT IN ("
                    "  SELECT invoice_id FROM documents "
                    "  WHERE category = 'bank_report' AND invoice_id IS NOT NULL"
                    ")",
                    (parsed["currency"], parsed_amount),
                ).fetchall()
                if len(candidates) == 1:
                    invoice = candidates[0]
                    parsed["invoice_number"] = invoice["invoice_number"]

        default_date = ""
        if invoice is not None:
            default_date = _display_date(invoice["service_date"] or invoice["issue_date"])

        settings_values = settings_store.get_all()

        all_invoices = db.execute(
            "SELECT invoices.id, invoices.invoice_number, invoices.issue_date, "
            "invoices.service_date, clients.name AS client_name FROM invoices "
            "JOIN clients ON clients.id = invoices.client_id "
            "ORDER BY invoices.issue_date DESC, invoices.id DESC"
        ).fetchall()
        invoice_options = [
            {
                "id": row["id"],
                "invoice_number": row["invoice_number"],
                "client_name": row["client_name"],
                "date_display": _display_date(row["service_date"] or row["issue_date"]),
            }
            for row in all_invoices
        ]

        return render_template(
            "inflow_form/review.html",
            token=token,
            parsed=parsed,
            invoice=invoice,
            default_date=default_date,
            sifra_osnova=settings_values.get("bank_form_sifra_osnova") or "302",
            place=settings_values.get("bank_form_place") or "Novi Sad",
            has_signature=config.SIGNATURE_PATH.exists(),
            invoice_options=invoice_options,
        )

    return render_template("inflow_form/upload.html", has_signature=config.SIGNATURE_PATH.exists())


@bp.route("/generate", methods=["POST"])
def generate():
    form = request.form
    token = form.get("token", "")
    pdf_path = config.TMP_DIR / f"{token}.pdf"
    if not token or not pdf_path.exists():
        flash("Сессия заполнения формы истекла — загрузите бланк заново.", "error")
        return redirect(url_for("inflow_form.upload"))

    if not config.SIGNATURE_PATH.exists():
        flash("Сначала загрузите PNG подписи в Настройках.", "error")
        return redirect(url_for("inflow_form.upload"))

    invoice_number = form.get("invoice_number", "").strip()
    currency = form.get("currency", "").strip()
    amount_display = form.get("amount_display", "").strip()
    invoice_date_display = form.get("invoice_date_display", "").strip()
    sifra_osnova = form.get("sifra_osnova", "").strip()
    place = form.get("place", "").strip()
    invoice_id = form.get("invoice_id") or None

    errors = []
    if not invoice_number:
        errors.append("Укажите номер инвойса.")
    if not currency or not amount_display:
        errors.append("Не удалось определить сумму — она должна быть указана банком в бланке.")
    if not invoice_date_display:
        errors.append("Укажите дату инвойса.")
    elif not re.match(r"^\d{2}/\d{2}/\d{4}$", invoice_date_display):
        errors.append("Дата инвойса должна быть в формате ДД/ММ/ГГГГ.")
    if not sifra_osnova:
        errors.append("Укажите šifra osnova.")
    if not place:
        errors.append("Укажите место подписания.")

    if errors:
        for e in errors:
            flash(e, "error")
        return redirect(url_for("inflow_form.upload"))

    pdf_bytes = pdf_path.read_bytes()
    signature_bytes = config.SIGNATURE_PATH.read_bytes()

    try:
        filled = inflow_form.fill_form(
            pdf_bytes,
            sifra_osnova=sifra_osnova,
            invoice_number=invoice_number,
            invoice_date_display=invoice_date_display,
            description=None,
            currency=currency,
            amount_display=amount_display,
            place=place,
            sign_date_display=inflow_form.today_display(),
            signature_png_bytes=signature_bytes,
        )
    except ValueError as e:
        logger.exception("Failed to fill bank form for invoice %r", invoice_number)
        flash(str(e), "error")
        return redirect(url_for("inflow_form.upload"))

    pdf_path.unlink(missing_ok=True)

    db = get_db()
    out_filename = f"obavestenje_o_prilivu_{invoice_number.replace('/', '-')}.pdf"

    target_dir = config.DOCUMENTS_DIR / "bank_report"
    target_dir.mkdir(parents=True, exist_ok=True)
    stored_name = f"{uuid.uuid4().hex[:8]}__{out_filename}"
    (target_dir / stored_name).write_bytes(filled)
    relative_path = f"bank_report/{stored_name}"

    client_id = None
    if invoice_id:
        inv = db.execute("SELECT client_id FROM invoices WHERE id = ?", (invoice_id,)).fetchone()
        if inv:
            client_id = inv["client_id"]

    db.execute(
        "INSERT INTO documents (category, client_id, invoice_id, title, file_path, "
        "original_filename, mime_type) VALUES ('bank_report', ?, ?, ?, ?, ?, 'application/pdf')",
        (client_id, invoice_id, f"Obaveštenje o prilivu {invoice_number}", relative_path, out_filename),
    )
    db.commit()

    flash("Форма заполнена, подписана и сохранена в Документах.", "success")
    return send_file(
        io.BytesIO(filled), mimetype="application/pdf",
        as_attachment=True, download_name=out_filename,
    )
