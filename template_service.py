"""
Module de service de template pour G4mailsender Bot.
Gère la gestion des templates d'email et la génération de contenu.
"""

import logging
import uuid
from typing import Dict, List, Any, Optional, Set

from database import Database


logger = logging.getLogger(__name__)


class TemplateService:
    """Service de template d'email."""
    
    def __init__(self, db: Database):
        """Initialiser le service de template avec la base de données."""
        self.db = db
    
    async def get_templates(self) -> List[Dict[str, Any]]:
        """Obtenir tous les templates d'email disponibles."""
        return await self.db.get_templates()
    
    async def get_template(self, template_id: str) -> Optional[Dict[str, Any]]:
        """Obtenir un template par ID."""
        return await self.db.get_template(template_id)
    
    async def get_custom_templates(self, user_id: int) -> List[Dict[str, Any]]:
        """Obtenir tous les templates personnalisés d'un utilisateur."""
        return await self.db.get_custom_templates(user_id)
    
    async def get_custom_template(self, user_id: int, template_id: str) -> Optional[Dict[str, Any]]:
        """Obtenir un template personnalisé par ID et user_id."""
        return await self.db.get_custom_template(user_id, template_id)
    
    async def add_template(self, name: str, subject: str, content: str) -> str:
        """
        Ajouter un nouveau template d'email.
        
        Args:
            name: Nom du template
            subject: Objet de l'email
            content: Contenu de l'email avec des placeholders
            
        Returns:
            ID du template
        """
        template_id = str(uuid.uuid4())
        await self.db.add_template(template_id, name, subject, content)
        return template_id
    
    async def add_custom_template(
        self, user_id: int, name: str, subject: str, content: str
    ) -> str:
        """
        Ajouter un template personnalisé pour un utilisateur.
        
        Args:
            user_id: ID utilisateur Telegram
            name: Nom du template
            subject: Objet de l'email
            content: Contenu de l'email avec des placeholders
            
        Returns:
            ID du template
        """
        template_id = str(uuid.uuid4())
        await self.db.add_custom_template(user_id, template_id, name, subject, content)
        return template_id
    
    def extract_placeholders(self, content: str) -> Set[str]:
        """
        Extraire tous les placeholders d'un template.
        Les placeholders sont au format {nom_du_placeholder}.
        
        Args:
            content: Contenu du template
            
        Returns:
            Ensemble des noms de placeholders
        """
        import re
        placeholders = set()
        pattern = r'{([^{}]*)}'
        
        matches = re.findall(pattern, content)
        for match in matches:
            placeholders.add(match)
        
        return placeholders
    
    def generate_email_content(
        self, template: Dict[str, Any], replacements: Dict[str, str]
    ) -> str:
        """
        Générer le contenu de l'email en remplaçant les placeholders dans le template.
        
        Args:
            template: Dict du template d'email
            replacements: Dict des clés de placeholder et valeurs de remplacement
            
        Returns:
            Contenu d'email généré
        """
        content = template["content"]
        
        # Remplacer tous les placeholders
        for key, value in replacements.items():
            placeholder = f"{{{key}}}"
            content = content.replace(placeholder, value)
        
        return content
    
    async def create_default_templates(self) -> None:
        """Créer des templates d'email par défaut si aucun n'existe."""
        templates = await self.get_templates()
        
        if not templates:
            # Template de bienvenue
            await self.add_template(
                name="Email de Bienvenue",
                subject="Bienvenue sur Notre Service",
                content="""
                <html>
                <body style="font-family: Arial, sans-serif; line-height: 1.6; color: #333;">
                    <div style="max-width: 600px; margin: 0 auto; padding: 20px;">
                        <h1 style="color: #4a6ee0;">Bienvenue, {nom}!</h1>
                        <p>Merci d'avoir rejoint notre service. Nous sommes ravis de vous avoir à bord!</p>
                        <p>Voici quelques ressources pour vous aider à démarrer:</p>
                        <ul>
                            <li>Notre <a href="https://exemple.com/guide" style="color: #4a6ee0;">Guide de Démarrage</a></li>
                            <li><a href="https://exemple.com/faq" style="color: #4a6ee0;">Questions fréquemment posées</a></li>
                            <li>Comment <a href="https://exemple.com/contact" style="color: #4a6ee0;">contacter le support</a></li>
                        </ul>
                        <p>Si vous avez des questions, n'hésitez pas à nous contacter!</p>
                        <div style="margin-top: 30px; padding-top: 20px; border-top: 1px solid #eee;">
                            <p style="font-size: 12px; color: #777;">
                                Cordialement,<br>
                                L'Équipe
                            </p>
                        </div>
                    </div>
                </body>
                </html>
                """
            )
            
            # Template d'invitation
            await self.add_template(
                name="Invitation à un Événement",
                subject="Vous êtes Invité: Événement Spécial",
                content="""
                <html>
                <body style="font-family: Arial, sans-serif; line-height: 1.6; color: #333;">
                    <div style="max-width: 600px; margin: 0 auto; padding: 20px;">
                        <h1 style="color: #4a6ee0;">Vous êtes Invité, {nom}!</h1>
                        <p>Nous organisons un événement spécial et nous serions ravis que vous vous joigniez à nous.</p>
                        <div style="background-color: #f5f5f5; padding: 15px; border-radius: 5px; margin: 20px 0;">
                            <h2 style="color: #4a6ee0; margin-top: 0;">Détails de l'Événement</h2>
                            <p><strong>Date:</strong> 15 juin 2025</p>
                            <p><strong>Heure:</strong> 19h00 - 22h00</p>
                            <p><strong>Lieu:</strong> {lieu}</p>
                        </div>
                        <p>Veuillez confirmer votre présence en cliquant sur le bouton ci-dessous:</p>
                        <div style="text-align: center; margin: 30px 0;">
                            <a href="https://exemple.com/rsvp" style="background-color: #4a6ee0; color: white; padding: 12px 25px; text-decoration: none; border-radius: 4px; font-weight: bold;">Confirmer Maintenant</a>
                        </div>
                        <p>Nous avons hâte de vous voir!</p>
                        <div style="margin-top: 30px; padding-top: 20px; border-top: 1px solid #eee;">
                            <p style="font-size: 12px; color: #777;">
                                Cordialement,<br>
                                L'Équipe des Événements
                            </p>
                        </div>
                    </div>
                </body>
                </html>
                """
            )
            
            # Template de suivi
            await self.add_template(
                name="Suivi",
                subject="Suite à Notre Conversation",
                content="""
                <html>
                <body style="font-family: Arial, sans-serif; line-height: 1.6; color: #333;">
                    <div style="max-width: 600px; margin: 0 auto; padding: 20px;">
                        <h1 style="color: #4a6ee0;">Bonjour {nom},</h1>
                        <p>Je souhaite faire un suivi de notre récente conversation et vous fournir des informations supplémentaires.</p>
                        <p>Comme discuté, voici les prochaines étapes:</p>
                        <ol>
                            <li>Examiner la proposition ci-jointe</li>
                            <li>Planifier une réunion de suivi</li>
                            <li>Finaliser l'accord</li>
                        </ol>
                        <p>N'hésitez pas à me contacter si vous avez des questions ou besoin de clarifications.</p>
                        <div style="text-align: center; margin: 30px 0;">
                            <a href="https://exemple.com/planifier" style="background-color: #4a6ee0; color: white; padding: 12px 25px; text-decoration: none; border-radius: 4px; font-weight: bold;">Planifier une Réunion</a>
                        </div>
                        <div style="margin-top: 30px; padding-top: 20px; border-top: 1px solid #eee;">
                            <p style="font-size: 12px; color: #777;">
                                Cordialement,<br>
                                L'Équipe Commerciale
                            </p>
                        </div>
                    </div>
                </body>
                </html>
                """
            )
            
            # Template de rappel de facture 
            await self.add_template(
                name="Rappel de Facture",
                subject="Rappel: Facture en Attente de Paiement",
                content="""
                <html>
                <body style="font-family: Arial, sans-serif; line-height: 1.6; color: #333;">
                    <div style="max-width: 600px; margin: 0 auto; padding: 20px;">
                        <h1 style="color: #4a6ee0;">Rappel de Facture</h1>
                        <p>Cher/Chère {nom},</p>
                        <p>Nous vous rappelons que la facture <strong>#{numero_facture}</strong> d'un montant de <strong>{montant} €</strong> est actuellement en attente de paiement.</p>
                        <div style="background-color: #f5f5f5; padding: 15px; border-radius: 5px; margin: 20px 0;">
                            <h2 style="color: #4a6ee0; margin-top: 0;">Détails de la Facture</h2>
                            <p><strong>Numéro de facture:</strong> #{numero_facture}</p>
                            <p><strong>Date d'émission:</strong> {date_emission}</p>
                            <p><strong>Date d'échéance:</strong> {date_echeance}</p>
                            <p><strong>Montant dû:</strong> {montant} €</p>
                        </div>
                        <p>Veuillez effectuer votre paiement dès que possible pour éviter tout frais de retard.</p>
                        <div style="text-align: center; margin: 30px 0;">
                            <a href="https://exemple.com/paiement" style="background-color: #4a6ee0; color: white; padding: 12px 25px; text-decoration: none; border-radius: 4px; font-weight: bold;">Payer Maintenant</a>
                        </div>
                        <p>Si vous avez déjà effectué le paiement, veuillez ignorer ce message.</p>
                        <div style="margin-top: 30px; padding-top: 20px; border-top: 1px solid #eee;">
                            <p style="font-size: 12px; color: #777;">
                                Cordialement,<br>
                                Service Comptabilité
                            </p>
                        </div>
                    </div>
                </body>
                </html>
                """
            )
            
            logger.info("Templates d'email par défaut créés")