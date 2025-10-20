import os

import os

class Config:
    # Clé secrète pour Flask
    SECRET_KEY = os.environ.get("SECRET_KEY", "dev-secret-key")  

    # Connexion à PostgreSQL
    SQLALCHEMY_DATABASE_URI = os.environ.get(
        "DATABASE_URL",
        "postgresql://postgres:hSiYApwtJSqJEpuxLYkrWKKosCgFdVYh@postgres.railway.internal:5432/railway"
    )
    SQLALCHEMY_TRACK_MODIFICATIONS = False  # éviter des warnings

    # Configuration Flask-Mail
    MAIL_SERVER = os.environ.get("MAIL_SERVER", "smtp.gmail.com")
    MAIL_PORT = int(os.environ.get("MAIL_PORT", 587))
    MAIL_USE_TLS = os.environ.get("MAIL_USE_TLS", "True") == "True"
    MAIL_USERNAME = os.environ.get("MAIL_USERNAME", "moua19878@gmail.com")
    MAIL_PASSWORD = os.environ.get("MAIL_PASSWORD", "upqc fxna tvyr xwvp")
    MAIL_DEFAULT_SENDER = os.environ.get("MAIL_DEFAULT_SENDER", "IZRUSSIA <moua19878@gmail.com>")



