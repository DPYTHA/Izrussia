from flask_sqlalchemy import SQLAlchemy
from datetime import datetime
from .extensions import db

db = SQLAlchemy()

class Cotisation(db.Model):
    __tablename__ = "cotisations"
    
    id = db.Column(db.Integer, primary_key=True)
    
    # Relation avec l'utilisateur
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False)
    
    # Montants envoyés et reçus
    montant_envoye = db.Column(db.Float, nullable=False)
    montant_recu = db.Column(db.Float, nullable=False)
    
    # Statut de la cotisation (ex: en_attente, validée, refusée)
    statut = db.Column(db.String(20), default="en_attente")
    
    # Date de la cotisation
    date_cotisation = db.Column(db.DateTime, default=datetime.utcnow)


    def to_dict(self):
        return {
            "id": self.id,
            "user_name": f"{self.user.first_name} {self.user.last_name}" if self.user else "-",
            "montant_envoye": self.montant_envoye,
            "montant_recu": self.montant_recu,
            "statut": self.statut,
            "date_cotisation": self.date_cotisation.strftime("%Y-%m-%d %H:%M:%S")
        }
