"""
Module de configuration pour G4mailsender Bot.
Charge les variables d'environnement et fournit les paramètres de configuration.
"""

import os
from typing import List


class Config:
    """Classe de configuration pour l'application."""
    
    def __init__(self):
        # Configuration du Bot Telegram
        self.TELEGRAM_API_TOKEN = os.getenv("TELEGRAM_API_TOKEN", "")
        if not self.TELEGRAM_API_TOKEN:
            raise ValueError("La variable d'environnement TELEGRAM_API_TOKEN n'est pas définie")
        
        # Nom du bot
        self.BOT_USERNAME = os.getenv("BOT_USERNAME", "G4mailsender_bot")
        
        # Configuration Email
        self.EMAIL_HOST = os.getenv("EMAIL_HOST", "")
        self.EMAIL_PORT = int(os.getenv("EMAIL_PORT", "587"))
        self.EMAIL_USER = os.getenv("EMAIL_USER", "")
        self.EMAIL_PASSWORD = os.getenv("EMAIL_PASSWORD", "")
        
        # Validation des paramètres email
        if not all([self.EMAIL_HOST, self.EMAIL_USER, self.EMAIL_PASSWORD]):
            raise ValueError("Les variables d'environnement de configuration email ne sont pas définies")
        
        # Configuration Oxapay
        self.OXAPAY_API_KEY = os.getenv("OXAPAY_API_KEY", "")
        self.OXAPAY_MERCHANT_ID = os.getenv("OXAPAY_MERCHANT_ID", "")
        self.OXAPAY_WEBHOOK_SECRET = os.getenv("OXAPAY_WEBHOOK_SECRET", "")
        
        # Validation des paramètres Oxapay
        if not all([self.OXAPAY_API_KEY, self.OXAPAY_MERCHANT_ID]):
            raise ValueError("Les variables d'environnement de configuration Oxapay ne sont pas définies")
        
        # Configuration MongoDB
        self.MONGODB_URI = os.getenv("MONGODB_URI", "mongodb://localhost:27017/g4mailsender")
        
        # Paramètres Administrateur
        admin_ids = os.getenv("ADMIN_USER_IDS", "")
        self.ADMIN_USER_IDS: List[str] = admin_ids.split(",") if admin_ids else []
        
        # Paramètres d'abonnement
        self.SUBSCRIPTION_PRICE_MONTHLY = float(os.getenv("SUBSCRIPTION_PRICE_MONTHLY", "9.99"))
        self.SUBSCRIPTION_PRICE_ANNUAL = float(os.getenv("SUBSCRIPTION_PRICE_ANNUAL", "99.99"))
        self.SUBSCRIPTION_PRICE_LIFETIME = float(os.getenv("SUBSCRIPTION_PRICE_LIFETIME", "299.99"))