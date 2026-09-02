# Paušaljivac

A local Flask + SQLite web app for managing the business admin of a **paušalac** — a
flat-rate-taxed sole proprietor (preduzetnik) in Serbia (*paušalno oporezivanje*).

It tracks clients, invoices to foreign clients, documents (tax rešenja, contracts, bank
reports, misc), the two paušal income-limit thresholds, tax payment reminders, KPO knjiga
generation, and filling/signing the bank's "Obaveštenje o prilivu" form for foreign
currency inflows.

This is a single-user, local-only tool — it has no authentication and is meant to run on
`localhost`, not be exposed to a network. Each person runs their own copy with their own
data; it's not something you'd host centrally for a group.

## Just want to run it? (Windows / macOS)

Grab the latest build from the [Releases](../../releases) page — `Pausaljivac-windows.zip`
or `Pausaljivac-macos.zip` — unzip it, and run `Pausaljivac.exe` (Windows) or
`Pausaljivac.app` (macOS). No Python install needed. It opens `http://localhost:5000` in
your browser automatically.

> These builds are new and not heavily field-tested yet — if one doesn't start on your
> machine, please open an issue with what OS/version you're on and any error output (the
> Windows build keeps a console window open; on macOS run it from Terminal via
> `Pausaljivac.app/Contents/MacOS/Pausaljivac` to see output).

The rest of this section is for running from source (also how Linux/WSL2 users run it).

## Requirements

- Python 3.11+
- On Linux/WSL2, system libraries for [WeasyPrint](https://doc.courtbouillon.org/weasyprint/stable/first_steps.html#installation) (used for invoice PDF generation)

## Setup

```bash
python3 -m venv .venv
.venv/bin/pip install -r requirements.txt
```

> **WSL2 note:** if `python3 -m venv .venv` fails with a missing-ensurepip error,
> `python3-venv` isn't installed and you may not have passwordless sudo. Work around it with:
> ```bash
> python3 -m venv --without-pip .venv
> curl -sS https://bootstrap.pypa.io/get-pip.py | .venv/bin/python
> .venv/bin/pip install -r requirements.txt
> ```

## Running

```bash
.venv/bin/python app.py
```

or, on Windows with WSL2, double-click `run.bat` (starts the app inside WSL and opens
`http://localhost:5000` in the default browser).

The first run creates `data/` with a fresh, empty SQLite database (from `schema.sql`) and
the document-category folders — nothing needs to be seeded by hand. Everything under
`data/` (the database, uploaded/generated documents, logs, temp files) is git-ignored: it's
your own business and financial records, not part of the app.

Once it's running, open **Настройки / Settings** first and fill in your business details
(name, PIB, bank account, invoice numbering format, etc.) — invoices and the bank form use
those.

## Project layout

- `app.py` — app factory, logging setup, blueprint registration
- `config.py` — paths and constants (no secrets — nothing here needs an environment variable)
- `schema.sql` — SQLite schema, applied fresh on first run
- `blueprints/` — one module per feature area (clients, invoices, documents, tax, settings,
  bank-form filling, reports)
- `services/` — business logic used by the blueprints (PDF generation, exchange rates,
  invoice numbering, income-limit math, the bank-form PDF overlay)
- `templates/` / `static/` — Jinja2 templates and CSS

## Contributing

Bug reports, fixes, and PRs are welcome — see [CONTRIBUTING.md](CONTRIBUTING.md). Forking
for your own customized version needs no permission either.

## License

[MIT](LICENSE).
