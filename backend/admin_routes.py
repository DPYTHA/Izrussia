# admin_routes.py
from flask import Blueprint, jsonify
from flask_jwt_extended import jwt_required, get_jwt_identity
from model import db, Cotisation  # ✅ importer depuis ton app principale, ne pas recréer SQLAlchemy()

admin_bp = Blueprint('admin', __name__)

@admin_bp.route('/api/admin/cotisation/<int:id>/<string:action>', methods=['POST'])
@jwt_required()
def admin_cotisation_action(id, action):
    admin_email = get_jwt_identity()
    cot = Cotisation.query.get(id)

    if not cot:
        return jsonify({"message": "Cotisation introuvable"}), 404

    if action == "approve":
        cot.statut = "approuvée"
        db.session.commit()
        return jsonify({"message": f"Cotisation #{id} approuvée avec succès"}), 200

    elif action == "confirm":
        cot.statut = "confirmée"
        db.session.commit()
        return jsonify({"message": f"Cotisation #{id} confirmée avec succès"}), 200

    elif action == "delete":
        db.session.delete(cot)
        db.session.commit()
        return jsonify({"message": f"Cotisation #{id} supprimée"}), 200

    else:
        return jsonify({"message": "Action invalide"}), 400
