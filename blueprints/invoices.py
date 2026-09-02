import re
from datetime import date

from flask import (
    Blueprint,
    abort,
    flash,
    redirect,
    render_template,
    request,
    send_from_directory,
    url_for,
)
from werkzeug.utils import secure_filename

import config
from database import get_db
from services import exchange_rates, invoice_numbering, pdf_generator, settings_store
from blueprints.documents import create_invoice_document

bp = Blueprint("invoices", __name__, url_prefix="/invoices")

STATUS_LABELS = {
    "draft": "Черновик",
    "issued": "Выставлен",
    "paid": "Оплачен",
    "cancelled": "Отменён",
}


def _past_descriptions(db):
    return [
        row["description"] for row in db.execute(
            "SELECT DISTINCT description FROM invoices "
            "WHERE description != '' ORDER BY description COLLATE NOCASE"
        ).fetchall()
    ]


@bp.route("/")
def list_invoices():
    db = get_db()
    invoices = db.execute(
        "SELECT invoices.*, clients.name AS client_name FROM invoices "
        "JOIN clients ON clients.id = invoices.client_id "
        "ORDER BY invoices.issue_date DESC, invoices.id DESC"
    ).fetchall()
    kpo_years = [
        row["yr"] for row in db.execute(
            "SELECT DISTINCT strftime('%Y', issue_date) AS yr FROM invoices "
            "WHERE status != 'cancelled' ORDER BY yr DESC"
        ).fetchall()
    ]
    return render_template(
        "invoices/list.html", invoices=invoices, status_labels=STATUS_LABELS,
        kpo_years=kpo_years,
    )


@bp.route("/<int:invoice_id>")
def view_invoice(invoice_id):
    db = get_db()
    invoice = db.execute(
        "SELECT invoices.*, clients.name AS client_name, "
        "documents.title AS contract_title FROM invoices "
        "JOIN clients ON clients.id = invoices.client_id "
        "LEFT JOIN documents ON documents.id = invoices.contract_document_id "
        "WHERE invoices.id = ?",
        (invoice_id,),
    ).fetchone()
    if invoice is None:
        abort(404)
    return render_template(
        "invoices/view.html", invoice=invoice, status_labels=STATUS_LABELS
    )


@bp.route("/<int:invoice_id>/edit", methods=["GET", "POST"])
def edit_invoice(invoice_id):
    db = get_db()
    invoice = db.execute("SELECT * FROM invoices WHERE id = ?", (invoice_id,)).fetchone()
    if invoice is None:
        abort(404)

    clients = db.execute(
        "SELECT * FROM clients ORDER BY name COLLATE NOCASE"
    ).fetchall()
    contracts = db.execute(
        "SELECT documents.id, documents.title, clients.name AS client_name "
        "FROM documents LEFT JOIN clients ON clients.id = documents.client_id "
        "WHERE documents.category = 'contract' ORDER BY documents.title"
    ).fetchall()
    past_descriptions = _past_descriptions(db)

    if request.method == "POST":
        form = request.form
        client_id = form.get("client_id")
        service_date = form.get("service_date") or None
        due_date = form.get("due_date") or None
        description = form.get("description", "").strip()
        contract_document_id = form.get("contract_document_id") or None
        notes = form.get("notes", "").strip()

        errors = []
        if not client_id:
            errors.append("Выберите клиента.")
        if not description:
            errors.append("Укажите описание услуги.")

        if errors:
            for e in errors:
                flash(e, "error")
            return render_template(
                "invoices/edit_form.html",
                invoice=invoice, clients=clients, contracts=contracts, form=form,
                past_descriptions=past_descriptions,
            )

        db.execute(
            "UPDATE invoices SET client_id = ?, service_date = ?, due_date = ?, "
            "description = ?, contract_document_id = ?, notes = ? WHERE id = ?",
            (client_id, service_date, due_date, description, contract_document_id, notes, invoice_id),
        )
        db.commit()

        flash("Инвойс обновлён.", "success")
        return redirect(url_for("invoices.view_invoice", invoice_id=invoice_id))

    return render_template(
        "invoices/edit_form.html", invoice=invoice, clients=clients, contracts=contracts,
        form=dict(invoice), past_descriptions=past_descriptions,
    )


