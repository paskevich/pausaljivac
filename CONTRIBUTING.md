# Contributing to Paušaljivac

Thanks for taking a look. This started as a personal tool for one Serbian
*paušalac* (flat-rate-taxed sole proprietor), so some defaults (currencies,
tax rules, the bank form) are specific to that use case — contributions that
make those configurable, or that fix bugs/improve the parts that are already
general-purpose, are very welcome.

## Getting set up

See the [README](README.md) for install/run instructions. In short:

```bash
python3 -m venv .venv
.venv/bin/pip install -r requirements.txt
.venv/bin/python app.py
```

The first run creates an empty `data/` (SQLite DB + document folders) from
`schema.sql` — you don't need any seed data to start developing.

## Making changes

- Keep PRs focused — one fix or feature per PR is easier to review than a
  bundle of unrelated changes.
- There's no automated test suite yet; at minimum, exercise the flow you
  touched through the running app before opening a PR, and mention what you
  checked in the PR description.
- Match the existing style: plain Flask blueprints + Jinja2 templates, no
  ORM, business logic in `services/`, no framework beyond what's already in
  `requirements.txt` unless there's a good reason.
- If you're changing something Serbia/paušal-specific (tax thresholds, the
  bank form, invoice numbering), link the source (law article, bank
  documentation) in the PR — those rules are easy to get subtly wrong.

## Reporting bugs / suggesting features

Open a GitHub issue. For bugs, include what you did, what you expected, and
what happened instead (screenshots help for anything PDF/layout-related).

## Forking for your own use

If you just want your own customized version rather than to contribute back,
forking is completely fine — no need to open an issue or ask first.
