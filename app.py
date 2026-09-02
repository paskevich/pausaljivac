import logging
from logging.handlers import RotatingFileHandler

from flask import Flask, got_request_exception, request

import config
import database
from blueprints.dashboard import bp as dashboard_bp
from blueprints.clients import bp as clients_bp
from blueprints.invoices import bp as invoices_bp
from blueprints.documents import bp as documents_bp
from blueprints.tax import bp as tax_bp
from blueprints.settings import bp as settings_bp
from blueprints.inflow_form import bp as inflow_form_bp
from blueprints.reports import bp as reports_bp


def setup_logging(app):
    config.LOG_DIR.mkdir(parents=True, exist_ok=True)
    handler = RotatingFileHandler(config.LOG_PATH, maxBytes=1_000_000, backupCount=3, encoding="utf-8")
    handler.setFormatter(logging.Formatter(
        "%(asctime)s %(levelname)s %(name)s: %(message)s"
    ))
    handler.setLevel(logging.INFO)

    # Attach to the root logger, not app.logger: module loggers created via
    # logging.getLogger(__name__) in blueprints/services (e.g. "blueprints.
    # inflow_form") are children of root, not of "app", so a handler on
    # app.logger alone would miss everything they log.
    root_logger = logging.getLogger()
    root_logger.addHandler(handler)
    root_logger.setLevel(logging.INFO)

    # Flask's debug mode re-raises unhandled exceptions for the interactive
    # debugger instead of routing them through app.logger, so file logging
    # would otherwise miss them. got_request_exception fires unconditionally
    # before that re-raise, so hook it directly.
    def _log_unhandled_exception(sender, exception, **extra):
        sender.logger.error("Unhandled exception on %s", request.path, exc_info=exception)

    got_request_exception.connect(_log_unhandled_exception, app)


def create_app():
    app = Flask(__name__)
    app.config["SECRET_KEY"] = config.SECRET_KEY
    app.config["MAX_CONTENT_LENGTH"] = config.MAX_CONTENT_LENGTH

    setup_logging(app)
    database.init_app(app)

    app.register_blueprint(dashboard_bp)
    app.register_blueprint(clients_bp)
    app.register_blueprint(invoices_bp)
    app.register_blueprint(documents_bp)
    app.register_blueprint(tax_bp)
    app.register_blueprint(settings_bp)
    app.register_blueprint(inflow_form_bp)
    app.register_blueprint(reports_bp)

    @app.template_filter("money")
    def format_money(value, decimals=2):
        if value is None:
            return "—"
        return f"{value:,.{decimals}f}"

    return app


app = create_app()

if __name__ == "__main__":
    database.init_db()
    app.run(debug=True, port=5000)