@bp.route("/<int:invoice_id>/pdf")
def download_pdf(invoice_id):
    db = get_db()
    invoice = db.execute("SELECT * FROM invoices WHERE id = ?", (invoice_id,)).fetchone()
    if invoice is None or not invoice["pdf_path"]:
        abort(404)
    return send_from_directory(
        config.DOCUMENTS_DIR, invoice["pdf_path"], as_attachment=False
    )


@bp.route("/<int:invoice_id>/delete", methods=["GET"])
def confirm_delete_invoice(invoice_id):
    db = get_db()
    invoice = db.execute(
        "SELECT invoices.*, clients.name AS client_name FROM invoices "
        "JOIN clients ON clients.id = invoices.client_id WHERE invoices.id = ?",
        (invoice_id,),
    ).fetchone()
    if invoice is None:
        abort(404)
    return render_template("invoices/confirm_delete.html", invoice=invoice)


@bp.route("/<int:invoice_id>/delete", methods=["POST"])
def delete_invoice(invoice_id):
    db = get_db()
    invoice = db.execute("SELECT * FROM invoices WHERE id = ?", (invoice_id,)).fetchone()
    if invoice is None:
        abort(404)

    linked_doc = db.execute(
        "SELECT * FROM documents WHERE invoice_id = ?", (invoice_id,)
    ).fetchone()

    if linked_doc is not None:
        db.execute("DELETE FROM documents WHERE id = ?", (linked_doc["id"],))
    db.execute("DELETE FROM invoices WHERE id = ?", (invoice_id,))
    db.commit()

    if linked_doc is not None:
        file_path = config.DOCUMENTS_DIR / linked_doc["file_path"]
        if file_path.exists():
            file_path.unlink()

    flash(f"Инвойс {invoice['invoice_number']} удалён безвозвратно.", "success")
    return redirect(url_for("invoices.list_invoices"))


@bp.route("/<int:invoice_id>/status", methods=["POST"])
def change_status(invoice_id):
    new_status = request.form.get("status")
    if new_status not in ("paid", "cancelled", "issued"):
        abort(400)
    db = get_db()
    db.execute("UPDATE invoices SET status = ? WHERE id = ?", (new_status, invoice_id))
    db.commit()
    flash("Статус инвойса обновлён.", "success")
    return redirect(url_for("invoices.view_invoice", invoice_id=invoice_id))


