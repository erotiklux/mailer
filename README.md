# G4mailsender - Bot Telegram d'envoi d'emails

Un bot Telegram basé en Python qui permet aux utilisateurs d'envoyer des emails avec ID d'expéditeur personnalisé en utilisant des templates prédéfinis. Le service nécessite un abonnement mensuel, annuel ou à vie traité via Oxapay.

## Fonctionnalités

- Interface Telegram en français pour envoyer des emails personnalisés
- Templates d'email prêts à l'emploi avec fonctionnalité de remplacement de nom
- ID d'expéditeur personnalisé pour l'envoi d'emails personnalisés
- Traitement des paiements d'abonnement via Oxapay (mensuel, annuel, à vie)
- Authentification des utilisateurs et gestion des abonnements
- Sélection de templates via une interface conversationnelle
- Suivi de livraison et confirmation d'email
- Fonctionnalités administratives pour gérer les templates et les utilisateurs
- Possibilité d'ajouter des templates personnalisés par utilisateur

## Instructions d'installation

### Prérequis

- Python 3.8 ou supérieur
- Base de données MongoDB
- Token API de bot Telegram 
- Compte de service email SMTP
- Compte marchand Oxapay

### Installation

1. Clonez ce dépôt:
   ```
   git clone https://github.com/votrepseudo/g4mailsender.git
   cd g4mailsender
   ```

2. Installez les dépendances requises:
   ```
   pip install -r requirements.txt
   ```

3. Créez un fichier `.env` basé sur `.env.example` fourni:
   ```
   cp .env.example .env
   ```

4. Remplissez les variables d'environnement requises dans le fichier `.env`:
   - Token API Telegram (obtenu auprès de [@BotFather](https://t.me/BotFather))
   - Identifiants du service email
   - Clés API Oxapay et ID marchand
   - Chaîne de connexion MongoDB
   - IDs utilisateur administrateur

### Exécution du Bot

Démarrez le bot principal:
```
python bot.py
```

Démarrez le serveur webhook (pour les notifications de paiement):
```
python webhook.py
```

## Utilisation

### Pour les Utilisateurs

1. Démarrez une conversation avec le bot en utilisant la commande `/start`
2. Si vous n'avez pas d'abonnement actif, suivez le processus de paiement
3. Une fois abonné, sélectionnez un template d'email parmi les options disponibles ou créez votre propre template
4. Entrez les valeurs pour les champs dynamiques (comme le nom du destinataire)
5. Entrez l'adresse email du destinataire
6. Vérifiez l'aperçu de l'email et envoyez quand vous êtes prêt

### Pour les Administrateurs

Utilisez ces commandes pour gérer le bot:

- `/stats` - Afficher les statistiques d'utilisation
- `/templates` - Lister tous les templates
- `/addtemplate nom|objet|contenu` - Ajouter un nouveau template
- `/subscriptions` - Lister les abonnements actifs
- `/extend user_id jours` - Prolonger l'abonnement d'un utilisateur

## Structure du Projet

- `bot.py` - Implémentation principale du bot Telegram
- `webhook.py` - Gestionnaire de webhook pour les notifications de paiement
- `config.py` - Configuration et variables d'environnement
- `database.py` - Opérations de base de données MongoDB
- `email_service.py` - Fonctionnalité d'envoi d'email
- `payment_service.py` - Traitement des paiements Oxapay
- `template_service.py` - Gestion des templates d'email

## Licence

Ce projet est sous licence MIT - voir le fichier LICENSE pour plus de détails.