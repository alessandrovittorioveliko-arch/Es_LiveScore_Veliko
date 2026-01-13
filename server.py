import asyncio
import json
import random
import tornado.web
import tornado.websocket
from datetime import datetime

# ============================================================================
# CARICAMENTO E NORMALIZZAZIONE DATABASE SQUADRE
# ============================================================================
def flatten_players(team):
    """Converte players da dict per ruoli a lista piatta"""
    if isinstance(team.get("players"), dict):
        all_players = []
        for role, player_list in team["players"].items():
            all_players.extend(player_list)
        team["players"] = all_players[:11]  # Massimo 11 titolari
    return team

with open('teams.json', 'r', encoding='utf-8') as f:
    teams_db = json.load(f)['teams']

# NORMALIZZA TUTTE LE SQUADRE
teams_db = [flatten_players(team) for team in teams_db]

print(f"✅ Caricate {len(teams_db)} squadre con {len(teams_db[0]['players'])} giocatori ciascuna")


# ============================================================================
# CONFIGURAZIONE PROBABILITÀ EVENTI (realistiche per il calcio)
# ============================================================================
EVENT_PROBABILITIES = {
    "goal": 0.03,              # 3% per minuto (circa 2-3 goal per partita)
    "yellow_card": 0.025,      # 2.5% per minuto (circa 2-3 cartellini gialli)
    "red_card": 0.003,         # 0.3% per minuto (raro, circa 1 ogni 3-4 partite)
    "substitution": 0.015,     # 1.5% per minuto (concentrato dopo il 60°)
    "corner": 0.08,            # 8% per minuto (circa 7-10 corner per partita)
    "offside": 0.04,           # 4% per minuto (4-5 fuorigioco)
    "penalty": 0.004,          # 0.4% per minuto (raro)
    "injury": 0.008            # 0.8% per minuto (infortuni occasionali)
}

# Probabilità aumentate in certi periodi
PERIOD_MULTIPLIERS = {
    "early": (1, 15, 0.7),      # Inizio: eventi ridotti (studio tattico)
    "normal": (16, 75, 1.0),    # Gioco normale
    "final": (76, 90, 1.4),     # Finale: eventi aumentati (pressing)
    "injury_time": (91, 95, 1.6) # Recupero: massima intensità
}

# ============================================================================
# GENERAZIONE CASUALE DEI MATCH
# ============================================================================
def generate_random_matches(num_matches=5):
    """
    Genera match casuali selezionando squadre random dal database.
    """
    matches = {}
    available_teams = teams_db.copy()
    random.shuffle(available_teams)
    
    match_statuses = ["live", "live", "live", "scheduled", "finished"]
    
    for i in range(num_matches):
        if len(available_teams) < 2:
            available_teams = teams_db.copy()
            random.shuffle(available_teams)
        
        home_team = available_teams.pop()
        away_team = available_teams.pop()
        
        status = match_statuses[i] if i < len(match_statuses) else "live"
        
        # Genera stato iniziale basato sullo status
        if status == "live":
            minute = random.randint(1, 85)
            home_score, away_score, events = simulate_match_history(
                home_team, away_team, minute
            )
        elif status == "finished":
            minute = 90
            home_score, away_score, events = simulate_match_history(
                home_team, away_team, 90
            )
        else:  # scheduled
            minute = 0
            home_score = 0
            away_score = 0
            events = []
        
        match_id = str(i + 1)
        matches[match_id] = {
            "id": match_id,
            "home": home_team["name"],
            "away": away_team["name"],
            "home_data": home_team,
            "away_data": away_team,
            "status": status,
            "minute": minute,
            "score": {"home": home_score, "away": away_score},
            "events": events,
            "half": 1 if minute <= 45 else 2,
            "injury_time": 0
        }
    
    return matches


def simulate_match_history(home_team, away_team, current_minute):
    """
    Simula la storia di un match fino al minuto corrente.
    Genera eventi realistici basati sulle probabilità e sulla forza delle squadre.
    """
    home_score = 0
    away_score = 0
    events = []
    
    # Calcola bias in base alla differenza di forza
    strength_diff = home_team["strength"] - away_team["strength"]
    home_bias = 0.5 + (strength_diff / 200)  # Da 0.3 a 0.7 circa
    
    for minute in range(1, current_minute + 1):
        # Determina moltiplicatore del periodo
        multiplier = get_period_multiplier(minute)
        
        # Genera eventi casuali
        for event_type, base_prob in EVENT_PROBABILITIES.items():
            adjusted_prob = base_prob * multiplier
            
            if random.random() < adjusted_prob:
                event = generate_event(
                    event_type, minute, home_team, away_team, 
                    home_bias, home_score, away_score
                )
                
                if event:
                    events.append(event)
                    
                    # Aggiorna punteggio se è un goal
                    if event_type == "goal" and event.get("scored"):
                        if event["team"] == "home":
                            home_score += 1
                        else:
                            away_score += 1
                    
                    # Penalty trasformato in goal
                    if event_type == "penalty" and event.get("scored"):
                        if event["team"] == "home":
                            home_score += 1
                        else:
                            away_score += 1
    
    return home_score, away_score, events


