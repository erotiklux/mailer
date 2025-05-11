#!/usr/bin/env python3
"""
G4mailsender - Bot Telegram d'envoi d'emails avec Intégration Oxapay

Un bot Telegram qui envoie des emails avec ID d'expéditeur personnalisé en utilisant des templates prédéfinis.
Les utilisateurs paient un abonnement mensuel, annuel ou à vie via Oxapay pour accéder au service.
"""

import logging
import os
from datetime import datetime, timedelta
from typing import Dict, Any, List, Optional

from dotenv import load_dotenv
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    Application,
    CommandHandler,
    MessageHandler,
    CallbackQueryHandler,
    ContextTypes,
    filters,
    ConversationHandler,
)

from config import Config
from database import Database
from email_service import EmailService
from payment_service import PaymentService
from template_service import TemplateService

# Charger les variables d'environnement
load_dotenv()

# Configurer le logging
logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s", level=logging.INFO
)
logger = logging.getLogger(__name__)

# États de conversation
START, SUBSCRIPTION_SELECTION = range(2)
TEMPLATE_SELECTION, CUSTOM_TEMPLATE, CUSTOM_TEMPLATE_NAME, CUSTOM_TEMPLATE_SUBJECT = range(2, 6)
CUSTOM_TEMPLATE_CONTENT, DYNAMIC_FIELDS, EMAIL_PREVIEW, EMAIL_SENDING = range(6, 10)
PAYMENT, PAYMENT_CHECK = range(10, 12)

# Initialiser les services
config = Config()
db = Database(config.MONGODB_URI)
email_service = EmailService(config)
template_service = TemplateService(db)
payment_service = PaymentService(config, db)

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Démarrer la conversation et vérifier si l'utilisateur a un abonnement actif."""
    user = update.effective_user
    user_id = user.id
    context.user_data["user_id"] = user_id
    
    # Vérifier si l'utilisateur existe dans la base de données, sinon le créer
    user_data = await db.get_user(user_id)
    if not user_data:
        await db.create_user(user_id, user.username or "")
        user_data = await db.get_user(user_id)
    
    # Message de bienvenue
    await update.message.reply_text(
        f"👋 Bienvenue sur G4mailsender, {user.first_name}!\n\n"
        "Je suis votre assistant pour l'envoi d'emails personnalisés avec ID d'expéditeur personnalisé."
    )
    
    # Vérifier si l'utilisateur a un abonnement actif
    if not user_data.get("subscription_active", False):
        await show_subscription_options(update, context)
        return SUBSCRIPTION_SELECTION
    
    # L'utilisateur a un abonnement actif
    subscription_type = user_data.get("subscription_type", "")
    subscription_end = user_data.get("subscription_end_date")
    
    if subscription_type == "lifetime":
        subscription_msg = "Vous avez un abonnement à vie."
    else:
        end_date = subscription_end.strftime("%d/%m/%Y") if subscription_end else "inconnue"
        subscription_msg = f"Vous avez un abonnement {subscription_type}. Date d'expiration: {end_date}"
    
    await update.message.reply_text(
        f"✅ {subscription_msg}\n\n"
        "Commençons à envoyer votre email personnalisé!"
    )
    
    return await show_template_selection(update, context)

