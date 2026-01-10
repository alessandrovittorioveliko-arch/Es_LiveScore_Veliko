import asyncio
import json
import random
import tornado.web
import tornado.websocket
from datetime import datetime

# ============================================================================
# CONFIGURAZIONE INIZIALE DEI MATCH
# ============================================================================
# Qui definiamo i 5 match con i loro dati iniziali
# Ogni match ha: id, squadre, stato (scheduled/live/finished), minuto, punteggio, eventi
matches = {
    "1": {
        "id": "1",
        "home": "Inter",
        "away": "Milan",
        "status": "live",      # Partita in corso
        "minute": 23,          # Minuto attuale
        "score": {"home": 1, "away": 0},
        "events": [
            {"minute": 12, "type": "goal", "team": "home", "player": "Lautaro Martinez"}
        ]
    },
    "2": {
        "id": "2",
        "home": "Juventus",
        "away": "Napoli",
        "status": "live",
        "minute": 67,
        "score": {"home": 2, "away": 2},
        "events": [
            {"minute": 15, "type": "goal", "team": "home", "player": "Vlahovic"},
            {"minute": 34, "type": "goal", "team": "away", "player": "Osimhen"},
            {"minute": 45, "type": "yellow_card", "team": "home", "player": "Bremer"},
            {"minute": 58, "type": "goal", "team": "away", "player": "Kvaratskhelia"},
            {"minute": 62, "type": "goal", "team": "home", "player": "Chiesa"}
        ]
    },
    "3": {
        "id": "3",
        "home": "Roma",
        "away": "Lazio",
        "status": "live",
        "minute": 12,
        "score": {"home": 0, "away": 0},
        "events": []
    },
    "4": {
        "id": "4",
        "home": "Atalanta",
        "away": "Fiorentina",
        "status": "scheduled",  # Partita programmata (non ancora iniziata)
        "minute": 0,
        "score": {"home": 0, "away": 0},
        "events": []
    },
    "5": {
        "id": "5",
        "home": "Bologna",
        "away": "Torino",
        "status": "finished",   # Partita terminata
        "minute": 90,
        "score": {"home": 3, "away": 1},
        "events": [
            {"minute": 18, "type": "goal", "team": "home", "player": "Zirkzee"},
            {"minute": 35, "type": "goal", "team": "home", "player": "Orsolini"},
            {"minute": 56, "type": "goal", "team": "away", "player": "Zapata"},
            {"minute": 78, "type": "red_card", "team": "away", "player": "Rodriguez"},
            {"minute": 85, "type": "goal", "team": "home", "player": "Ferguson"}
        ]
    }
}
