from flask import Flask

import config
import database
from blueprints.dashboard import bp as dashboard_bp
from blueprints.clients import bp as clients_bp
from blueprints.invoices import bp as invoices_bp
from blueprints.documents import bp as documents_bp
from blueprints.tax import bp as tax_bp
from blueprints.settings import bp as settings_bp
from blueprints.inflow_form import bp as inflow_form_bp


def create_app():
    app = Flask(__name__)
    app.config["SECRET_KEY"] = config.SECRET_KEY
    app.config["MAX_CONTENT_LENGTH"] = config.MAX_CONTENT_LENGTH

    database.init_app(app)

    app.register_blueprint(dashboard_bp)
    app.register_blueprint(clients_bp)
    app.register_blueprint(invoices_bp)
    app.register_blueprint(documents_bp)
    app.register_blueprint(tax_bp)
    app.register_blueprint(settings_bp)
    app.register_blueprint(inflow_form_bp)

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
