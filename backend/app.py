from __future__ import annotations

from pathlib import Path
from flask import Flask, jsonify, render_template

from backend.api.search import bp as search_bp
from backend.api.signals import bp as signals_bp
from backend.api.onset import bp as onset_bp
from backend.api.outcomes import bp as outcomes_bp
from backend.api.trends import bp as trends_bp
from backend.api.filter_options import bp as filter_options_bp
from backend.api.geo_data import bp as geo_data_bp
from backend.db.mongo import get_client


def create_app() -> Flask:
    root = Path(__file__).resolve().parents[1]  # VAERS_Interactive/
    frontend_dir = root / "frontend"

    app = Flask(
        __name__,
        static_folder=str(frontend_dir / "static"),
        template_folder=str(frontend_dir / "templates"),
    )

    # UI
    @app.get("/")
    def home():
        return render_template("index.html")

    # API blueprints
    app.register_blueprint(search_bp)
    app.register_blueprint(signals_bp)
    app.register_blueprint(onset_bp)
    app.register_blueprint(outcomes_bp)
    app.register_blueprint(trends_bp)
    app.register_blueprint(filter_options_bp)
    app.register_blueprint(geo_data_bp)

    # Health
    @app.get("/health")
    def health():
        try:
            client = get_client()
            client.admin.command("ping")
            return jsonify({"ok": True})
        except Exception as e:
            return jsonify({"ok": False, "error": str(e)}), 500

    return app


if __name__ == "__main__":
    app = create_app()
    app.run(host="127.0.0.1", port=5000, debug=True)
