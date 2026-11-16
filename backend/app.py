from flask import Flask, jsonify
from flask_cors import CORS

from config import CORS_ORIGINS, FLASK_DEBUG, FLASK_PORT
from database.connection import DatabaseConnectionError
from routes.auth import auth_bp


def register_blueprints(app):
    app.register_blueprint(auth_bp)


def create_app():
    app = Flask(__name__)
    origenes = "*" if CORS_ORIGINS == "*" else [o.strip() for o in CORS_ORIGINS.split(",")]
    CORS(app, resources={r"/api/*": {"origins": origenes}}, allow_headers=["Content-Type", "Authorization"])
    register_blueprints(app)

    @app.route("/api/health", methods=["GET"])
    def health():
        return jsonify({"status": "ok"})

    @app.errorhandler(DatabaseConnectionError)
    def database_unavailable(_error):
        return jsonify({"error": "Servicio de base de datos no disponible"}), 503

    @app.errorhandler(404)
    def not_found(_error):
        return jsonify({"error": "Recurso no encontrado"}), 404

    @app.errorhandler(405)
    def method_not_allowed(_error):
        return jsonify({"error": "Método no permitido"}), 405

    return app


app = create_app()


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=FLASK_PORT, debug=FLASK_DEBUG)
