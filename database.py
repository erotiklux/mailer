"""
Module de base de données pour G4mailsender Bot.
Fournit des opérations de base de données pour la gestion des utilisateurs, templates et journalisation.
"""

import logging
from datetime import datetime
from typing import Dict, List, Optional, Any, Union

import pymongo
from pymongo import MongoClient
from pymongo.collection import Collection


logger = logging.getLogger(__name__)


class Database:
    """Opérations de base de données pour l'application."""
    
    def __init__(self, uri: str):
        """Initialiser la connexion à la base de données."""
        self.client = MongoClient(uri)
        self.db = self.client.get_database()
        
        # Collections
        self.users: Collection = self.db.users
        self.templates: Collection = self.db.templates
        self.emails: Collection = self.db.emails
        self.payments: Collection = self.db.payments
        self.custom_templates: Collection = self.db.custom_templates
        
        # Créer des index
        self._create_indexes()
    
    def _create_indexes(self) -> None:
        """Créer des index de base de données."""
        # Collection utilisateurs
        self.users.create_index("user_id", unique=True)
        
        # Collection templates
        self.templates.create_index("name", unique=True)
        
        # Collection templates personnalisés
        self.custom_templates.create_index([("user_id", 1), ("name", 1)], unique=True)
        
        # Collection emails
        self.emails.create_index("user_id")
        self.emails.create_index("timestamp")
        
        # Collection paiements
        self.payments.create_index("payment_id", unique=True)
        self.payments.create_index("user_id")
    
    async def get_user(self, user_id: int) -> Optional[Dict[str, Any]]:
        """Obtenir les données utilisateur par user_id."""
        return self.users.find_one({"user_id": user_id})
    
    async def create_user(self, user_id: int, username: str) -> None:
        """Créer un nouvel utilisateur."""
        user_data = {
            "user_id": user_id,
            "username": username,
            "created_at": datetime.now(),
            "subscription_active": False,
            "subscription_type": None,
            "subscription_end_date": None,
            "emails_sent_total": 0,
            "emails_sent_month": 0,
        }
        self.users.insert_one(user_data)
    
    async def update_subscription(
        self, user_id: int, active: bool, subscription_type: str, 
        end_date: Optional[datetime], payment_id: str
    ) -> None:
        """Mettre à jour le statut d'abonnement de l'utilisateur."""
        update_data = {
            "subscription_active": active,
            "subscription_type": subscription_type,
            "last_payment_id": payment_id,
            "emails_sent_month": 0,  # Réinitialiser le compteur lors d'un nouvel abonnement
        }
        
        # Si c'est un abonnement à vie, end_date sera None
        if end_date is not None:
            update_data["subscription_end_date"] = end_date
        else:
            # Pour abonnement à vie, mettre une date très lointaine
            update_data["subscription_end_date"] = None
        
        self.users.update_one(
            {"user_id": user_id},
            {"$set": update_data},
        )
    
    async def log_email_sent(
        self, user_id: int, template_id: str, recipient_email: str, 
        recipient_name: str, is_custom_template: bool = False
    ) -> None:
        """Journaliser un email envoyé par un utilisateur."""
        # Ajouter à la collection emails
        email_data = {
            "user_id": user_id,
            "template_id": template_id,
            "is_custom_template": is_custom_template,
            "recipient_email": recipient_email,
            "recipient_name": recipient_name,
            "timestamp": datetime.now(),
        }
        self.emails.insert_one(email_data)
        
        # Mettre à jour les compteurs utilisateur
        self.users.update_one(
            {"user_id": user_id},
            {
                "$inc": {
                    "emails_sent_total": 1,
                    "emails_sent_month": 1,
                }
            },
        )
    
    async def log_payment(
        self, payment_id: str, user_id: int, amount: float, 
        subscription_type: str, status: str
    ) -> None:
        """Journaliser une transaction de paiement."""
        payment_data = {
            "payment_id": payment_id,
            "user_id": user_id,
            "amount": amount,
            "subscription_type": subscription_type,
            "status": status,
            "timestamp": datetime.now(),
        }
        self.payments.insert_one(payment_data)
    
    async def update_payment_status(self, payment_id: str, status: str) -> None:
        """Mettre à jour le statut de paiement."""
        self.payments.update_one(
            {"payment_id": payment_id}, {"$set": {"status": status}}
        )
    
    async def get_payment(self, payment_id: str) -> Optional[Dict[str, Any]]:
        """Obtenir les détails d'un paiement par ID."""
        return self.payments.find_one({"payment_id": payment_id})
    
    async def get_template(self, template_id: str) -> Optional[Dict[str, Any]]:
        """Obtenir un template par ID."""
        return self.templates.find_one({"id": template_id})
    
    async def get_templates(self) -> List[Dict[str, Any]]:
        """Obtenir tous les templates."""
        return list(self.templates.find())
    
    async def add_template(
        self, template_id: str, name: str, subject: str, content: str
    ) -> None:
        """Ajouter un nouveau template d'email."""
        template_data = {
            "id": template_id,
            "name": name,
            "subject": subject,
            "content": content,
            "created_at": datetime.now(),
        }
        self.templates.insert_one(template_data)
    
    async def add_custom_template(
        self, user_id: int, template_id: str, name: str, subject: str, content: str
    ) -> None:
        """Ajouter un template personnalisé pour un utilisateur."""
        template_data = {
            "user_id": user_id,
            "id": template_id,
            "name": name,
            "subject": subject,
            "content": content,
            "created_at": datetime.now(),
        }
        self.custom_templates.insert_one(template_data)
    
    async def get_custom_template(self, user_id: int, template_id: str) -> Optional[Dict[str, Any]]:
        """Obtenir un template personnalisé par ID et user_id."""
        return self.custom_templates.find_one({"user_id": user_id, "id": template_id})
    
    async def get_custom_templates(self, user_id: int) -> List[Dict[str, Any]]:
        """Obtenir tous les templates personnalisés d'un utilisateur."""
        return list(self.custom_templates.find({"user_id": user_id}))
    
    async def get_stats(self) -> Dict[str, Union[int, float]]:
        """Obtenir les statistiques de l'application."""
        # Total des utilisateurs
        total_users = self.users.count_documents({})
        
        # Abonnements actifs
        active_subscriptions = self.users.count_documents({
            "subscription_active": True,
            "$or": [
                {"subscription_end_date": {"$gt": datetime.now()}},
                {"subscription_end_date": None}  # Pour les abonnements à vie
            ]
        })
        
        # Abonnements par type
        monthly_subs = self.users.count_documents({
            "subscription_active": True,
            "subscription_type": "monthly",
            "subscription_end_date": {"$gt": datetime.now()}
        })
        
        annual_subs = self.users.count_documents({
            "subscription_active": True,
            "subscription_type": "annual",
            "subscription_end_date": {"$gt": datetime.now()}
        })
        
        lifetime_subs = self.users.count_documents({
            "subscription_active": True,
            "subscription_type": "lifetime"
        })
        
        # Total des emails envoyés
        emails_sent = self.emails.count_documents({})
        
        # Emails envoyés aujourd'hui
        today_start = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)
        emails_sent_today = self.emails.count_documents({
            "timestamp": {"$gte": today_start}
        })
        
        return {
            "total_users": total_users,
            "active_subscriptions": active_subscriptions,
            "monthly_subscriptions": monthly_subs,
            "annual_subscriptions": annual_subs,
            "lifetime_subscriptions": lifetime_subs,
            "emails_sent": emails_sent,
            "emails_sent_today": emails_sent_today,
        }