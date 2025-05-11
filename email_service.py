"""
Module de service d'email pour G4mailsender Bot.
Gère la fonctionnalité d'envoi d'emails avec ID d'expéditeur personnalisé.
"""

import logging
import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from typing import Dict, Any

from config import Config


logger = logging.getLogger(__name__)


class EmailService:
    """Service d'email pour l'envoi d'emails."""
    
    def __init__(self, config: Config):
        """Initialiser le service d'email avec la configuration."""
        self.config = config
        self.host = config.EMAIL_HOST
        self.port = config.EMAIL_PORT
        self.username = config.EMAIL_USER
        self.password = config.EMAIL_PASSWORD
    
    async def send_email(
        self,
        recipient_email: str,
        subject: str,
        content: str,
        sender_name: str = None,
    ) -> Dict[str, Any]:
        """
        Envoyer un email au destinataire spécifié.
        
        Args:
            recipient_email: Adresse email du destinataire
            subject: Objet de l'email
            content: Contenu de l'email (HTML ou texte brut)
            sender_name: Nom personnalisé de l'expéditeur
            
        Returns:
            Dict contenant le statut et le message
        """
        try:
            # Créer un conteneur de message
            msg = MIMEMultipart('alternative')
            msg['Subject'] = subject
            
            # Définir l'expéditeur avec un nom personnalisé si fourni
            if sender_name:
                msg['From'] = f"{sender_name} <{self.username}>"
            else:
                msg['From'] = self.username
                
            msg['To'] = recipient_email
            
            # Joindre les versions HTML et texte brut
            text_part = MIMEText(self._strip_html(content), 'plain')
            html_part = MIMEText(content, 'html')
            
            msg.attach(text_part)
            msg.attach(html_part)
            
            # Envoyer l'email
            with smtplib.SMTP(self.host, self.port) as server:
                server.starttls()
                server.login(self.username, self.password)
                server.send_message(msg)
            
            logger.info(f"Email envoyé avec succès à {recipient_email}")
            return {"status": "success", "message": "Email envoyé avec succès"}
            
        except Exception as e:
            logger.error(f"Échec de l'envoi de l'email : {str(e)}")
            return {"status": "error", "message": str(e)}
    
    def _strip_html(self, html_content: str) -> str:
        """
        Convertir le contenu HTML en texte brut pour le fallback.
        Ceci est une implémentation simple - pour la production,
        envisagez d'utiliser un convertisseur HTML-texte approprié.
        """
        # Ceci est une implémentation très basique
        text = html_content
        text = text.replace('<br>', '\n').replace('<br/>', '\n').replace('<br />', '\n')
        text = text.replace('<p>', '\n').replace('</p>', '\n')
        text = text.replace('<div>', '\n').replace('</div>', '\n')
        text = text.replace('<h1>', '\n').replace('</h1>', '\n')
        text = text.replace('<h2>', '\n').replace('</h2>', '\n')
        text = text.replace('<h3>', '\n').replace('</h3>', '\n')
        text = text.replace('<li>', '\n- ').replace('</li>', '')
        
        # Supprimer toutes les balises HTML restantes
        in_tag = False
        result = ""
        for char in text:
            if char == '<':
                in_tag = True
            elif char == '>':
                in_tag = False
            elif not in_tag:
                result += char
        
        # Nettoyer les sauts de ligne multiples
        while '\n\n\n' in result:
            result = result.replace('\n\n\n', '\n\n')
        
        return result.strip()