#!/bin/bash
echo "🚀 Lancement de l'application IZRUSSIA..."

# Aller dans le dossier backend
cd backend

# Installer les dépendances Python
pip install -r requirements.txt

# Lancer Flask
python app.py
chmod +x start.sh
