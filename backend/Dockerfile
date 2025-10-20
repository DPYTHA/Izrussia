# =========================
# Dockerfile pour backend Flask
# =========================

# 1️⃣ Image de base
FROM python:3.11-slim

# 2️⃣ Variables d'environnement pour éviter les messages d'alerte
ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

# 3️⃣ Créer le répertoire de travail dans le conteneur
WORKDIR /app

# 4️⃣ Installer les dépendances système nécessaires pour psycopg2
RUN apt-get update && apt-get install -y \
    build-essential \
    libpq-dev \
    gcc \
    && rm -rf /var/lib/apt/lists/*

# 5️⃣ Copier le fichier requirements.txt et installer les dépendances Python
COPY requirements.txt .
RUN pip install --upgrade pip
RUN pip install --no-cache-dir -r requirements.txt

# 6️⃣ Copier tout le code source dans le conteneur
COPY . .

# 7️⃣ Exposer le port de l'application Flask
EXPOSE 5000

# 8️⃣ Commande pour lancer l'application avec Gunicorn
#    app:app -> app.py et variable Flask app
CMD ["gunicorn", "-b", "0.0.0.0:5000", "app:app"]
