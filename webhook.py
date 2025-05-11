#!/usr/bin/env python3
"""
Gestionnaire de webhook pour G4mailsender Bot.
Traite les notifications de paiement Oxapay.
"""

import json
import logging
import os
from typing import Dict, Any

from dotenv import load_dotenv
from fastapi import FastAPI, Request, HTTPException, Header
from pydantic import BaseModel

from config import Config
from database import Database
from payment_service import PaymentService

# Charger les variables d'environnement
load_dotenv()

# Configurer le logging
logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s", level=logging.INFO
)
logger = logging.getLogger(__name__)

# Initialiser l'application FastAPI
app = FastAPI(title="G4mailsender Webhooks")

# Initialiser les services
config = Config()
db = Database(config.MONGODB_URI)
payment_service = PaymentService(config, db)


class OxapayWebhook(BaseModel):
    """Modèle de charge utile de webhook Oxapay."""
    
    order_id: str
    status: str
    amount: float
    currency: str
    custom: Dict[str, Any]


@app.post("/webhook/oxapay")
async def oxapay_webhook(
    request: Request,
    x_oxapay_signature: str = Header(None),
):
    """
    Gérer les notifications de webhook Oxapay.
    
    Ce point de terminaison traite les mises à jour de statut de paiement d'Oxapay.
    """
    try:
        # Obtenir le corps de la requête brut
        body = await request.body()
        payload = json.loads(body)
        
        # Vérifier la signature du webhook
        if not payment_service.verify_webhook_signature(payload, x_oxapay_signature):
            logger.warning("Signature de webhook non valide")
            raise HTTPException(status_code=401, detail="Signature non valide")
        
        # Traiter le webhook
        result = await payment_service.process_webhook(payload, x_oxapay_signature)
        
        if result["status"] == "error":
            logger.error(f"Erreur de traitement de webhook: {result['message']}")
            raise HTTPException(status_code=400, detail=result["message"])
        
        return {"status": "success"}
        
    except json.JSONDecodeError:
        logger.error("Charge utile JSON non valide")
        raise HTTPException(status_code=400, detail="Charge utile JSON non valide")
    
    except Exception as e:
        logger.error(f"Erreur de webhook: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


if __name__ == "__main__":
    import uvicorn
    
    # Démarrer le serveur webhook
    uvicorn.run(app, host="0.0.0.0", port=8000)