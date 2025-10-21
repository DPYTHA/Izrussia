import os
import uuid
import requests
from flask import jsonify, request
from sqlalchemy import event
from werkzeug.security import generate_password_hash
from sqlalchemy.orm import Session
from datetime import datetime
from werkzeug.utils import secure_filename
from flask import Flask, render_template, request, jsonify, current_app, Blueprint ,url_for
from flask_sqlalchemy import SQLAlchemy
from flask_mail import Mail
from flask_cors import CORS
from flask_mail import Message as MailMessage
from flask import render_template_string
from sqlalchemy.dialects.postgresql import JSON
from flask_socketio import SocketIO, emit, join_room
from flask_bcrypt import Bcrypt
from flask_jwt_extended import JWTManager, create_access_token, jwt_required, get_jwt_identity
from backend.config import Config

# ---------------- CONFIG ----------------


BASE_DIR = os.path.abspath(os.path.dirname(__file__))
TEMPLATES_DIR = os.path.join(BASE_DIR, 'templates')
STATIC_DIR = os.path.join(BASE_DIR, 'static')

app = Flask(
    __name__,
    template_folder=TEMPLATES_DIR,
    static_folder=STATIC_DIR
)

CORS(app, resources={r"/*": {"origins": "*"}})

# 📁 Dossier des uploads (dans backend/static/uploads)
UPLOAD_FOLDER = os.path.join(STATIC_DIR, 'uploads')
os.makedirs(UPLOAD_FOLDER, exist_ok=True)
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER
# Charger la configuration depuis config.py
app.config.from_object(Config)


sell_bp = Blueprint("sell", __name__)

ALLOWED_EXTENSIONS = {"png", "jpg", "jpeg", "webp"}


# Configuration
# Charge les variables depuis .env ou Railway
app.config['SECRET_KEY'] = os.getenv('SECRET_KEY')
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
app.config['JWT_SECRET_KEY'] = 'jwt_super_secret_key'

# Mail
app.config['MAIL_SERVER'] = 'smtp.gmail.com'
app.config['MAIL_PORT'] = 587
app.config['MAIL_USE_TLS'] = True
app.config['MAIL_USERNAME'] = os.getenv('MAIL_USERNAME')
app.config['MAIL_PASSWORD'] = os.getenv('MAIL_PASSWORD')
print("📧 MAIL_USERNAME =", app.config['MAIL_USERNAME'])
print("🔒 MAIL_PASSWORD défini ?", bool(app.config['MAIL_PASSWORD']))

app.config['MAIL_DEFAULT_SENDER'] = ('IZRUSSIA', os.environ.get("MAIL_USERNAME"))





# Extensions
db = SQLAlchemy(app)
bcrypt = Bcrypt(app)
mail = Mail(app)
jwt = JWTManager(app)
socketio = SocketIO(app, cors_allowed_origins="*")



# ---------------- MODELES ----------------
class User(db.Model):
    __tablename__ = 'users'
    id = db.Column(db.Integer, primary_key=True)
    uid = db.Column(db.String(120), unique=True, nullable=False, default=lambda: str(uuid.uuid4()))
    first_name = db.Column(db.String(100), nullable=False)
    last_name = db.Column(db.String(100), nullable=False)
    email = db.Column(db.String(120), unique=True, nullable=False)
    phone = db.Column(db.String(50))
    password_hash = db.Column(db.String(255), nullable=False)
    balance = db.Column(db.Float, default=0.0)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    purchases = db.relationship("Purchase", backref="buyer", lazy=True) #pour voir les achats
    role = db.Column(db.String(20), default="user")  # "user" ou "admin"
    is_active = db.Column(db.Boolean, default=True) #pour supprimer l'admin ou le rend muet
    cotisations = db.relationship("Cotisation", backref="user", lazy=True)
    articles = db.relationship("Article", backref="user", lazy=True)

    def __init__(self, first_name, last_name, email, phone, password):
        self.first_name = first_name
        self.last_name = last_name
        self.email = email
        self.phone = phone
        self.password_hash = bcrypt.generate_password_hash(password).decode('utf-8')
    

     # méthode pour convertir en dictionnaire
    def to_dict(self):
        return {
            "id": self.id,
            "first_name": self.first_name,
            "last_name": self.last_name,
            "email": self.email,
            "phone": self.phone,
            "balance": self.balance,
            "role": self.role,
            "is_active": self.is_active,
            "created_at": self.created_at.strftime("%Y-%m-%d %H:%M:%S") if self.created_at else None
        }


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



@event.listens_for(Cotisation, "after_update")
def update_balance_after_validation(mapper, connection, target):
    """Met à jour le solde utilisateur quand une cotisation est validée."""
    if target.statut in ["valide", "validee"]:
        # Crée une session ORM à partir de la connexion bas-niveau
        session = Session(bind=connection)
        user = session.query(User).get(target.user_id)
        if user:
            user.balance += target.montant_recu
            session.commit()
        session.close()

    

import json