@bp.route("/new", methods=["GET", "POST"])
def new_invoice():
    db = get_db()
    clients = db.execute(
        "SELECT * FROM clients WHERE is_active = 1 ORDER BY name COLLATE NOCASE"
    ).fetchall()
    contracts = db.execute(
        "SELECT documents.id, documents.title, clients.name AS client_name "
        "FROM documents LEFT JOIN clients ON clients.id = documents.client_id "
        "WHERE documents.category = 'contract' ORDER BY documents.title"
    ).fetchall()
    past_descriptions = _past_descriptions(db)

    if request.method == "POST":
        form = request.form
        client_id = form.get("client_id")
        currency = form.get("currency", "EUR")
        amount_raw = form.get("amount", "").strip()
        issue_date = form.get("issue_date") or date.today().isoformat()
        service_date = form.get("service_date") or None
        due_date = form.get("due_date") or None
        description = form.get("description", "").strip()
        contract_document_id = form.get("contract_document_id") or None
        manual_rate = form.get("manual_rate", "").strip() or None

        errors = []
        if not client_id:
            errors.append("Выберите клиента.")
        if currency not in config.SUPPORTED_CURRENCIES:
            errors.append("Недопустимая валюта.")
        try:
            amount = float(amount_raw)
            if amount <= 0:
                errors.append("Сумма должна быть больше нуля.")
        except ValueError:
            amount = None
            errors.append("Некорректная сумма.")
        if not description:
            errors.append("Укажите описание услуги.")

        rate_info = None
        if not errors:
            rate_info = exchange_rates.get_rate(db, currency, issue_date, manual_rate)
            if rate_info is None:
                errors.append(
                    f"Курс {currency}→RSD на {issue_date} не найден. "
                    "Введите курс вручную ниже."
                )

        if errors:
            for e in errors:
                flash(e, "error")
            return render_template(
                "invoices/form.html",
                clients=clients,
                contracts=contracts,
                currencies=config.SUPPORTED_CURRENCIES,
                form=form,
                need_manual_rate=True,
                past_descriptions=past_descriptions,
            )

        if rate_info.get("fallback"):
            flash(
                f"Курс на {issue_date} не найден, использован курс за "
                f"{rate_info['date']}. Проверьте вручную при необходимости.",
                "warning",
            )

        amount_rsd = round(amount * rate_info["rate"], 2)
        year = int(issue_date[:4])
        fmt = settings_store.get("invoice_number_format")
        invoice_number = invoice_numbering.next_number(db, issue_date, fmt)

        cur = db.execute(
            "INSERT INTO invoices (invoice_number, client_id, issue_date, service_date, "
            "due_date, currency, amount, description, exchange_rate, exchange_rate_date, "
            "exchange_rate_source, amount_rsd, contract_document_id, status) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 'issued')",
            (
                invoice_number,
                client_id,
                issue_date,
                service_date,
                due_date,
                currency,
                amount,
                description,
                rate_info["rate"],
                rate_info["date"],
                rate_info["source"],
                amount_rsd,
                contract_document_id,
            ),
        )
        invoice_id = cur.lastrowid
        db.commit()

        client = db.execute("SELECT * FROM clients WHERE id = ?", (client_id,)).fetchone()
        settings_values = settings_store.get_all()

        pdf_filename = f"invoice_{invoice_number.replace('/', '-')}.pdf"
        output_path = config.DOCUMENTS_DIR / "invoice" / str(year) / pdf_filename
        pdf_generator.generate_invoice_pdf(
            {
                "invoice": {
                    "invoice_number": invoice_number,
                    "issue_date": issue_date,
                    "service_date": service_date,
                    "due_date": due_date,
                    "currency": currency,
                    "amount": amount,
                    "description": description,
                    "amount_rsd": amount_rsd,
                },
                "client": client,
                "settings": settings_values,
            },
            output_path,
        )
        relative_path = f"invoice/{year}/{pdf_filename}"
        db.execute(
            "UPDATE invoices SET pdf_path = ? WHERE id = ?", (relative_path, invoice_id)
        )
        create_invoice_document(
            db, invoice_id, client_id, year, f"Инвойс {invoice_number}",
            relative_path, pdf_filename,
        )
        db.commit()

        flash(f"Инвойс {invoice_number} создан.", "success")
        return redirect(url_for("invoices.view_invoice", invoice_id=invoice_id))

    return render_template(
        "invoices/form.html",
        clients=clients,
        contracts=contracts,
        currencies=config.SUPPORTED_CURRENCIES,
        form={},
        need_manual_rate=False,
        past_descriptions=past_descriptions,
    )


