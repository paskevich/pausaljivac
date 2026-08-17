import uuid

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

bp = Blueprint("documents", __name__, url_prefix="/documents")

CATEGORY_LABELS = {
    "resenje": "Решение налоговой",
    "contract": "Договор",
    "other": "Прочее",
    "invoice": "Инвойс",
    "bank_report": "Отчёт в банк",
}


@bp.route("/")
def list_documents():
    db = get_db()

    category = request.args.get("category", "")
    client_id = request.args.get("client_id", "")
    tag = request.args.get("tag", "")
    year = request.args.get("year", "")

    query = (
        "SELECT documents.*, clients.name AS client_name, "
        "GROUP_CONCAT(tags.name) AS tag_names "
        "FROM documents "
        "LEFT JOIN clients ON clients.id = documents.client_id "
        "LEFT JOIN document_tags ON document_tags.document_id = documents.id "
        "LEFT JOIN tags ON tags.id = document_tags.tag_id "
        "WHERE 1=1"
    )
    params = []

    if category:
        query += " AND documents.category = ?"
        params.append(category)
    if client_id:
        query += " AND documents.client_id = ?"
        params.append(client_id)
    if year:
        query += " AND documents.period_year = ?"
        params.append(year)
    if tag:
        query += (
            " AND documents.id IN (SELECT document_id FROM document_tags "
            "JOIN tags ON tags.id = document_tags.tag_id WHERE tags.name = ?)"
        )
        params.append(tag)

    query += " GROUP BY documents.id ORDER BY documents.uploaded_at DESC"

    documents = db.execute(query, params).fetchall()
    clients = db.execute("SELECT * FROM clients ORDER BY name COLLATE NOCASE").fetchall()
    all_tags = db.execute("SELECT name FROM tags ORDER BY name").fetchall()

    return render_template(
        "documents/list.html",
        documents=documents,
        clients=clients,
        all_tags=all_tags,
        categories=config.DOCUMENT_CATEGORIES,
        category_labels=CATEGORY_LABELS,
        filters={"category": category, "client_id": client_id, "tag": tag, "year": year},
    )


@bp.route("/upload", methods=["GET", "POST"])
def upload_document():
    db = get_db()
    if request.method == "POST":
        file = request.files.get("file")
        category = request.form.get("category", "other")
        title = request.form.get("title", "").strip()
        client_id = request.form.get("client_id") or None
        period_year = request.form.get("period_year") or None
        period_month = request.form.get("period_month") or None
        tags_raw = request.form.get("tags", "")
        notes = request.form.get("notes", "").strip()

        if category not in config.DOCUMENT_CATEGORIES or category == "invoice":
            flash("Недопустимая категория документа.", "error")
            return redirect(url_for("documents.upload_document"))

        if not file or file.filename == "":
            flash("Выберите файл для загрузки.", "error")
            return redirect(url_for("documents.upload_document"))

        document_id = save_uploaded_file(
            db, file, category, client_id=client_id, period_year=period_year,
            period_month=period_month, title=title, notes=notes,
        )
        _attach_tags(db, document_id, tags_raw)
        db.commit()

        flash("Документ загружен.", "success")
        return redirect(url_for("documents.list_documents"))

    clients = db.execute("SELECT * FROM clients ORDER BY name COLLATE NOCASE").fetchall()
    return render_template(
        "documents/upload_form.html",
        clients=clients,
        categories=[c for c in config.DOCUMENT_CATEGORIES if c != "invoice"],
        category_labels=CATEGORY_LABELS,
    )


@bp.route("/<int:document_id>/download")
def download_document(document_id):
    db = get_db()
    doc = db.execute("SELECT * FROM documents WHERE id = ?", (document_id,)).fetchone()
    if doc is None:
        abort(404)
    directory = config.DOCUMENTS_DIR
    return send_from_directory(
        directory, doc["file_path"], as_attachment=True,
        download_name=doc["original_filename"] or doc["title"],
    )


@bp.route("/<int:document_id>/delete", methods=["GET"])
def confirm_delete_document(document_id):
    db = get_db()
    doc = db.execute("SELECT * FROM documents WHERE id = ?", (document_id,)).fetchone()
    if doc is None:
        abort(404)
    linked_invoice = None
    if doc["category"] == "invoice" and doc["invoice_id"] is not None:
        linked_invoice = db.execute(
            "SELECT invoice_number FROM invoices WHERE id = ?", (doc["invoice_id"],)
        ).fetchone()
    return render_template(
        "documents/confirm_delete.html", doc=doc, linked_invoice=linked_invoice
    )