async def show_subscription_options(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Afficher les options d'abonnement disponibles."""
    buttons = [
        [
            InlineKeyboardButton(
                f"Mensuel ${config.SUBSCRIPTION_PRICE_MONTHLY}/mois", 
                callback_data="subscribe_monthly"
            )
        ],
        [
            InlineKeyboardButton(
                f"Annuel ${config.SUBSCRIPTION_PRICE_ANNUAL}/an", 
                callback_data="subscribe_annual"
            )
        ],
        [
            InlineKeyboardButton(
                f"À vie ${config.SUBSCRIPTION_PRICE_LIFETIME} (paiement unique)", 
                callback_data="subscribe_lifetime"
            )
        ],
    ]
    
    reply_markup = InlineKeyboardMarkup(buttons)
    
    message = (
        "📱 Pour utiliser G4mailsender, vous avez besoin d'un abonnement actif.\n\n"
        "Veuillez choisir un plan d'abonnement:"
    )
    
    if hasattr(update, 'callback_query') and update.callback_query:
        await update.callback_query.edit_message_text(text=message, reply_markup=reply_markup)
    else:
        await update.message.reply_text(text=message, reply_markup=reply_markup)
    
    return SUBSCRIPTION_SELECTION

async def handle_subscription_selection(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Gérer la sélection d'abonnement."""
    query = update.callback_query
    await query.answer()
    
    subscription_type = query.data.split("_")[1]  # monthly, annual, lifetime
    context.user_data["subscription_type"] = subscription_type
    
    # Créer un paiement pour l'abonnement sélectionné
    try:
        payment_data = await payment_service.create_payment(
            user_id=context.user_data["user_id"],
            subscription_type=subscription_type
        )
        
        # Stocker l'ID de paiement dans le contexte
        context.user_data["payment_id"] = payment_data["id"]
        context.user_data["payment_amount"] = payment_data["amount"]
        
        # Créer un bouton avec l'URL de paiement
        keyboard = [
            [InlineKeyboardButton("Payer Maintenant", url=payment_data["payment_url"])],
            [InlineKeyboardButton("J'ai Terminé le Paiement", callback_data="check_payment")]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        # Afficher le message de paiement
        if subscription_type == "monthly":
            plan_text = "mensuel"
        elif subscription_type == "annual":
            plan_text = "annuel"
        else:
            plan_text = "à vie"
            
        await query.edit_message_text(
            f"Vous avez sélectionné le plan {plan_text} à ${payment_data['amount']}.\n\n"
            "Veuillez cliquer sur le bouton ci-dessous pour effectuer votre paiement. "
            "Après avoir terminé, cliquez sur 'J'ai Terminé le Paiement' pour vérifier.",
            reply_markup=reply_markup
        )
        
        return PAYMENT_CHECK
        
    except Exception as e:
        logger.error(f"Erreur de création de paiement: {e}")
        await query.edit_message_text(
            "Désolé, une erreur s'est produite lors de la création de votre paiement. "
            "Veuillez réessayer plus tard ou contacter le support."
        )
        return ConversationHandler.END

async def check_payment(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Vérifier si le paiement a été effectué avec succès."""
    query = update.callback_query
    await query.answer()
    
    user_id = context.user_data["user_id"]
    payment_id = context.user_data["payment_id"]
    subscription_type = context.user_data["subscription_type"]
    
    try:
        # Vérifier le statut du paiement avec le service de paiement
        payment_status = await payment_service.check_payment(payment_id)
        
        if payment_status["status"] == "completed":
            # Le paiement est réussi, continuer vers la sélection du template
            if subscription_type == "monthly":
                period_text = "un mois"
                end_date = datetime.now() + timedelta(days=30)
                end_date_str = end_date.strftime("%d/%m/%Y")
                expiry_text = f"L'abonnement expirera le: {end_date_str}"
            elif subscription_type == "annual":
                period_text = "un an"
                end_date = datetime.now() + timedelta(days=365)
                end_date_str = end_date.strftime("%d/%m/%Y")
                expiry_text = f"L'abonnement expirera le: {end_date_str}"
            else:  # lifetime
                period_text = "à vie"
                expiry_text = "Cet abonnement n'expire jamais."
            
            await query.edit_message_text(
                "✅ Paiement réussi! Votre abonnement est maintenant actif.\n\n"
                f"Vous avez accès au service pour {period_text}.\n"
                f"{expiry_text}\n\n"
                "Continuons avec votre email personnalisé."
            )
            
            # Attendre un moment pour que l'utilisateur puisse lire le message
            await query.message.reply_text(
                "Maintenant, choisissons un template pour votre email."
            )
            
            return await show_template_selection(update, context)
            
        else:
            # Le paiement n'est pas encore terminé
            keyboard = [
                [InlineKeyboardButton("Réessayer", url=payment_status["payment_url"])],
                [InlineKeyboardButton("Vérifier à Nouveau", callback_data="check_payment")],
                [InlineKeyboardButton("Annuler", callback_data="cancel_payment")]
            ]
            reply_markup = InlineKeyboardMarkup(keyboard)
            
            await query.edit_message_text(
                "Le paiement n'est pas encore terminé. Veuillez terminer le paiement ou vérifier à nouveau plus tard.",
                reply_markup=reply_markup
            )
            
            return PAYMENT_CHECK
            
    except Exception as e:
        logger.error(f"Erreur de vérification de paiement: {e}")
        await query.edit_message_text(
            "Désolé, une erreur s'est produite lors de la vérification de votre paiement. "
            "Veuillez contacter le support."
        )
        return ConversationHandler.END

async def cancel_payment(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Annuler le processus de paiement."""
    query = update.callback_query
    await query.answer()
    
    await query.edit_message_text(
        "Processus de paiement annulé. Tapez /start pour réessayer quand vous serez prêt."
    )
    
    return ConversationHandler.END

async def show_template_selection(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Afficher les templates d'email disponibles."""
    # Récupérer les templates par défaut
    templates = await template_service.get_templates()
    
    # Récupérer les templates personnalisés de l'utilisateur
    user_id = context.user_data["user_id"]
    custom_templates = await template_service.get_custom_templates(user_id)
    
    # Combinaison de tous les templates disponibles
    all_templates = []
    
    if templates:
        all_templates.extend([
            [InlineKeyboardButton(t["name"], callback_data=f"template_{t['id']}")]
            for t in templates
        ])
    
    if custom_templates:
        all_templates.extend([
            [InlineKeyboardButton(f"📝 {t['name']} (Personnalisé)", callback_data=f"custom_template_{t['id']}")]
            for t in custom_templates
        ])
    
    # Ajouter un bouton pour créer un nouveau template personnalisé
    all_templates.append([InlineKeyboardButton("➕ Créer un nouveau template", callback_data="create_template")])
    
    reply_markup = InlineKeyboardMarkup(all_templates)
    
    message = "📋 Veuillez sélectionner un template d'email:"
    
    if hasattr(update, 'callback_query') and update.callback_query:
        await update.callback_query.edit_message_text(text=message, reply_markup=reply_markup)
    else:
        await update.message.reply_text(text=message, reply_markup=reply_markup)
    
    return TEMPLATE_SELECTION

async def template_selected(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Gérer la sélection du template."""
    query = update.callback_query
    await query.answer()
    
    data = query.data
    
    if data.startswith("template_"):
        # Template standard sélectionné
        template_id = data.split("_")[1]
        template = await template_service.get_template(template_id)
        context.user_data["is_custom_template"] = False
    elif data.startswith("custom_template_"):
        # Template personnalisé sélectionné
        template_id = data.split("_")[2]
        user_id = context.user_data["user_id"]
        template = await template_service.get_custom_template(user_id, template_id)
        context.user_data["is_custom_template"] = True
    else:
        # Création d'un nouveau template
        await query.edit_message_text(
            "Vous avez choisi de créer un nouveau template personnalisé.\n\n"
            "Veuillez entrer un nom pour votre template:"
        )
        return CUSTOM_TEMPLATE_NAME
    
    if not template:
        await query.edit_message_text("Template introuvable. Veuillez réessayer.")
        return await show_template_selection(update, context)
    
    context.user_data["template"] = template
    
    # Extraire tous les placeholders du template
    placeholders = template_service.extract_placeholders(template["content"])
    context.user_data["placeholders"] = list(placeholders)
    context.user_data["placeholder_values"] = {}
    context.user_data["current_placeholder_index"] = 0
    
    # S'il n'y a pas de placeholders, aller directement à l'aperçu
    if not placeholders:
        return await prepare_email_preview(update, context)
    
    # Sinon, commencer à recueillir les valeurs des champs dynamiques
    return await collect_dynamic_fields(update, context)

async def create_custom_template_name(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Recueillir le nom du template personnalisé."""
    name = update.message.text
    context.user_data["custom_template_name"] = name
    
    await update.message.reply_text(
        f"Nom du template: {name}\n\n"
        "Maintenant, veuillez entrer l'objet de l'email:"
    )
    
    return CUSTOM_TEMPLATE_SUBJECT

async def create_custom_template_subject(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Recueillir l'objet du template personnalisé."""
    subject = update.message.text
    context.user_data["custom_template_subject"] = subject
    
    await update.message.reply_text(
        f"Objet de l'email: {subject}\n\n"
        "Maintenant, veuillez entrer le contenu HTML de votre template.\n\n"
        "Vous pouvez utiliser des placeholders au format {nom} qui seront remplacés lors de l'envoi.\n"
        "Par exemple: Bonjour {nom}, votre commande #{numero} est prête."
    )
    
    return CUSTOM_TEMPLATE_CONTENT

async def create_custom_template_content(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Recueillir le contenu du template personnalisé."""
    content = update.message.text
    user_id = context.user_data["user_id"]
    name = context.user_data["custom_template_name"]
    subject = context.user_data["custom_template_subject"]
    
    # Sauvegarder le template personnalisé
    template_id = await template_service.add_custom_template(
        user_id=user_id,
        name=name,
        subject=subject,
        content=content
    )
    
    # Récupérer le template complet
    template = await template_service.get_custom_template(user_id, template_id)
    context.user_data["template"] = template
    context.user_data["is_custom_template"] = True
    
    # Extraire tous les placeholders du template
    placeholders = template_service.extract_placeholders(content)
    context.user_data["placeholders"] = list(placeholders)
    context.user_data["placeholder_values"] = {}
    context.user_data["current_placeholder_index"] = 0
    
    await update.message.reply_text(
        f"✅ Template '{name}' créé avec succès!\n\n"
        f"Objet: {subject}\n\n"
        f"Placeholders détectés: {', '.join(placeholders) if placeholders else 'Aucun'}"
    )
    
    # S'il n'y a pas de placeholders, aller directement à l'aperçu
    if not placeholders:
        return await prepare_email_preview(update, context)
    
    # Sinon, commencer à recueillir les valeurs des champs dynamiques
    return await collect_dynamic_fields(update, context)

async def collect_dynamic_fields(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Recueillir les valeurs pour les champs dynamiques du template."""
    placeholders = context.user_data["placeholders"]
    current_index = context.user_data["current_placeholder_index"]
    
    if current_index >= len(placeholders):
        # Tous les placeholders ont été traités, passer à l'email
        return await prepare_email_preview(update, context)
    
    current_placeholder = placeholders[current_index]
    
    message = f"Veuillez entrer la valeur pour le champ: {current_placeholder}"
    
    if hasattr(update, 'callback_query') and update.callback_query:
        await update.callback_query.edit_message_text(text=message)
    else:
        await update.message.reply_text(text=message)
    
    return DYNAMIC_FIELDS

async def process_dynamic_field(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Traiter la valeur entrée pour un champ dynamique."""
    value = update.message.text
    placeholders = context.user_data["placeholders"]
    current_index = context.user_data["current_placeholder_index"]
    current_placeholder = placeholders[current_index]
    
    # Sauvegarder la valeur
    context.user_data["placeholder_values"][current_placeholder] = value
    
    # Passer au placeholder suivant
    context.user_data["current_placeholder_index"] = current_index + 1
    
    # Vérifier s'il reste des placeholders à traiter
    if current_index + 1 < len(placeholders):
        return await collect_dynamic_fields(update, context)
    
    # Tous les placeholders ont été traités
    await update.message.reply_text(
        "Toutes les valeurs ont été collectées. Préparation de l'aperçu de l'email..."
    )
    
    return await prepare_email_preview(update, context)

async def prepare_email_preview(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Préparer et afficher l'aperçu de l'email."""
    # Collecter l'adresse email du destinataire
    await update.message.reply_text(
        "Veuillez entrer l'adresse email du destinataire:"
    )
    
    context.user_data["collecting_email"] = True
    return EMAIL_PREVIEW

async def process_recipient_email(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Traiter l'adresse email du destinataire et afficher l'aperçu de l'email."""
    email = update.message.text
    
    # Validation basique de l'email
    if "@" not in email or "." not in email:
        await update.message.reply_text(
            "Format d'email invalide. Veuillez entrer une adresse email valide:"
        )
        return EMAIL_PREVIEW
    
    context.user_data["recipient_email"] = email
    context.user_data["collecting_email"] = False
    
    template = context.user_data["template"]
    replacements = context.user_data.get("placeholder_values", {})
    
    # Générer l'aperçu avec substitution des champs
    preview = template_service.generate_email_content(template, replacements)
    
    context.user_data["email_content"] = preview
    
    # Envoyer l'aperçu avec les boutons envoyer/modifier
    keyboard = [
        [
            InlineKeyboardButton("Envoyer l'Email", callback_data="send_email"),
            InlineKeyboardButton("Modifier", callback_data="edit_fields"),
        ]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await update.message.reply_text(
        f"📧 *Aperçu de l'Email*\n\n"
        f"*À:* {email}\n"
        f"*Objet:* {template['subject']}\n\n"
        f"*Contenu:*\n{preview[:500]}...\n\n"  # Limiter l'aperçu pour éviter les messages trop longs
        "Veuillez vérifier l'email ci-dessus et sélectionner une action:",
        reply_markup=reply_markup,
        parse_mode="Markdown",
    )
    
    return EMAIL_SENDING

async def send_email(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Envoyer l'email en utilisant le service configuré."""
    query = update.callback_query
    await query.answer()
    
    template = context.user_data["template"]
    recipient_email = context.user_data["recipient_email"]
    email_content = context.user_data["email_content"]
    placeholders = context.user_data.get("placeholder_values", {})
    
    # Déterminer le nom du destinataire s'il est disponible
    recipient_name = placeholders.get("nom", "")
    if not recipient_name:
        recipient_name = placeholders.get("name", "Destinataire")
    
    await query.edit_message_text("Envoi de l'email... Veuillez patienter.")
    
    try:
        result = await email_service.send_email(
            recipient_email=recipient_email,
            subject=template["subject"],
            content=email_content,
            sender_name=template.get("sender_name", "G4mailsender"),
        )
        
        # Journaliser l'envoi d'email
        is_custom = context.user_data.get("is_custom_template", False)
        await db.log_email_sent(
            user_id=context.user_data["user_id"],
            template_id=template["id"],
            recipient_email=recipient_email,
            recipient_name=recipient_name,
            is_custom_template=is_custom
        )
        
        # Message de succès avec options pour envoyer un autre ou quitter
        keyboard = [
            [
                InlineKeyboardButton("Envoyer un Autre Email", callback_data="send_another"),
                InlineKeyboardButton("Quitter", callback_data="exit"),
            ]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        await query.edit_message_text(
            "✅ Email envoyé avec succès!\n\n"
            f"Destinataire: {recipient_name} ({recipient_email})\n"
            f"Template: {template['name']}\n\n"
            "Que souhaitez-vous faire ensuite?",
            reply_markup=reply_markup,
        )
        
    except Exception as e:
        logger.error(f"Erreur d'envoi d'email: {e}")
        
        # Message d'erreur avec option de réessayer
        keyboard = [
            [
                InlineKeyboardButton("Réessayer", callback_data="retry_send"),
                InlineKeyboardButton("Modifier les Détails", callback_data="edit_fields"),
            ]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        await query.edit_message_text(
            "❌ Échec de l'envoi de l'email. Veuillez réessayer ou modifier vos détails.",
            reply_markup=reply_markup,
        )
    
    return EMAIL_SENDING

async def process_sending_choice(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Traiter le choix de l'utilisateur après l'envoi de l'email."""
    query = update.callback_query
    await query.answer()
    
    choice = query.data
    
    if choice == "send_another":
        # Réinitialiser certaines données du contexte
        context.user_data.pop("template", None)
        context.user_data.pop("recipient_email", None)
        context.user_data.pop("email_content", None)
        context.user_data.pop("placeholder_values", None)
        context.user_data.pop("placeholders", None)
        
        return await show_template_selection(update, context)
    elif choice == "retry_send":
        return await send_email(update, context)
    elif choice == "edit_fields":
        # Revenir à la collecte des champs dynamiques
        context.user_data["current_placeholder_index"] = 0
        await query.edit_message_text(
            "Revenons aux champs de votre email. Nous allons les reprendre un par un."
        )
        return await collect_dynamic_fields(update, context)
    elif choice == "exit":
        await query.edit_message_text(
            "Merci d'utiliser G4mailsender! Tapez /start pour recommencer."
        )
        return ConversationHandler.END
    
    return ConversationHandler.END

async def admin_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Gérer les commandes administrateur."""
    user_id = update.effective_user.id
    
    # Vérifier si l'utilisateur est administrateur
    if str(user_id) not in config.ADMIN_USER_IDS:
        await update.message.reply_text("Vous n'avez pas la permission d'utiliser les commandes d'administration.")
        return
    
    # Traiter différentes commandes d'administration
    command_parts = update.message.text.split()
    admin_cmd = command_parts[0].lower()
    
    if admin_cmd == "/stats":
        # Afficher les statistiques
        stats = await db.get_stats()
        await update.message.reply_text(
            f"📊 *Statistiques*\n\n"
            f"Total des utilisateurs: {stats['total_users']}\n"
            f"Abonnements actifs: {stats['active_subscriptions']}\n"
            f"- Mensuels: {stats['monthly_subscriptions']}\n"
            f"- Annuels: {stats['annual_subscriptions']}\n"
            f"- À vie: {stats['lifetime_subscriptions']}\n"
            f"Total des emails envoyés: {stats['emails_sent']}\n"
            f"Emails envoyés aujourd'hui: {stats['emails_sent_today']}",
            parse_mode="Markdown"
        )
    
    elif admin_cmd == "/addtemplate" and len(command_parts) > 1:
        # Format: /addtemplate <nom>|<objet>|<contenu>
        template_data = " ".join(command_parts[1:])
        try:
            name, subject, content = template_data.split("|", 2)
            template_id = await template_service.add_template(name, subject, content)
            await update.message.reply_text(f"Template ajouté avec ID: {template_id}")
        except ValueError:
            await update.message.reply_text(
                "Format invalide. Utilisez: /addtemplate nom|objet|contenu"
            )
    
    elif admin_cmd == "/templates":
        # Lister tous les templates
        templates = await template_service.get_templates()
        if not templates:
            await update.message.reply_text("Aucun template trouvé.")
            return
        
        template_list = "\n\n".join([
            f"*{t['name']}* (ID: {t['id']})\nObjet: {t['subject']}"
            for t in templates
        ])
        
        await update.message.reply_text(
            f"📝 *Templates Disponibles*\n\n{template_list}",
            parse_mode="Markdown"
        )
    
    elif admin_cmd == "/help":
        # Aide administrateur
        await update.message.reply_text(
            "🔑 *Commandes Administrateur*\n\n"
            "/stats - Afficher les statistiques d'utilisation\n"
            "/templates - Lister tous les templates\n"
            "/addtemplate nom|objet|contenu - Ajouter un nouveau template\n"
            "/subscriptions - Lister les abonnements actifs\n"
            "/extend user_id jours - Prolonger l'abonnement d'un utilisateur",
            parse_mode="Markdown"
        )

async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Afficher les informations d'aide."""
    await update.message.reply_text(
        "🤖 *Aide G4mailsender*\n\n"
        "Ce bot vous permet d'envoyer des emails personnalisés en utilisant des templates pré-faits.\n\n"
        "*Commandes:*\n"
        "/start - Commencer à utiliser le bot\n"
        "/help - Afficher ce message d'aide\n"
        "/status - Vérifier le statut de votre abonnement\n\n"
        "Pour utiliser ce service, vous avez besoin d'un abonnement actif.\n"
        f"Options d'abonnement disponibles:\n"
        f"- Mensuel: ${config.SUBSCRIPTION_PRICE_MONTHLY}/mois\n"
        f"- Annuel: ${config.SUBSCRIPTION_PRICE_ANNUAL}/an\n"
        f"- À vie: ${config.SUBSCRIPTION_PRICE_LIFETIME} (paiement unique)",
        parse_mode="Markdown"
    )

async def status_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Afficher le statut d'abonnement de l'utilisateur."""
    user_id = update.effective_user.id
    user_data = await db.get_user(user_id)
    
    if not user_data:
        await update.message.reply_text("Votre compte n'a pas été trouvé. Veuillez utiliser /start pour configurer votre compte.")
        return
    
    if user_data.get("subscription_active", False):
        subscription_type = user_data.get("subscription_type", "")
        end_date = user_data.get("subscription_end_date")
        
        if subscription_type == "lifetime":
            status_message = "Vous avez un abonnement *à vie*. Il n'expire jamais."
            days_left = "∞"
        else:
            if isinstance(end_date, datetime):
                end_date_str = end_date.strftime("%d/%m/%Y")
                delta = end_date - datetime.now()
                days_left = max(0, delta.days)
            else:
                end_date_str = "Inconnue"
                days_left = "Inconnu"
            
            if subscription_type == "monthly":
                type_text = "mensuel"
            elif subscription_type == "annual":
                type_text = "annuel"
            else:
                type_text = subscription_type
                
            status_message = (
                f"Votre abonnement {type_text} est *actif*.\n"
                f"Date d'expiration: {end_date_str}\n"
                f"Jours restants: {days_left}"
            )
        
        await update.message.reply_text(
            f"✅ *Statut d'Abonnement*\n\n"
            f"{status_message}\n\n"
            f"Emails envoyés ce mois-ci: {user_data.get('emails_sent_month', 0)}",
            parse_mode="Markdown"
        )
        
        # Ajouter un bouton de renouvellement si moins de 7 jours restants
        if subscription_type != "lifetime" and isinstance(days_left, int) and days_left < 7:
            keyboard = [[InlineKeyboardButton("Renouveler l'Abonnement", callback_data="renew_subscription")]]
            reply_markup = InlineKeyboardMarkup(keyboard)
            
            await update.message.reply_text(
                "Votre abonnement expirera bientôt. Souhaitez-vous le renouveler?",
                reply_markup=reply_markup
            )
    else:
        keyboard = [[InlineKeyboardButton("S'abonner Maintenant", callback_data="subscribe_now")]]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        await update.message.reply_text(
            "❌ *Statut d'Abonnement*\n\n"
            "Vous n'avez pas d'abonnement actif.\n\n"
            "Options d'abonnement disponibles:\n"
            f"- Mensuel: ${config.SUBSCRIPTION_PRICE_MONTHLY}/mois\n"
            f"- Annuel: ${config.SUBSCRIPTION_PRICE_ANNUAL}/an\n"
            f"- À vie: ${config.SUBSCRIPTION_PRICE_LIFETIME} (paiement unique)",
            parse_mode="Markdown",
            reply_markup=reply_markup
        )

async def handle_subscription_buttons(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Gérer les boutons liés aux abonnements depuis la commande /status."""
    query = update.callback_query
    await query.answer()
    
    if query.data == "subscribe_now":
        # Rediriger vers la sélection d'abonnement
        return await show_subscription_options(update, context)
    elif query.data == "renew_subscription":
        # Rediriger vers la sélection d'abonnement pour renouvellement
        await query.edit_message_text(
            "Choisissez un plan pour renouveler votre abonnement."
        )
        return await show_subscription_options(update, context)
    
    return SUBSCRIPTION_SELECTION

def main() -> None:
    """Démarrer le bot."""
    # Créer l'Application
    application = Application.builder().token(config.TELEGRAM_API_TOKEN).build()
    
    # Ajouter le gestionnaire de conversation
    conv_handler = ConversationHandler(
        entry_points=[CommandHandler("start", start)],
        states={
            SUBSCRIPTION_SELECTION: [
                CallbackQueryHandler(
                    handle_subscription_selection, 
                    pattern="^subscribe_(monthly|annual|lifetime)$"
                ),
            ],
            PAYMENT_CHECK: [
                CallbackQueryHandler(check_payment, pattern="^check_payment$"),
                CallbackQueryHandler(cancel_payment, pattern="^cancel_payment$"),
            ],
            TEMPLATE_SELECTION: [
                CallbackQueryHandler(template_selected, pattern="^template_"),
                CallbackQueryHandler(template_selected, pattern="^custom_template_"),
                CallbackQueryHandler(template_selected, pattern="^create_template$"),
            ],
            CUSTOM_TEMPLATE_NAME: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, create_custom_template_name),
            ],
            CUSTOM_TEMPLATE_SUBJECT: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, create_custom_template_subject),
            ],
            CUSTOM_TEMPLATE_CONTENT: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, create_custom_template_content),
            ],
            DYNAMIC_FIELDS: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, process_dynamic_field),
            ],
            EMAIL_PREVIEW: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, process_recipient_email),
            ],
            EMAIL_SENDING: [
                CallbackQueryHandler(send_email, pattern="^send_email$"),
                CallbackQueryHandler(
                    lambda u, c: collect_dynamic_fields(u, c), pattern="^edit_fields$"
                ),
                CallbackQueryHandler(process_sending_choice),
            ],
        },
        fallbacks=[CommandHandler("start", start)],
    )
    
    application.add_handler(conv_handler)
    
    # Gestionnaire pour les boutons d'abonnement depuis la commande status
    application.add_handler(
        CallbackQueryHandler(
            handle_subscription_buttons, 
            pattern="^(subscribe_now|renew_subscription)$"
        )
    )
    
    # Commandes administrateur
    application.add_handler(CommandHandler("stats", admin_command))
    application.add_handler(CommandHandler("templates", admin_command))
    application.add_handler(CommandHandler("addtemplate", admin_command))
    
    # Autres commandes
    application.add_handler(CommandHandler("help", help_command))
    application.add_handler(CommandHandler("status", status_command))
    
    # Démarrer le Bot
    application.run_polling()

if __name__ == "__main__":
    main()