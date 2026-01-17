# -*- coding: utf-8 -*-
import asyncio
import json
import random
import tornado.web
import tornado.websocket
from datetime import datetime

# CARICAMENTO E NORMALIZZAZIONE DATABASE SQUADRE
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

# SISTEMA DI CAMPIONATO
class Championship:
    def __init__(self, teams):
        self.teams = teams
        self.standings = {team["id"]: {
            "name": team["name"],
            "played": 0,
            "wins": 0,
            "draws": 0,
            "losses": 0,
            "goals_for": 0,
            "goals_against": 0,
            "points": 0
        } for team in teams}
        self.matches = {}
        self.current_matchday = 1
        self.generate_calendar()
    
    def generate_calendar(self):
        """
        Genera il calendario del campionato (2 gironi = 38 giornate totali).
        Tutte le squadre giocano contemporaneamente ogni giornata.
        """
        team_list = [t["id"] for t in self.teams]
        num_teams = len(team_list)
        
        # Con 20 squadre: 19 giornate per girone = 38 giornate totali
        num_matchdays_per_girone = num_teams - 1
        match_id = 1
        
        # Algoritmo round-robin per generare calendario bilanciato
        for girone in range(2):  # 2 gironi (andata e ritorno)
            teams_in_round = team_list.copy()
            
            for matchday in range(1, num_matchdays_per_girone + 1):
                # Ottieni gli accoppiamenti per questa giornata
                matches_in_matchday = 0
                for i in range(num_teams // 2):
                    home_id = teams_in_round[i]
                    away_id = teams_in_round[num_teams - 1 - i]
                    
                    # Crea la partita
                    home_team = next(t for t in self.teams if t["id"] == home_id)
                    away_team = next(t for t in self.teams if t["id"] == away_id)
                    
                    actual_matchday = matchday + (girone * num_matchdays_per_girone)
                    
                    self.matches[str(match_id)] = {
                        "id": str(match_id),
                        "matchday": actual_matchday,
                        "home_id": home_id,
                        "away_id": away_id,
                        "home": home_team["name"],
                        "away": away_team["name"],
                        "home_data": home_team,
                        "away_data": away_team,
                        "status": "scheduled",
                        "minute": 0,
                        "score": {"home": 0, "away": 0},
                        "events": [],
                        "half": 1,
                        "injury_time": 0
                    }
                    match_id += 1
                    matches_in_matchday += 1
                
                # Ruota le squadre per il prossimo round (algoritmo round-robin)
                # Mantieni il primo fisso, ruota gli altri
                fixed = teams_in_round[0]
                teams_in_round = [fixed] + [teams_in_round[-1]] + teams_in_round[1:-1]
        
        self.current_matchday = 1
    
    def get_matches_by_matchday(self, matchday):
        """Restituisce le partite di una giornata"""
        return {mid: m for mid, m in self.matches.items() if m["matchday"] == matchday}
    
        
        home_id = match["home_id"]
        away_id = match["away_id"]
        home_score = match["score"]["home"]
        away_score = match["score"]["away"]
        

# CONFIGURAZIONE PROBABILITÀ EVENTI (realistiche per il calcio)
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

# INIZIALIZZA IL CAMPIONATO
championship = Championship(teams_db[:20])  # Usa tutte le 20 squadre
matches = championship.matches


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


# GENERA I MATCH INIZIALI
# Le partite sono generate dal calendario del campionato
num_matchdays = max(m["matchday"] for m in matches.values())
print(f"📅 Calendario generato con {len(matches)} partite ({num_matchdays} giornate)")

# SET GLOBALE PER CLIENT WEBSOCKET
clients = set()


# HANDLER HTTP
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


# HANDLER WEBSOCKET
class MatchesWebSocket(tornado.websocket.WebSocketHandler):
    def check_origin(self, origin):
        return True
    
    def open(self):
        print(" WebSocket aperto - Nuovo client connesso")
        clients.add(self)
        asyncio.create_task(self.send_initial_state())
    
    async def send_initial_state(self):
        await self.write_message(json.dumps({
            "type": "initial_state",
            "matches": matches,
            "standings": championship.get_sorted_standings(),
            "current_matchday": championship.current_matchday
        }))
    
    def on_close(self):
        print(" WebSocket chiuso - Client disconnesso")
        clients.remove(self)


# SIMULAZIONE MATCH CON PROBABILITÀ REALISTICHE
async def simulate_matches():
    """
    Loop che simula l'avanzamento dei match con eventi probabilistici realistici.
    Tutti i match della stessa giornata iniziano insieme e quando finiscono 
    tutti, passa alla giornata successiva. La classifica si aggiorna in tempo reale.
    """
    live_matchday = 1
    max_matchday = max(m["matchday"] for m in matches.values())
    
    # Avvia tutte le partite della prima giornata
    first_matchday_matches = [m for m in matches.values() if m["matchday"] == 1]
    for match in first_matchday_matches:
        match["status"] = "live"
        match["minute"] = 0
        match["score"] = {"home": 0, "away": 0}
        match["events"] = []
    
    print(f"\n🎯 INIZIO GIORNATA {live_matchday} - {len(first_matchday_matches)} PARTITE IN CAMPO\n")
    
    while live_matchday <= max_matchday:
        await asyncio.sleep(1)  # 1 secondo = 1 minuto di gioco
        
        updated_matches = []
        standings_updated = False
        
        # Prendi tutte le partite della giornata corrente
        current_matchday_matches = [m for m in matches.values() if m["matchday"] == live_matchday]
        
        for match_id, match in matches.items():
            if match["matchday"] != live_matchday:
                continue
            
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
                print(f"⏱️  Fine 1° tempo: {match['home']} {match['score']['home']}-{match['score']['away']} {match['away']}")
            
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
                championship.update_standings(match_id)
                standings_updated = True
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
                        if event_type == "goal" and event.get("scored", True):
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
        if (updated_matches or standings_updated) and clients:
            message = json.dumps({
                "type": "match_update",
                "matches": updated_matches,
                "standings": championship.get_sorted_standings() if standings_updated else None,
                "current_matchday": live_matchday
            })
            
            for client in list(clients):
                try:
                    await client.write_message(message)
                except Exception as e:
                    print(f"Errore invio: {e}")
        
        # Passa alla giornata successiva quando TUTTE le partite della giornata sono finite
        if all(m["status"] == "finished" for m in current_matchday_matches):
            if live_matchday < max_matchday:
                live_matchday += 1
                # Avvia tutte le partite della nuova giornata
                next_matchday_matches = [m for m in matches.values() if m["matchday"] == live_matchday]
                for match in next_matchday_matches:
                    match["status"] = "live"
                    match["minute"] = 0
                    match["score"] = {"home": 0, "away": 0}
                    match["events"] = []
                print(f"\n{'='*70}")
                print(f"🎯 INIZIO GIORNATA {live_matchday} - {len(next_matchday_matches)} PARTITE IN CAMPO")
                print(f"{'='*70}\n")
            else:
                print(f"\n{'='*70}")
                print(f"{'='*70}\n")
                break


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

    
    asyncio.create_task(simulate_matches())
    await asyncio.Event().wait()


if __name__ == "__main__":
    asyncio.run(main())