@bp.route("/import", methods=["GET", "POST"])
def import_invoice():
    db = get_db()
    clients = db.execute(
        "SELECT * FROM clients WHERE is_active = 1 ORDER BY name COLLATE NOCASE"
    ).fetchall()
    contracts = db.execute(
        "SELECT documents.id, documents.title, clients.name AS client_name "
        "FROM documents LEFT JOIN clients ON clients.id = documents.client_id "
        "WHERE documents.category = 'contract' ORDER BY documents.title"
    ).fetchall()
    past_descriptions = _past_descriptions(db)

    if request.method == "POST":
        form = request.form
        client_id = form.get("client_id")
        invoice_number = form.get("invoice_number", "").strip()
        currency = form.get("currency", "EUR")
        amount_raw = form.get("amount", "").strip()
        issue_date = form.get("issue_date") or date.today().isoformat()
        service_date = form.get("service_date") or None
        due_date = form.get("due_date") or None
        description = form.get("description", "").strip()
        status = form.get("status", "issued")
        contract_document_id = form.get("contract_document_id") or None
        manual_rate = form.get("manual_rate", "").strip() or None
        file = request.files.get("file")

        errors = []
        if not client_id:
            errors.append("Выберите клиента.")
        if not invoice_number:
            errors.append("Укажите номер счёта (как на оригинальном PDF).")
        elif db.execute(
            "SELECT id FROM invoices WHERE invoice_number = ?", (invoice_number,)
        ).fetchone():
            errors.append(f"Инвойс с номером {invoice_number} уже есть в системе.")
        if currency not in config.SUPPORTED_CURRENCIES:
            errors.append("Недопустимая валюта.")
        try:
            amount = float(amount_raw)
            if amount <= 0:
                errors.append("Сумма должна быть больше нуля.")
        except ValueError:
            amount = None
            errors.append("Некорректная сумма.")
        if not description:
            errors.append("Укажите описание услуги.")
        if status not in ("issued", "paid"):
            errors.append("Недопустимый статус.")
        if not file or file.filename == "":
            errors.append("Прикрепите PDF существующего счёта.")

        rate_info = None
        if not errors:
            rate_info = exchange_rates.get_rate(db, currency, issue_date, manual_rate)
            if rate_info is None:
                errors.append(
                    f"Курс {currency}→RSD на {issue_date} не найден. "
                    "Введите курс вручную ниже."
                )

        if errors:
            for e in errors:
                flash(e, "error")
            return render_template(
                "invoices/import_form.html",
                clients=clients,
                contracts=contracts,
                currencies=config.SUPPORTED_CURRENCIES,
                form=form,
                need_manual_rate=True,
                past_descriptions=past_descriptions,
            )

        if rate_info.get("fallback"):
            flash(
                f"Курс на {issue_date} не найден, использован курс за "
                f"{rate_info['date']}. Проверьте вручную при необходимости.",
                "warning",
            )

        amount_rsd = round(amount * rate_info["rate"], 2)
        year = int(issue_date[:4])

        cur = db.execute(
            "INSERT INTO invoices (invoice_number, client_id, issue_date, service_date, "
            "due_date, currency, amount, description, exchange_rate, exchange_rate_date, "
            "exchange_rate_source, amount_rsd, contract_document_id, status) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (
                invoice_number, client_id, issue_date, service_date, due_date,
                currency, amount, description, rate_info["rate"], rate_info["date"],
                rate_info["source"], amount_rsd, contract_document_id, status,
            ),
        )
        invoice_id = cur.lastrowid

        original_filename = file.filename
        ext = "".join(re.findall(r"\.[A-Za-z0-9]+$", original_filename)) or ".pdf"
        safe_stub = secure_filename(f"invoice_{invoice_number.replace('/', '-')}") or f"invoice_{invoice_id}"
        pdf_filename = f"{safe_stub}{ext}"
        output_dir = config.DOCUMENTS_DIR / "invoice" / str(year)
        output_dir.mkdir(parents=True, exist_ok=True)
        file.save(output_dir / pdf_filename)
        relative_path = f"invoice/{year}/{pdf_filename}"

        db.execute(
            "UPDATE invoices SET pdf_path = ? WHERE id = ?", (relative_path, invoice_id)
        )
        create_invoice_document(
            db, invoice_id, client_id, year, f"Инвойс {invoice_number}",
            relative_path, original_filename,
        )

        # Keep future auto-generated numbers from colliding with this imported one.
        seq_match = re.match(r"^(\d+)", invoice_number)
        if seq_match:
            imported_seq = int(seq_match.group(1))
            row = db.execute(
                "SELECT next_seq FROM invoice_sequences WHERE year = ?", (year,)
            ).fetchone()
            if row is None:
                db.execute(
                    "INSERT INTO invoice_sequences (year, next_seq) VALUES (?, ?)",
                    (year, imported_seq + 1),
                )
            elif row["next_seq"] <= imported_seq:
                db.execute(
                    "UPDATE invoice_sequences SET next_seq = ? WHERE year = ?",
                    (imported_seq + 1, year),
                )

        db.commit()

        flash(f"Инвойс {invoice_number} импортирован.", "success")
        return redirect(url_for("invoices.view_invoice", invoice_id=invoice_id))

    return render_template(
        "invoices/import_form.html",
        clients=clients,
        contracts=contracts,
        currencies=config.SUPPORTED_CURRENCIES,
        form={},
        need_manual_rate=False,
        past_descriptions=past_descriptions,
    )