def get_period_multiplier(minute):
    """
    Restituisce il moltiplicatore di probabilità in base al minuto.
    """
    for period_name, (start, end, mult) in PERIOD_MULTIPLIERS.items():
        if start <= minute <= end:
            return mult
    return 1.0


def generate_event(event_type, minute, home_team, away_team, home_bias, home_score, away_score):
    """
    Genera un evento specifico con dati realistici.
    """
    # Determina quale squadra causa l'evento (con bias)
    team = "home" if random.random() < home_bias else "away"
    team_data = home_team if team == "home" else away_team
    team_name = team_data["name"]
    
    # Seleziona un giocatore casuale
    player = random.choice(team_data["players"])
    
    event = {
        "minute": minute,
        "type": event_type,
        "team": team,
        "player": player,
        "team_name": team_name
    }
    
    # Dettagli specifici per tipo di evento
    if event_type == "goal":
        event["scored"] = True
        # Tipo di goal
        goal_types = ["tiro", "colpo di testa", "punizione", "contropiede"]
        event["detail"] = random.choice(goal_types)
        
        # Possibile assistente
        if random.random() < 0.7:  # 70% dei goal hanno un assist
            other_players = [p for p in team_data["players"] if p != player]
            event["assist"] = random.choice(other_players)
    
    elif event_type == "penalty":
        # 75% di probabilità di segnare un rigore
        scored = random.random() < 0.75
        event["scored"] = scored
        event["detail"] = "segnato" if scored else "sbagliato"
    
    elif event_type == "substitution":
        # Solo dopo il 45° minuto
        if minute < 45:
            return None
        other_players = [p for p in team_data["players"] if p != player]
        event["player_in"] = random.choice(other_players)
        event["player_out"] = player
    
    elif event_type == "injury":
        event["severity"] = random.choice(["lieve", "moderata", "grave"])
    
    elif event_type == "yellow_card":
        reasons = ["fallo", "simulazione", "proteste", "gioco pericoloso"]
        event["reason"] = random.choice(reasons)
    
    elif event_type == "red_card":
        reasons = ["doppia ammonizione", "fallo grave", "condotta violenta"]
        event["reason"] = random.choice(reasons)
    
    return event


# ============================================================================
# GENERA I MATCH INIZIALI
# ============================================================================
matches = generate_random_matches(5)

# ============================================================================
# SET GLOBALE PER CLIENT WEBSOCKET
# ============================================================================
clients = set()


# ============================================================================
# HANDLER HTTP
# ============================================================================
class MainHandler(tornado.web.RequestHandler):
    def get(self):
        self.render("index.html")


class MatchHandler(tornado.web.RequestHandler):
    def get(self, match_id):
        if match_id not in matches:
            self.set_status(404)
            self.write("Match non trovato")
            return
        self.render("match.html", match_id=match_id)


# ============================================================================
# HANDLER WEBSOCKET
# ============================================================================
class MatchesWebSocket(tornado.websocket.WebSocketHandler):
    def check_origin(self, origin):
        return True
    
    def open(self):
        print("🔌 WebSocket aperto - Nuovo client connesso")
        clients.add(self)
        asyncio.create_task(self.send_initial_state())
    
    async def send_initial_state(self):
        await self.write_message(json.dumps({
            "type": "initial_state",
            "matches": matches
        }))
    
    def on_close(self):
        print("❌ WebSocket chiuso - Client disconnesso")
        clients.remove(self)


