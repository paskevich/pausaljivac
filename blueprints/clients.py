from flask import Blueprint, abort, flash, redirect, render_template, request, url_for

import config
from database import get_db

bp = Blueprint("clients", __name__, url_prefix="/clients")


@bp.route("/")
def list_clients():
    db = get_db()
    clients = db.execute(
        "SELECT * FROM clients ORDER BY is_active DESC, name COLLATE NOCASE"
    ).fetchall()
    return render_template("clients/list.html", clients=clients)


@bp.route("/new", methods=["GET", "POST"])
def new_client():
    if request.method == "POST":
        _save_client(None)
        return redirect(url_for("clients.list_clients"))
    return render_template(
        "clients/form.html", client=None, currencies=config.SUPPORTED_CURRENCIES
    )


@bp.route("/<int:client_id>/edit", methods=["GET", "POST"])
def edit_client(client_id):
    db = get_db()
    client = db.execute("SELECT * FROM clients WHERE id = ?", (client_id,)).fetchone()
    if client is None:
        abort(404)
    if request.method == "POST":
        _save_client(client_id)
        return redirect(url_for("clients.list_clients"))
    return render_template(
        "clients/form.html", client=client, currencies=config.SUPPORTED_CURRENCIES
    )


@bp.route("/<int:client_id>/toggle-active", methods=["POST"])
def toggle_active(client_id):
    db = get_db()
    client = db.execute("SELECT * FROM clients WHERE id = ?", (client_id,)).fetchone()
    if client is None:
        abort(404)
    db.execute(
        "UPDATE clients SET is_active = ? WHERE id = ?",
        (0 if client["is_active"] else 1, client_id),
    )
    db.commit()
    return redirect(url_for("clients.list_clients"))


def _save_client(client_id):
    name = request.form.get("name", "").strip()
    if not name:
        flash("Имя клиента обязательно.", "error")
        return

    fields = {
        "name": name,
        "country": request.form.get("country", "").strip(),
        "address": request.form.get("address", "").strip(),
        "email": request.form.get("email", "").strip(),
        "contact_person": request.form.get("contact_person", "").strip(),
        "default_currency": request.form.get("default_currency", "EUR"),
        "notes": request.form.get("notes", "").strip(),
    }

    db = get_db()
    if client_id is None:
        db.execute(
            "INSERT INTO clients (name, country, address, email, contact_person, "
            "default_currency, notes) VALUES (:name, :country, :address, :email, "
            ":contact_person, :default_currency, :notes)",
            fields,
        )
        flash("Клиент добавлен.", "success")
    else:
        fields["id"] = client_id
        db.execute(
            "UPDATE clients SET name=:name, country=:country, address=:address, "
            "email=:email, contact_person=:contact_person, "
            "default_currency=:default_currency, notes=:notes WHERE id=:id",
            fields,
        )
        flash("Клиент обновлён.", "success")
    db.commit()