@bp.route("/<int:document_id>/delete", methods=["POST"])
def delete_document(document_id):
    db = get_db()
    doc = db.execute("SELECT * FROM documents WHERE id = ?", (document_id,)).fetchone()
    if doc is None:
        abort(404)

    if doc["category"] == "invoice" and doc["invoice_id"] is not None:
        db.execute(
            "UPDATE invoices SET pdf_path = NULL WHERE id = ?", (doc["invoice_id"],)
        )
        flash("PDF также откреплён от соответствующего инвойса.", "warning")

    linked_resenja = db.execute(
        "SELECT resenje_number FROM tax_resenja WHERE document_id = ?", (document_id,)
    ).fetchall()
    if linked_resenja:
        db.execute(
            "UPDATE tax_resenja SET document_id = NULL WHERE document_id = ?",
            (document_id,),
        )
        names = ", ".join(r["resenje_number"] or "без номера" for r in linked_resenja)
        flash(f"Документ также откреплён от решения(й): {names}.", "warning")

    db.execute("DELETE FROM documents WHERE id = ?", (document_id,))
    db.commit()

    file_path = config.DOCUMENTS_DIR / doc["file_path"]
    if file_path.exists():
        file_path.unlink()

    flash("Документ удалён.", "success")
    return redirect(url_for("documents.list_documents"))


PREVIEWABLE_IMAGE_TYPES = {"image/png", "image/jpeg", "image/gif", "image/webp"}
PREVIEWABLE_INLINE_TYPES = PREVIEWABLE_IMAGE_TYPES | {"application/pdf", "text/plain"}


@bp.route("/<int:document_id>/view")
def view_document(document_id):
    db = get_db()
    doc = db.execute(
        "SELECT documents.*, clients.name AS client_name FROM documents "
        "LEFT JOIN clients ON clients.id = documents.client_id "
        "WHERE documents.id = ?",
        (document_id,),
    ).fetchone()
    if doc is None:
        abort(404)

    mime_type = doc["mime_type"] or ""
    previewable = mime_type in PREVIEWABLE_INLINE_TYPES
    is_image = mime_type in PREVIEWABLE_IMAGE_TYPES

    return render_template(
        "documents/view.html",
        doc=doc,
        category_labels=CATEGORY_LABELS,
        previewable=previewable,
        is_image=is_image,
    )


@bp.route("/<int:document_id>/raw")
def raw_document(document_id):
    db = get_db()
    doc = db.execute("SELECT * FROM documents WHERE id = ?", (document_id,)).fetchone()
    if doc is None:
        abort(404)
    return send_from_directory(config.DOCUMENTS_DIR, doc["file_path"], as_attachment=False)


def save_uploaded_file(db, file, category, client_id=None, period_year=None,
                        period_month=None, title=None, notes=""):
    original_filename = file.filename
    if not title:
        title = original_filename
    safe_name = secure_filename(original_filename) or "file"
    stored_name = f"{uuid.uuid4().hex[:8]}__{safe_name}"

    target_dir = config.DOCUMENTS_DIR / category
    target_dir.mkdir(parents=True, exist_ok=True)
    file.save(target_dir / stored_name)

    relative_path = f"{category}/{stored_name}"

    cur = db.execute(
        "INSERT INTO documents (category, client_id, period_year, period_month, "
        "title, file_path, original_filename, mime_type, notes) "
        "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
        (
            category, client_id, period_year, period_month, title,
            relative_path, original_filename, file.mimetype, notes,
        ),
    )
    return cur.lastrowid


def create_invoice_document(db, invoice_id, client_id, period_year, title, relative_path, original_filename):
    db.execute(
        "INSERT INTO documents (category, client_id, invoice_id, period_year, "
        "title, file_path, original_filename, mime_type) "
        "VALUES ('invoice', ?, ?, ?, ?, ?, ?, 'application/pdf')",
        (client_id, invoice_id, period_year, title, relative_path, original_filename),
    )


def _attach_tags(db, document_id, tags_raw):
    names = [t.strip() for t in tags_raw.split(",") if t.strip()]
    for name in names:
        db.execute("INSERT OR IGNORE INTO tags (name) VALUES (?)", (name,))
        tag_row = db.execute("SELECT id FROM tags WHERE name = ?", (name,)).fetchone()
        db.execute(
            "INSERT OR IGNORE INTO document_tags (document_id, tag_id) VALUES (?, ?)",
            (document_id, tag_row["id"]),
        )
