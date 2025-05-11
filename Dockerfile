FROM python:3.10-slim

WORKDIR /app

# Copier les requirements d'abord pour un meilleur caching
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copier le code de l'application
COPY . .

# Rendre les scripts exécutables
RUN chmod +x bot.py webhook.py

# Exécuter le bot par défaut
CMD ["python", "bot.py"]