# ============================================================================
# SIMULAZIONE MATCH CON PROBABILITÀ REALISTICHE
# ============================================================================
async def simulate_matches():
    """
    Loop che simula l'avanzamento dei match con eventi probabilistici realistici.
    """
    while True:
        await asyncio.sleep(1)  # 1 secondo = 1 minuto di gioco
        
        updated_matches = []
        
        for match_id, match in matches.items():
            if match["status"] != "live":
                continue
            
            # ----------------------------------------------------------------
            # AVANZAMENTO TEMPO
            # ----------------------------------------------------------------
            match["minute"] += 1
            current_minute = match["minute"]
            
            # Gestione fine primo tempo
            if current_minute == 45:
                match["half"] = 1
                match["injury_time"] = random.randint(1, 5)
                print(f"⏱️  Fine 1° tempo: {match['home']} vs {match['away']}")
            
            # Gestione inizio secondo tempo
            if current_minute == 46:
                match["half"] = 2
                match["injury_time"] = 0
            
            # Gestione fine secondo tempo
            if current_minute == 90:
                match["injury_time"] = random.randint(3, 7)
                print(f"⏱️  90° minuto: +{match['injury_time']} di recupero")
            
            # Fine match
            if current_minute >= 90 + match["injury_time"]:
                match["status"] = "finished"
                print(f"🏁 FINE PARTITA: {match['home']} {match['score']['home']}-{match['score']['away']} {match['away']}")
                updated_matches.append(match)
                continue
            
            # ----------------------------------------------------------------
            # GENERAZIONE EVENTI CON PROBABILITÀ REALISTICHE
            # ----------------------------------------------------------------
            multiplier = get_period_multiplier(current_minute)
            
            home_team = match["home_data"]
            away_team = match["away_data"]
            strength_diff = home_team["strength"] - away_team["strength"]
            home_bias = 0.5 + (strength_diff / 200)
            
            for event_type, base_prob in EVENT_PROBABILITIES.items():
                adjusted_prob = base_prob * multiplier
                
                if random.random() < adjusted_prob:
                    event = generate_event(
                        event_type, current_minute, home_team, away_team,
                        home_bias, match["score"]["home"], match["score"]["away"]
                    )
                    
                    if event:
                        match["events"].append(event)
                        
                        # Aggiorna punteggio
                        if event_type == "goal" and event.get("scored"):
                            match["score"][event["team"]] += 1
                            print(f"⚽ GOL! {event['player']} ({event['team_name']}) - "
                                  f"{match['home']} {match['score']['home']}-{match['score']['away']} {match['away']}")
                        
                        elif event_type == "penalty":
                            if event.get("scored"):
                                match["score"][event["team"]] += 1
                                print(f"⚽🎯 RIGORE SEGNATO! {event['player']} ({event['team_name']})")
                            else:
                                print(f"❌ RIGORE SBAGLIATO! {event['player']} ({event['team_name']})")
                        
                        elif event_type == "yellow_card":
                            print(f"🟨 Cartellino giallo: {event['player']} ({event['team_name']})")
                        
                        elif event_type == "red_card":
                            print(f"🟥 CARTELLINO ROSSO! {event['player']} ({event['team_name']})")
                        
                        elif event_type == "corner":
                            print(f"🚩 Corner per {event['team_name']}")
            
            updated_matches.append(match)
        
        # ----------------------------------------------------------------
        # BROADCAST AGGIORNAMENTI
        # ----------------------------------------------------------------
        if updated_matches and clients:
            message = json.dumps({
                "type": "match_update",
                "matches": updated_matches
            })
            
            for client in list(clients):
                try:
                    await client.write_message(message)
                except Exception as e:
                    print(f"Errore invio: {e}")


# ============================================================================
# FUNZIONE PRINCIPALE
# ============================================================================
async def main():
    print("=" * 70)
    print("⚽ SERVER EVENTI SPORTIVI LIVE - SERIE A 2025/2026")
    print("=" * 70)
    
    app = tornado.web.Application(
        [
            (r"/", MainHandler),
            (r"/match/([^/]+)", MatchHandler),
            (r"/ws", MatchesWebSocket),
            (r"/static/(.*)", tornado.web.StaticFileHandler, {"path": "static"}),
        ],
        template_path="templates",
        debug=True
    )
    
    app.listen(8888)
    print("\n✅ Server avviato su http://localhost:8888")
    print("📡 WebSocket disponibile su ws://localhost:8888/ws")
    print("\n📊 MATCH GENERATI:")
    for match_id, match in matches.items():
        status_emoji = {"live": "🔴", "scheduled": "📅", "finished": "✅"}[match["status"]]
        print(f"  {status_emoji} {match['home']} vs {match['away']} - {match['status']}")
    
    print("\n🎲 Sistema di probabilità eventi attivo:")
    print("  • Goal: 3% per minuto (realistico)")
    print("  • Cartellini gialli: 2.5% per minuto")
    print("  • Cartellini rossi: 0.3% per minuto (raro)")
    print("  • Rigori: 0.4% per minuto (raro)")
    print("  • Corner: 8% per minuto")
    print("  • Sostituzioni: concentrate dopo il 60°")
    print("  • Eventi aumentati nel finale (76-90')")
    
    print("\n⌨️  Premi CTRL+C per fermare il server\n")
    
    asyncio.create_task(simulate_matches())
    await asyncio.Event().wait()


if __name__ == "__main__":
    asyncio.run(main())
