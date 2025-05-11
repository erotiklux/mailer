"""
Module de service de paiement pour G4mailsender Bot.
Gère le traitement des paiements avec Oxapay.
"""

import json
import logging
import uuid
from datetime import datetime, timedelta
from typing import Dict, Any, Optional

import requests

from config import Config
from database import Database


logger = logging.getLogger(__name__)

# URL de base de l'API Oxapay
OXAPAY_API_URL = "https://api.oxapay.com/v1"


class PaymentService:
    """Service de paiement pour gérer l'intégration Oxapay."""
    
    def __init__(self, config: Config, db: Database):
        """Initialiser le service de paiement avec la configuration."""
        self.config = config
        self.db = db
        self.api_key = config.OXAPAY_API_KEY
        self.merchant_id = config.OXAPAY_MERCHANT_ID
        self.webhook_secret = config.OXAPAY_WEBHOOK_SECRET
    
    async def create_payment(
        self, user_id: int, subscription_type: str
    ) -> Dict[str, Any]:
        """
        Créer une demande de paiement avec Oxapay.
        
        Args:
            user_id: ID utilisateur Telegram
            subscription_type: Type d'abonnement (mensuel, annuel, à vie)
            
        Returns:
            Dict avec les détails de paiement incluant ID et URL de paiement
        """
        # Générer un ID de paiement unique
        payment_id = str(uuid.uuid4())
        
        # Déterminer le montant et la description en fonction du type d'abonnement
        if subscription_type == "monthly":
            amount = self.config.SUBSCRIPTION_PRICE_MONTHLY
            description = "Abonnement Mensuel G4mailsender"
        elif subscription_type == "annual":
            amount = self.config.SUBSCRIPTION_PRICE_ANNUAL
            description = "Abonnement Annuel G4mailsender"
        elif subscription_type == "lifetime":
            amount = self.config.SUBSCRIPTION_PRICE_LIFETIME
            description = "Abonnement à Vie G4mailsender"
        else:
            raise ValueError(f"Type d'abonnement non valide: {subscription_type}")
        
        # Créer la charge utile du paiement
        payload = {
            "merchant_id": self.merchant_id,
            "amount": amount,
            "currency": "USD",
            "order_id": payment_id,
            "description": description,
            "callback_url": f"https://yourdomain.com/webhook/oxapay",  # Remplacer par votre URL webhook
            "return_url": f"https://t.me/{self.config.BOT_USERNAME}",  # Remplacer par votre nom d'utilisateur bot
            "custom": json.dumps({"user_id": user_id, "subscription_type": subscription_type}),
        }
        
        headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {self.api_key}"
        }
        
        try:
            # Faire une requête API pour créer le paiement
            response = requests.post(
                f"{OXAPAY_API_URL}/checkout",
                json=payload,
                headers=headers
            )
            response.raise_for_status()
            
            # Analyser la réponse
            result = response.json()
            
            if result.get("status") == "success":
                payment_data = result.get("data", {})
                
                # Journaliser le paiement dans la base de données
                await self.db.log_payment(
                    payment_id=payment_id,
                    user_id=user_id,
                    amount=amount,
                    subscription_type=subscription_type,
                    status="pending"
                )
                
                return {
                    "id": payment_id,
                    "payment_url": payment_data.get("url"),
                    "status": "pending",
                    "subscription_type": subscription_type,
                    "amount": amount
                }
            else:
                error_message = result.get("message", "Erreur inconnue")
                logger.error(f"Échec de la création du paiement : {error_message}")
                raise Exception(f"La création du paiement a échoué : {error_message}")
                
        except requests.RequestException as e:
            logger.error(f"Erreur de requête API de paiement : {str(e)}")
            raise Exception(f"La requête API de paiement a échoué : {str(e)}")
    
    async def check_payment(self, payment_id: str) -> Dict[str, Any]:
        """
        Vérifier le statut d'un paiement.
        
        Args:
            payment_id: ID de paiement à vérifier
            
        Returns:
            Dict avec les informations de statut de paiement
        """
        headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {self.api_key}"
        }
        
        try:
            # Faire une requête API pour vérifier le statut du paiement
            response = requests.get(
                f"{OXAPAY_API_URL}/checkout/{payment_id}",
                headers=headers
            )
            response.raise_for_status()
            
            # Analyser la réponse
            result = response.json()
            
            if result.get("status") == "success":
                payment_data = result.get("data", {})
                payment_status = payment_data.get("status", "unknown")
                
                # Obtenir les détails du paiement depuis la base de données
                payment = await self.db.get_payment(payment_id)
                subscription_type = payment.get("subscription_type") if payment else None
                
                # Mettre à jour le statut du paiement dans la base de données
                await self.db.update_payment_status(payment_id, payment_status)
                
                # Si le paiement est complété, mettre à jour l'abonnement utilisateur
                if payment_status == "completed" and payment:
                    user_id = payment.get("user_id")
                    await self._update_user_subscription(user_id, subscription_type, payment_id)
                
                return {
                    "id": payment_id,
                    "status": payment_status,
                    "payment_url": payment_data.get("url"),
                    "subscription_type": subscription_type
                }
            else:
                error_message = result.get("message", "Erreur inconnue")
                logger.error(f"Échec de la vérification du paiement : {error_message}")
                raise Exception(f"La vérification du paiement a échoué : {error_message}")
                
        except requests.RequestException as e:
            logger.error(f"Erreur de vérification du statut de paiement : {str(e)}")
            raise Exception(f"La vérification du statut du paiement a échoué : {str(e)}")
    
    async def _update_user_subscription(
        self, user_id: int, subscription_type: str, payment_id: str
    ) -> None:
        """
        Mettre à jour l'abonnement de l'utilisateur en fonction du type d'abonnement.
        
        Args:
            user_id: ID utilisateur Telegram
            subscription_type: Type d'abonnement (mensuel, annuel, à vie)
            payment_id: ID du paiement
        """
        end_date = None
        
        if subscription_type == "monthly":
            end_date = datetime.now() + timedelta(days=30)
        elif subscription_type == "annual":
            end_date = datetime.now() + timedelta(days=365)
        elif subscription_type == "lifetime":
            end_date = None  # Pas de date de fin pour l'abonnement à vie
        else:
            logger.error(f"Type d'abonnement non valide lors de la mise à jour: {subscription_type}")
            return
        
        await self.db.update_subscription(
            user_id=user_id,
            active=True,
            subscription_type=subscription_type,
            end_date=end_date,
            payment_id=payment_id
        )
    
    def verify_webhook_signature(self, payload: Dict[str, Any], signature: str) -> bool:
        """
        Vérifier la signature du webhook d'Oxapay.
        
        Args:
            payload: Charge utile du webhook
            signature: Signature des en-têtes de requête
            
        Returns:
            Booléen indiquant si la signature est valide
        """
        import hmac
        import hashlib
        
        # Convertir la charge utile en chaîne
        payload_str = json.dumps(payload, separators=(',', ':'))
        
        # Calculer la signature
        expected_signature = hmac.new(
            self.webhook_secret.encode('utf-8'),
            payload_str.encode('utf-8'),
            hashlib.sha256
        ).hexdigest()
        
        # Vérifier la signature
        return hmac.compare_digest(expected_signature, signature)
    
    async def process_webhook(self, payload: Dict[str, Any], signature: str) -> Dict[str, Any]:
        """
        Traiter la notification webhook d'Oxapay.
        
        Args:
            payload: Charge utile du webhook
            signature: Signature des en-têtes de requête
            
        Returns:
            Dict avec le résultat du traitement
        """
        # Vérifier la signature
        if not self.verify_webhook_signature(payload, signature):
            logger.warning("Signature de webhook non valide")
            return {"status": "error", "message": "Signature non valide"}
        
        try:
            # Extraire les données de paiement
            payment_id = payload.get("order_id")
            status = payload.get("status")
            custom_data = json.loads(payload.get("custom", "{}"))
            user_id = custom_data.get("user_id")
            subscription_type = custom_data.get("subscription_type")
            
            if not all([payment_id, status, user_id, subscription_type]):
                return {"status": "error", "message": "Champs requis manquants"}
            
            # Mettre à jour le statut du paiement dans la base de données
            await self.db.update_payment_status(payment_id, status)
            
            # Si le paiement est complété, mettre à jour l'abonnement utilisateur
            if status == "completed":
                await self._update_user_subscription(
                    user_id=user_id,
                    subscription_type=subscription_type,
                    payment_id=payment_id
                )
            
            return {"status": "success", "message": "Webhook traité"}
            
        except Exception as e:
            logger.error(f"Erreur de traitement de webhook : {str(e)}")
            return {"status": "error", "message": str(e)}