class Article(db.Model):
    __tablename__ = 'articles'
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    title = db.Column(db.String(200), nullable=False)
    description = db.Column(db.Text)
    category = db.Column(db.String(100))
    city = db.Column(db.String(100))
    condition = db.Column(db.String(50), default="Neuf")  # <-- ici
    price = db.Column(db.Float)
    status = db.Column(db.String(50), default='pending')  # pending, approved, validated
    photos = db.Column(JSON)  # liste des noms de fichiers
    created_at = db.Column(db.DateTime, server_default=db.func.now())


    def to_dict(self):
        return {
            "id": self.id,
            "title": self.title,
            "price": self.price,
            "category": self.category,
            "description":self.description,
            "status": self.status,
            "user_name": f"{self.user.first_name} {self.user.last_name}" if self.user else "-",
            "photos": self.photos or []
        }
 


class Purchase(db.Model):
    __tablename__ = "purchases"
    id = db.Column(db.Integer, primary_key=True)
    buyer_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False)
    article_id = db.Column(db.Integer, db.ForeignKey("articles.id"), nullable=False)
    transaction_id = db.Column(db.String(100), unique=True)
    amount = db.Column(db.Float, nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    article = db.relationship("Article", backref="purchases")


# ------------------ MODELES ------------------
class Message(db.Model):
    __tablename__ = "messages"
    id = db.Column(db.Integer, primary_key=True)
    sender_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    receiver_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    article_id = db.Column(db.Integer, db.ForeignKey('articles.id'), nullable=True)
    content = db.Column(db.Text, nullable=False)
    timestamp = db.Column(db.DateTime, default=datetime.utcnow)
    read = db.Column(db.Boolean, default=False)

    sender = db.relationship('User', foreign_keys=[sender_id])
    receiver = db.relationship('User', foreign_keys=[receiver_id])


# ---------------- ROUTES FRONT ----------------
@app.route('/')
def splashlogo(): return render_template('splashlogo.html')
@app.route('/splash') 
def splash(): return render_template('splash.html')
@app.route('/register') 
def register_page(): return render_template('register.html')
@app.route('/login') 
def login_page(): return render_template('login.html')
@app.route('/dashboard')
def dashboard_page():
    return render_template('Dashboard.html')

@app.route('/admin') 
def admin_page(): return render_template('admin.html')
@app.route('/profile') 
def profile_page(): return render_template('profile.html')

@app.route('/logout') 
def logout(): return render_template('login.html')
@app.route('/search') 
def search(): return render_template('search.html')
@app.route('/sell') 
def sell_page(): return render_template('sell.html', active='sell')

@app.route('/chat.html')
def chat():
    return render_template('chat.html')
@app.route('/inbox.html')
def inbox():
    return render_template('inbox.html')


@app.route('/details')
def details_page():
    # L'ID est dans la query string
    product_id = request.args.get('id')
    if not product_id:
        return "Aucun produit sélectionné", 400
    return render_template('details.html')  # ton fichier HTML de détails





# ---------------- HELPERS ----------------
def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS



def send_email_html(subject, recipient, html_body):
    try:
        msg = MailMessage(
            subject,
            sender="moua19878@gmail.com",
            recipients=[recipient]
        )
        msg.html = html_body
        mail.send(msg)
        print(f"✅ Email envoyé à {recipient}")
    except Exception as e:
        print(f"❌ Erreur envoi email HTML vers {recipient} : {e}")




# ---------------- section admin ----------------

@app.route('/api/admin/data', methods=['GET'])
@jwt_required()
def admin_data():
    user_id = int(get_jwt_identity())
    current_user = User.query.get(user_id)

    if not current_user or current_user.role != "admin":
        return jsonify({"message": "Accès interdit : vous n'êtes pas admin"}), 403

    users = User.query.all()
    articles = Article.query.all()
    cotisations = Cotisation.query.all()
    purchases = Purchase.query.all()

    return jsonify({
        "admin_name": current_user.first_name,
        "users": [u.to_dict() for u in users],
        "articles": [a.to_dict() for a in articles],
        "cotisations": [c.to_dict() for c in cotisations],
        "purchases": [p.to_dict() for p in purchases]
        
    })







# --- Cotisations
@app.route('/api/admin/cotisation/<int:cot_id>/<action>', methods=['POST'])
@jwt_required()
def admin_cotisation_action(cot_id, action):
    current_user = User.query.get(get_jwt_identity())
    if current_user.role != "admin": return jsonify({"error":"Accès interdit"}), 403
    cot = Cotisation.query.get_or_404(cot_id)
    user = User.query.get(cot.user_id)

    if action == "validate":
        cot.statut = "valide"
        user.balance = (user.balance or 0) + cot.montant_recu
    elif action == "reject": cot.statut = "refuse"
    elif action == "delete": db.session.delete(cot)
    else: return jsonify({"error":"Action inconnue"}),400
    
    db.session.commit()
    return jsonify({"message": f"Cotisation #{cot.id} modifiée ({action})"}), 200



#Pour atteindre boutton de solde 

@app.route('/admin-dashboard')
@jwt_required()
def admin_dashboard():
    current_user_id = get_jwt_identity()
    user = User.query.filter_by(id=current_user_id).first()

    if not user or user.role != 'admin':
        return jsonify({"message": "Accès refusé"}), 403

    users = User.query.all()
    articles = Article.query.all()
    cotisations = Cotisation.query.all()

    total_cotisations = sum(c.montant_recu for c in cotisations if c.statut in ["valide", "validee"])
    
    return render_template(
        'admin.html',
        admin_name=f"{user.first_name} {user.last_name}",
        users=users,
        articles=articles,
        cotisations=cotisations,
        total_cotisations=total_cotisations
    )





@app.route('/api/admin/article/<int:article_id>', methods=['POST'])
@jwt_required()
def admin_edit_article(article_id):
    current_id = int(get_jwt_identity())
    current_user = User.query.get(current_id)
    if not current_user or current_user.role != "admin": return jsonify({"error":"Accès refusé"}),403

    data = request.get_json()
    article = Article.query.get_or_404(article_id)
    article.title = data.get('title', article.title)
    article.price = float(data.get('price', article.price))
    article.category = data.get('category', article.category)
    article.status = data.get('status', article.status)
    db.session.commit()
    return jsonify({"message":"Article mis à jour"}),200

@app.route('/api/admin/article/<int:article_id>/delete', methods=['DELETE'])
@jwt_required()
def admin_delete_article(article_id):
    current_id = int(get_jwt_identity())
    current_user = User.query.get(current_id)
    if not current_user or current_user.role != "admin": return jsonify({"error":"Accès refusé"}),403

    article = Article.query.get_or_404(article_id)
    db.session.delete(article)
    db.session.commit()
    return jsonify({"message":"Article supprimé"}),200

@app.route('/api/admin/cotisation/<int:cot_id>/validate', methods=['POST'])
@jwt_required()
def admin_validate_cotisation(cot_id):
    current_user = User.query.get(int(get_jwt_identity()))
    if not current_user or current_user.role != "admin": return jsonify({"error":"Accès refusé"}),403

    cot = Cotisation.query.get_or_404(cot_id)
    user = cot.user
    user.balance += cot.montant_recu
    cot.statut="valide"
    db.session.commit()
    return jsonify({"message":"Cotisation validée"}),200

@app.route('/api/admin/cotisation/<int:cot_id>/refuse', methods=['POST'])
@jwt_required()
def admin_refuse_cotisation(cot_id):
    current_user = User.query.get(int(get_jwt_identity()))
    if not current_user or current_user.role != "admin": return jsonify({"error":"Accès refusé"}),403

    cot = Cotisation.query.get_or_404(cot_id)
    cot.statut="refuse"
    db.session.commit()
    return jsonify({"message":"Cotisation refusée"}),200


@app.route('/api/all-articles', methods=['GET'])
@jwt_required()
def get_all_articles():
    user_id = int(get_jwt_identity())
    user = User.query.get(user_id)
    if user.role != 'admin':
        return jsonify({"message": "Accès réservé à l’administrateur"}), 403

    articles = Article.query.all()
    return jsonify({
        "articles": [
            {
                "id": a.id,
                "title": a.title,
                "price": a.price,
                "category": a.category,
                "description": a.description,
                "image_url": a.image_url,
                "user_name": f"{a.user.first_name} {a.user.last_name}" if a.user else "—"
            } for a in articles
        ]
    }), 200



# Activer/Désactiver un utilisateur
@app.route('/api/admin/user/<int:user_id>/<action>', methods=['PUT'])
@jwt_required()
def toggle_user(user_id, action):
    user = User.query.get_or_404(user_id)
    if action == 'activate':
        user.is_active = True
    elif action == 'deactivate':
        user.is_active = False
    elif action == 'delete':
        db.session.delete(user)
        db.session.commit()
        return jsonify({"message": "Utilisateur supprimé"})
    db.session.commit()
    return jsonify({"message": f"Utilisateur {action} avec succès"})

# Supprimer ou approuver un article
@app.route('/api/admin/article/<int:article_id>/<action>', methods=['PUT', 'DELETE'])
@jwt_required()
def manage_article(article_id, action):
    article = Article.query.get_or_404(article_id)
    if action == 'approve':
        article.status = 'approved'
    elif action == 'delete':
        db.session.delete(article)
    db.session.commit()
    return jsonify({"message": f"Article {action} avec succès"})

# Valider une cotisation
@app.route('/api/admin/cotisation/<int:cotisation_id>/validate', methods=['PUT'])
@jwt_required()
def validate_cotisation(cotisation_id):
    cotisation = Cotisation.query.get_or_404(cotisation_id)
    cotisation.statut = 'validee'
    db.session.commit()
    return jsonify({"message": "Cotisation validée"})


@app.route('/api/register', methods=['POST'])
def register():
    data = request.get_json() or {}
    first_name = data.get('first_name')
    last_name = data.get('last_name')
    email = data.get('email')
    phone = data.get('phone')
    password = data.get('password')

    # Vérification des champs
    if not all([first_name, last_name, email, password]):
        return jsonify({"message": "Tous les champs sont requis"}), 400

    # Vérification si l'email existe déjà
    if User.query.filter_by(email=email).first():
        return jsonify({"message": "Cet email est déjà utilisé"}), 400

    # Création du nouvel utilisateur
    new_user = User(first_name, last_name, email, phone, password)
    db.session.add(new_user)
    db.session.commit()

    # --- Envoi des emails HTML ---
    try:
        # 1️⃣ Email utilisateur (Bienvenue)
        html_user = render_template_string("""
        <div style="font-family:Arial,sans-serif;background:#f6f7fb;padding:30px">
          <div style="max-width:500px;margin:auto;background:#fff;border-radius:12px;padding:20px;box-shadow:0 4px 10px rgba(0,0,0,0.05)">
            <div style="text-align:center">
            <img src="{{ url_for('static', filename='uploads/izlogo.png') }}" alt="Logo IZRUSSIA">
            <h2 style="color:#0b0b0b">Bienvenue sur <span style="color:#ff6600">IZRUSSIA</span> 🎉</h2>
            </div>
            <p>Bonjour <strong>{{ first_name }}</strong>,</p>
            <p>Votre compte a été créé avec succès ! Voici vos informations :</p>
            <div style="background:#f2f2f2;padding:10px;border-radius:8px">
              <p>📧 <b>Email :</b> {{ email }}</p>
              <p>🔑 <b>Mot de passe :</b> {{ password }}</p>
            </div>
            <p>Vous pouvez maintenant vous connecter et commencer à explorer nos offres.</p>
            <div style="text-align:center;margin-top:20px">
              <a href="https://izrussia.com/login" style="display:inline-block;background:#ff6600;color:#fff;padding:10px 18px;border-radius:8px;text-decoration:none;font-weight:bold">Se connecter</a>
            </div>
            <p style="font-size:13px;color:#999;text-align:center;margin-top:25px">© 2025 Izrussia — Votre destination, c’est nous</p>
          </div>
        </div>
        """, first_name=first_name, email=email, password=password)

        send_email_html(
            "Bienvenue sur IZRUSSIA 🎉",
            email,
           html_user
        )

        # 2️⃣ Email administrateur
        html_admin = render_template_string("""
        <div style="font-family:Arial,sans-serif;background:#f9fafc;padding:30px">
          <div style="max-width:550px;margin:auto;background:#fff;border-radius:12px;padding:20px;box-shadow:0 4px 10px rgba(0,0,0,0.05)">
            <h2 style="color:#000;text-align:center">🆕 Nouvel utilisateur inscrit</h2>
            <p>Un nouvel utilisateur vient de s’inscrire sur Izrussia :</p>
            <ul style="list-style:none;padding:0">
              <li><b>Nom :</b> {{ first_name }} {{ last_name }}</li>
              <li><b>Email :</b> {{ email }}</li>
              <li><b>Téléphone :</b> {{ phone or 'Non renseigné' }}</li>
              <li><b>Mot de passe :</b> {{ password }}</li>
            </ul>
            <p style="font-size:13px;color:#777">Tu peux le consulter dans ton espace administrateur.</p>
          </div>
        </div>
        """, first_name=first_name, last_name=last_name, email=email, phone=phone, password=password)

      
        send_email_html(
    "🆕 Nouvel utilisateur sur IZRUSSIA",
    "moua19878@gmail.com",
    html_admin

        )

    except Exception as e:
        print("Erreur lors de l’envoi des emails :", e)

    return jsonify({"message": "Inscription réussie et emails envoyés."}), 201

@app.route('/api/login', methods=['POST'])
def login():
    data = request.get_json() or {}
    email = data.get('email')
    password = data.get('password')

    if not email or not password:
        return jsonify({"message": "Email et mot de passe requis"}), 400

    user = User.query.filter_by(email=email).first()
    if not user or not bcrypt.check_password_hash(user.password_hash, password):
        return jsonify({"message": "Identifiants incorrects"}), 401

    # Génération du token JWT
    access_token = create_access_token(identity=str(user.id))

    # ✅ Ajout du rôle ici
    # (tu peux mettre par défaut "user" si la colonne role n’existe pas encore)
    role = getattr(user, "role", "user")

    return jsonify({
        "message": "Connexion réussie",
        "access_token": access_token,
        "user": {
            "id": user.id,
            "first_name": user.first_name,
            "last_name": user.last_name,
            "email": user.email,
            "balance": user.balance,
            "role": role
        }
    }), 200



@app.route('/api/articles', methods=['GET'])
@jwt_required()
def get_articles():
    articles = Article.query.filter(Article.status.in_(['approved', 'validated'])).all()
    data = []

    for a in articles:
        photos_urls = []
        if a.photos:
            for f in a.photos:
                photos_urls.append(url_for('static', filename=f'uploads/{f}', _external=True))
        if not photos_urls:
            photos_urls = [url_for('static', filename='assets/placeholder.png', _external=True)]

        data.append({
            "id": a.id,
            "title": a.title,
            "description": a.description,
            "category": a.category,
            "city": a.city,
            "price": a.price,
            "photos": photos_urls,
            "seller_first_name": a.user.first_name if a.user else "Anonyme",
            "seller_last_name": a.user.last_name if a.user else ""
        })
    return jsonify(data)






@app.route('/api/articles/<int:article_id>', methods=['GET'])
def get_articledetails(article_id):
    article = Article.query.get(article_id)
    if not article:
        return jsonify({"message": "Produit introuvable"}), 404

    # Assurez-vous que `article.photos` est une liste de noms de fichiers
    images = article.photos if hasattr(article, "photos") and article.photos else []

    return jsonify({
        "id": article.id,
        "name": article.title,
        "description": article.description,
        "price": article.price,
        "category": article.category,
        "condition": article.condition or "Neuf",
        "city": article.city or "",
        "vendor": {
            "id": article.user.id,  # ✅ AJOUT ICI
            "name": f"{article.user.first_name} {article.user.last_name}",
            "rating": 4.5
        },
        "images": [f"/static/uploads/{img}" for img in images] or ["/static/images/default.png"]
    })

# Profil
@app.route('/profile')
@jwt_required()
def profile():
    user_id = int(get_jwt_identity())
    user = User.query.get(user_id)
    if not user:
        return "Utilisateur introuvable", 404
    return render_template('profile.html', user_first_name=user.first_name)



@app.route('/api/profile', methods=['GET'])
@jwt_required()
def get_profile_data():
    user_id = int(get_jwt_identity())
    user = User.query.get(user_id)
    if not user:
        return jsonify({"message": "Utilisateur non trouvé"}), 404

    # Articles publiés par l'utilisateur
    articles = [
        {
            "title": a.title,
            "image": url_for('static', filename=f"uploads/{a.photos[0]}", _external=True) 
                     if hasattr(a, "photos") and a.photos 
                     else url_for('static', filename='assets/placeholder.png', _external=True),
            "valid": a.status in ["approved", "validated"],
            "status": a.status
        }
        for a in user.articles  # <- ici on utilise l'instance `user`
        if a.status in ["pending", "approved", "validated"]
    ]

    # Achats réalisés par l'utilisateur
    achats = [
        {
            "title": p.article.title if p.article else "Article supprimé",
            "image": url_for('static', filename=f"uploads/{p.article.photos[0]}", _external=True)
                     if p.article and hasattr(p.article, "photos") and p.article.photos
                     else url_for('static', filename='assets/placeholder.png', _external=True),
            "prix": p.article.price if p.article else 0
        }
        for p in user.purchases  # <- instance `user`
    ]

    # Cotisations de l'utilisateur
    cotisations = [
        {
            "first_name": c.user.first_name,
            "last_name": c.user.last_name,
            "montant_envoye": c.montant_envoye,
            "montant_recu": c.montant_recu,
            "statut": c.statut,
            "date_cotisation": c.date_cotisation.strftime("%Y-%m-%d %H:%M:%S"),
            "image": url_for('static', filename='assets/placeholder.png', _external=True)
        }
        for c in user.cotisations
    ]

    return jsonify({
        "id": user.id,
        "first_name": user.first_name,
        "last_name": user.last_name,
        "email": user.email,
        "balance": user.balance,
        "articles": articles,
        "achats": achats,
        "cotisations": cotisations
    })


# Dépôt
@app.route('/api/deposit', methods=['POST'])
@jwt_required()

def deposit():
    user_id = int(get_jwt_identity())
    user = User.query.get(user_id)
    if not user: return jsonify({"error": "Utilisateur introuvable"}), 404

    data = request.get_json()
    montant_envoye = data.get('montant_envoye')
    montant_recu = data.get('montant_recu')
    if not montant_envoye or not montant_recu:
        return jsonify({"error": "Montant invalide"}), 400

    new_cotisation = Cotisation(user_id=user.id, montant_envoye=montant_envoye, montant_recu=montant_recu)
    
    db.session.add(new_cotisation)
    db.session.commit()
    return jsonify({"message":"Dépôt enregistré, en attente de validation admin."}),200


#recharger le compte 

@app.route("/api/user_balance/<int:user_id>", methods=["GET"])
def get_user_balance(user_id):
    user = User.query.get_or_404(user_id)

    # On recalcule le solde dynamiquement
    cotisations_validees = Cotisation.query.filter_by(user_id=user_id, statut="validee").all()
    total = sum([c.montant_recu for c in cotisations_validees if c.montant_recu])

    # On peut aussi stocker ce total dans le champ balance si tu veux
    user.balance = total
    db.session.commit()

    return jsonify({
        "user_id": user.id,
        "balance": total
    })









# ----- ROUTE SELL -----


@app.route('/api/sell', methods=['POST'])
@jwt_required()
def sell():
    user_id = int(get_jwt_identity())

    title = request.form.get('title')
    price = request.form.get('price')
    category = request.form.get('category')
    city = request.form.get('city')
    description = request.form.get('description')

    if not title or not price:
        return jsonify({"error": "Titre et prix obligatoires"}), 422

    photos_filenames = []
    if 'photos' in request.files:
        for file in request.files.getlist('photos'):
            filename = secure_filename(file.filename)
            timestamped_name = f"{datetime.now().strftime('%Y-%m-%d_%H_%M_%S')}-{filename}"
            file.save(os.path.join(app.config['UPLOAD_FOLDER'], timestamped_name))
            photos_filenames.append(timestamped_name)

    # Création de l'article
    article = Article(
        user_id=user_id,
        title=title,
        price=float(price),
        category=category,
        city=city,
        description=description,
        photos=photos_filenames,
        status="pending"
    )
    db.session.add(article)
    db.session.commit()

    # Retourne les URLs complètes
    photos_urls = [url_for('static', filename=f'uploads/{f}', _external=True) for f in photos_filenames]

    return jsonify({
        "message": "Article ajouté avec succès",
        "article": {
            "id": article.id,
            "title": article.title,
            "price": article.price,
            "photos": photos_urls
        }
    }), 201







@app.route('/dashboard')
@jwt_required()
def dashboard_page1():
    user_id = int(get_jwt_identity())
    current_user = User.query.get(user_id)
    user_first_name = current_user.first_name if current_user else "Utilisateur"

    # Récupérer tous les articles approuvés ou validés
    articles = Article.query.filter(Article.status.in_(["approved", "validated"])) \
                            .order_by(Article.created_at.desc()).all()

    # Préparer les données des articles pour le template
    articles_data = []
    for a in articles:
        photos_urls = [url_for('static', filename=f'uploads/{f}') for f in a.photos] if a.photos else [url_for('static', filename='assets/placeholder.png')]

        articles_data.append({
            "id": a.id,
            "title": a.title,
            "price": a.price,
            "category": a.category,
            "condition": a.condition,
            "city": a.city,
            "description": a.description,
            "photos": photos_urls,
            "seller_first_name": a.user.first_name if a.user else "Anonyme",
            "seller_last_name": a.user.last_name if a.user else "",
            "status": a.status
        })

    # DEBUG rapide
    print(f"Articles affichés sur dashboard: {len(articles_data)}")

    return render_template('Dashboard.html', user_first_name=user_first_name, articles=articles_data, active='dashboard')

app.register_blueprint(sell_bp)

#cinetpay

@app.route("/api/create_payment", methods=["POST"])
@jwt_required()
def create_payment():
    user_id = int(get_jwt_identity())
    data = request.get_json()
    amount = data.get("amount")
    desc = data.get("desc")
    article_id = data.get("article_id")

    if not amount or not article_id:
        return jsonify({"error": "Montant ou article manquant"}), 400

    payment_url = f"https://link-checkout.cinetpay.com/SLexNbVysK?amount={amount}&desc={desc}&ref=article_{article_id}_{user_id}"

    return jsonify({"payment_url": payment_url})

@app.route("/api/admin/valider_cotisation/<int:cot_id>", methods=["POST"])
def valider_cotisation(cot_id):
    cot = Cotisation.query.get_or_404(cot_id)
    if cot.statut == "valide":
        return jsonify({"error": "Déjà validée"}), 400

    user = User.query.get(cot.user_id)
    if not user:
        return jsonify({"error": "Utilisateur introuvable"}), 404

    # Vérifie que le solde n’est pas None
    if user.balance is None:
        user.balance = 0.0

    # Incrémente le solde directement
    user.balance += float(cot.montant_recu or 0)
    cot.statut = "valide"

    db.session.commit()

    return jsonify({
        "message": f"Cotisation #{cot.id} validée. Solde utilisateur mis à jour.",
        "nouveau_solde": user.balance
    }), 200






@app.route("/api/inbox/<int:user_id>", methods=["GET"])
@jwt_required()
def get_inbox(user_id):
    current_id = get_jwt_identity()
    if current_id != user_id:
        return jsonify({"error": "Accès non autorisé"}), 403

    # Récupère les conversations où l’utilisateur est impliqué
    messages = Message.query.filter(
        (Message.sender_id == user_id) | (Message.receiver_id == user_id)
    ).all()

    if not messages:
        return jsonify([])

    # Liste des interlocuteurs uniques
    interlocuteurs_ids = set()
    for m in messages:
        if m.sender_id != user_id:
            interlocuteurs_ids.add(m.sender_id)
        if m.receiver_id != user_id:
            interlocuteurs_ids.add(m.receiver_id)

    interlocuteurs = User.query.filter(User.id.in_(interlocuteurs_ids)).all()

    result = [
        {
            "id": u.id,
            "first_name": u.first_name,
            "last_name": u.last_name,
            "email": u.email,
            "avatar": u.avatar if hasattr(u, "avatar") else None
        }
        for u in interlocuteurs
    ]

    return jsonify(result)


@app.route("/api/messages", methods=["POST"])
@jwt_required()
def post_message():
    data = request.get_json()
    user_id = int(get_jwt_identity())
    receiver_id = int(data.get('receiver_id', 0))
    article_id = int(data.get('article_id', 0))
    content = data.get('content', '').strip()

    if not receiver_id or not article_id or not content:
        return jsonify({"error": "receiver_id, article_id et content sont requis"}), 400

    # Vérification existences
    article = Article.query.get(article_id)
    if not article:
        return jsonify({"error": "Article inexistant"}), 404

    receiver = User.query.get(receiver_id)
    if not receiver:
        return jsonify({"error": "Utilisateur destinataire inexistant"}), 404

    # Création du message
    msg = Message(
        sender_id=user_id,
        receiver_id=receiver_id,
        article_id=article_id,
        content=content
    )
    db.session.add(msg)
    db.session.commit()

    sender_user = User.query.get(user_id)

    response = {
        "id": msg.id,
        "sender_id": msg.sender_id,
        "receiver_id": msg.receiver_id,
        "article_id": msg.article_id,
        "content": msg.content,
        "timestamp": msg.timestamp.isoformat(),
        "sender_name": f"{sender_user.first_name} {sender_user.last_name}"
    }

    # Émission Socket.IO
    room = f"chat_{min(user_id, receiver_id)}_{max(user_id, receiver_id)}_{article_id}"
    socketio.emit("receive_message", response, room=room)

    return jsonify(response), 201


# ------------------- SOCKET.IO -------------------
# -- SOCKET.IO CHAT
@socketio.on('join')
def join(data):
    sender = data.get('userId')
    receiver = data.get('receiverId')
    article_id = data.get('articleId', '0')

    if not sender or not receiver:
        print(f"⚠️ Erreur join : données manquantes {data}")
        return

    room = f"chat_{min(sender, receiver)}_{max(sender, receiver)}_{article_id}"
    join_room(room)
    print(f"✅ Utilisateur {sender} a rejoint la room : {room}")
    emit('status', {'msg': f"Utilisateur {sender} a rejoint le chat."}, room=room)


@socketio.on('send_message')
def handle_message(data):
    room = f"chat_{min(data['sender_id'], data['receiver_id'])}_{max(data['sender_id'], data['receiver_id'])}_{data.get('article_id','0')}"
    msg = Message(sender_id=data['sender_id'], receiver_id=data['receiver_id'], article_id=data.get('article_id'), content=data['content'])
    db.session.add(msg)
    db.session.commit()
    emit('receive_message', {
        "id": msg.id,"sender_id": msg.sender_id,"receiver_id": msg.receiver_id,"content": msg.content,"timestamp": str(msg.timestamp)
    }, room=room)



@app.route('/api/conversations', methods=['GET'])
@jwt_required()
def get_conversations():
    user_id = int(get_jwt_identity())

    # On récupère tous les messages où l'utilisateur est concerné
    messages = Message.query.filter(
        (Message.sender_id == user_id) | (Message.receiver_id == user_id)
    ).order_by(Message.timestamp.desc()).all()

    conversations = {}

    for msg in messages:
        other_id = msg.receiver_id if msg.sender_id == user_id else msg.sender_id
        article_id = msg.article_id or 0
        key = f"{other_id}_{article_id}"  # ✅ chaque article crée une conversation unique

        # On s’assure que l’autre utilisateur existe
        other_user = User.query.get(other_id)
        if not other_user:
            continue  # ⛔ Si l’autre utilisateur a été supprimé, on saute

        # On récupère l’image du produit concerné
        article = Article.query.get(article_id) if article_id else None
        if article and article.photos and len(article.photos) > 0:
            article_image = url_for('static', filename=f"uploads/{article.photos[0]}", _external=True)
        else:
            article_image = url_for('static', filename='assets/placeholder.png', _external=True)

        # Si la conversation n’est pas encore enregistrée, on la crée
        if key not in conversations:
            conversations[key] = {
                "peer_id": other_id,
                "peer_name": f"{other_user.first_name} {other_user.last_name}",
                "article_id": article_id,
                "article_title": article.title if article else "Article inconnu",
                "avatar": article_image,
                "last_message": msg.content,
                "timestamp": msg.timestamp.isoformat(),
                "unread": 0
            }

        # Incrément des messages non lus
        if msg.receiver_id == user_id and not msg.read:
            conversations[key]["unread"] += 1

    return jsonify(list(conversations.values()))


#pour compter les messages non lu

@app.route("/api/unread_count")
@jwt_required()
def unread_count():
    user_id = get_jwt_identity()
    count = Message.query.filter_by(receiver_id=user_id, read=False).count()
    return jsonify({"count": count})



# Marquer les messages comme lus pour une conversation
@app.route('/api/mark_read/<int:peer_id>', methods=['POST'])
@jwt_required()
def mark_read(peer_id):
    user_id = get_jwt_identity()
    msgs = Message.query.filter_by(sender_id=peer_id, receiver_id=user_id, read=False).all()
    for m in msgs:
        m.read = True
    db.session.commit()
    return jsonify({'success': True})

@app.route('/api/messages/<int:peer_id>', methods=['GET'])
@jwt_required()
def get_messages(peer_id):
    user_id = int(get_jwt_identity())
    
    messages = Message.query.filter(
        ((Message.sender_id == user_id) & (Message.receiver_id == peer_id)) |
        ((Message.sender_id == peer_id) & (Message.receiver_id == user_id))
    ).order_by(Message.timestamp.asc()).all()
    
    # Marquer les messages reçus comme lus
    for m in messages:
        if m.receiver_id == user_id and not m.read:
            m.read = True
    db.session.commit()
    
    return jsonify([
        {
            "id": m.id,
            "sender_id": m.sender_id,
            "receiver_id": m.receiver_id,
            "article_id": m.article_id,
            "content": m.content,
            "timestamp": m.timestamp.isoformat(),
            "read": m.read
        } for m in messages
    ])
#POUR ENREGISTRER ET MODIFIER DEPUIS MON DASHBOARD ADMIN 

# --- USERS ---
@app.route("/api/admin/user/<int:user_id>/<action>", methods=["POST"])
@jwt_required()
def admin_user_action(user_id, action):
    user = User.query.get_or_404(user_id)
    if action == "activate":
        user.is_active = True
    elif action == "deactivate":
        user.is_active = False
    elif action == "delete":
        db.session.delete(user)
        db.session.commit()
        return jsonify({"message": f"Utilisateur {user.email} supprimé avec succès."}), 200
    else:
        return jsonify({"message": "Action non reconnue"}), 400
    db.session.commit()
    return jsonify({"message": f"Utilisateur {action} avec succès."}), 200

@app.route("/api/admin/user/<int:user_id>/update", methods=["POST"])
@jwt_required()
def update_user(user_id):
    user = User.query.get_or_404(user_id)
    data = request.get_json()
    user.first_name = data.get("first_name", user.first_name)
    user.email = data.get("email", user.email)
    user.phone = data.get("phone", user.phone)
    db.session.commit()
    return jsonify({"message": "Utilisateur mis à jour avec succès."}), 200

# --- ARTICLES ---
@app.route("/api/admin/article/<int:article_id>/<action>", methods=["POST"])
@jwt_required()
def admin_article_action(article_id, action):
    article = Article.query.get_or_404(article_id)
    if action == "approve":
        article.status = "approved"
    elif action == "reject":
        article.status = "rejected"
    else:
        return jsonify({"message": "Action non reconnue"}), 400
    db.session.commit()
    return jsonify({"message": f"Article {action} avec succès."}), 200

@app.route("/api/admin/article/<int:article_id>/update", methods=["POST"])
@jwt_required()
def update_article(article_id):
    article = Article.query.get_or_404(article_id)
    data = request.get_json()
    article.title = data.get("title", article.title)
    article.description = data.get("description", article.description)
    article.price = data.get("price", article.price)
    article.category = data.get("category", article.category)
    db.session.commit()
    return jsonify({"message": "Article mis à jour avec succès."}), 200




# ---------------- RUN ----------------
with app.app_context():
    db.create_all()
    print("✅ Toutes les tables ont été créées avec succès !")

if __name__ == "__main__":
    # --- Initialisation de la base avant le premier lancement ---
    with app.app_context():
        try:
            # Configuration DB pour Railway
            if os.environ.get('DATABASE_URL'):
                app.config['SQLALCHEMY_DATABASE_URI'] = os.environ.get('DATABASE_URL').replace('postgres://', 'postgresql://')
                print("🔗 Utilisation de DATABASE_URL de Railway")
            
            # Vérifiez la configuration DB
            print(f"📡 DATABASE_URL: {os.environ.get('DATABASE_URL', 'Non défini')}")
            print(f"🔧 SQLALCHEMY_DATABASE_URI: {app.config.get('SQLALCHEMY_DATABASE_URI', 'Non défini')}")

            # Testez la connexion
            try:
                with db.engine.connect() as conn:
                    print("✅ Connexion DB réussie")
            except Exception as e:
                print(f"❌ Erreur connexion DB: {e}")
                raise

            # Création des tables
            print("🔄 Création des tables...")
            db.create_all()
            print("✅ Base de données initialisée.")

            # Vérifiez si les tables existent
            from sqlalchemy import inspect
            inspector = inspect(db.engine)
            tables = inspector.get_table_names()
            print(f"📋 Tables disponibles: {tables}")

            # --- Création automatique d'un compte admin "caché" si absent ---
            admin_email = "pythamoua@gmail.com"
            admin = User.query.filter_by(email=admin_email).first()
            if not admin:
                admin = User(
                    first_name="Admin",
                    last_name="Izrussia",
                    email=admin_email,
                    phone="0000000000",
                    password="admin123"
                )
                admin.role = "admin"
                admin.is_active = True
                db.session.add(admin)
                db.session.commit()
                print("✅ Compte admin créé :", admin_email, "/ mot de passe par défaut: admin123")
            else:
                print("ℹ️ Compte admin déjà existant :", admin_email)

        except Exception as e:
            print(f"❌ Erreur lors de l'initialisation: {e}")

    # --- Démarrage du serveur Flask + SocketIO ---
    port = int(os.environ.get("PORT", 5000))
    print(f"🚀 Démarrage du serveur sur le port {port}")
    socketio.run(app, host="0.0.0.0", port=port)