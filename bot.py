import random
import discord
from discord import app_commands
from discord.ext import commands
import sqlite3
from config import token
from datetime import datetime
# Configura il bot
TOKEN = token # Sostituisci con il tuo vero token
intents = discord.Intents.default()
intents.message_content = True
bot = commands.Bot(command_prefix='!', intents=intents)


# Configura il database
conn = sqlite3.connect('aoe4_tournament.db')
c = conn.cursor()

# Crea la tabella players se non esiste
c.execute('''
    CREATE TABLE IF NOT EXISTS players (
        username TEXT PRIMARY KEY,
        points INTEGER,
        matches INTEGER,
        wins INTEGER DEFAULT 0,
        losses INTEGER DEFAULT 0
    )
''')

# Crea la tabella player_civ_stats se non esiste
c.execute('''
    CREATE TABLE IF NOT EXISTS player_civ_stats (
        username TEXT,
        civ TEXT,
        matches INTEGER DEFAULT 0,
        wins INTEGER DEFAULT 0,
        losses INTEGER DEFAULT 0,
        PRIMARY KEY (username, civ)
    )
''')


c.execute('''
    CREATE TABLE IF NOT EXISTS mare_seeds (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        seed INTEGER NOT NULL,
        timestamp DATETIME DEFAULT CURRENT_TIMESTAMP
    )
''')

c.execute('''
    CREATE TABLE IF NOT EXISTS terra_seeds (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        seed INTEGER NOT NULL,
        timestamp DATETIME DEFAULT CURRENT_TIMESTAMP
    )
''')


conn.commit()

# Variabili globali per le squadre
squadra1 = []
squadra2 = []
civilizations = [
    "Inglesi", "Francesi", "Cinesi", "Mongoli",
    "Rus", "Sacro Romano Impero", "Dinastia Abbaside", "Sultanato di Delhi",
    "Ottomani", "Maliani", "Bizantini", "Giapponesi", "Ayyubidi", "Giovanna D'arco", "Ordine del Drago", "Eredità di Zhu Xi"
]
assigned_civs = {}

@bot.event
async def on_ready():
    await bot.tree.sync()  # Sincronizza i comandi aggiornati
    print(f"Bot connesso come {bot.user} e comandi slash sincronizzati.")


def update_player_scores(names, points_change, is_win):
    for name in names:
        name = name.lower().strip()
        c.execute("SELECT points, matches, wins, losses FROM players WHERE username = ?", (name,))
        result = c.fetchone()

        if result:
            points = max(result[0] + points_change, 0)
            matches = result[1] + 1
            wins = result[2] + (1 if is_win else 0)
            losses = result[3] + (0 if is_win else 1)
            c.execute("UPDATE players SET points = ?, matches = ?, wins = ?, losses = ? WHERE username = ?",
                      (points, matches, wins, losses, name))
        else:
            initial_wins = 1 if is_win else 0
            initial_losses = 0 if is_win else 1
            c.execute("INSERT INTO players (username, points, matches, wins, losses) VALUES (?, ?, ?, ?, ?)",
                      (name, max(points_change, 0), 1, initial_wins, initial_losses))
        conn.commit()


# Comando /win
@bot.tree.command(name="win", description="Assegna i punti alla squadra vincente (1 o 2)")
async def win(interaction: discord.Interaction, squadra_vincente: int):
    global squadra1, squadra2
    if not squadra1 or not squadra2:
        await interaction.response.send_message("Le squadre non sono state impostate. Usa il comando /matchmaking prima di usare /win.")
        return

    if squadra_vincente == 1:
        update_player_scores(squadra1, 2, True)
        update_player_scores(squadra2, -1, False)
    elif squadra_vincente == 2:
        update_player_scores(squadra2, 2, True)
        update_player_scores(squadra1, -1, False)
    else:
        await interaction.response.send_message("Inserisci 1 o 2 per specificare la squadra vincente.")
        return
    squadra1 = []
    squadra2 = []
    await interaction.response.send_message("Punti assegnati e squadre resettate!")


# Comando /matchmaking
@bot.tree.command(name="matchmaking", description="Crea un match 4v4 bilanciato con casualità tra i giocatori di AoE4")
async def matchmaking(interaction: discord.Interaction, name1: str, name2: str, name3: str, name4: str, name5: str, name6: str, name7: str, name8: str):
    global squadra1, squadra2, assigned_civs
    try:
        names = [name1.strip().lower(), name2.strip().lower(), name3.strip().lower(), name4.strip().lower(),
                 name5.strip().lower(), name6.strip().lower(), name7.strip().lower(), name8.strip().lower()]
        players = []

        # Recupera i punti dei giocatori dal database
        for name in names:
            c.execute("SELECT points FROM players WHERE username = ?", (name,))
            result = c.fetchone()
            points = result[0] if result else 0
            players.append((name, points))
        random.shuffle(players)
        players.sort(key=lambda x: x[1], reverse=True)

        squadra1, squadra2 = [], []
        punti_squadra1, punti_squadra2 = 0, 0

        # Distribuisci i giocatori bilanciando i punti
        for player in players:
            if len(squadra1) < 4 and (punti_squadra1 <= punti_squadra2 or len(squadra2) >= 4):
                squadra1.append(player[0])
                punti_squadra1 += player[1]
            else:
                squadra2.append(player[0])
                punti_squadra2 += player[1]

        random.shuffle(civilizations)
        selected_civilizations = [civ.strip().lower() for civ in civilizations[:8]]  # Normalizza le civiltà
        assigned_civs = {players[i][0]: selected_civilizations[i] for i in range(8)}

        team1_message = "\n".join(f"{player} - {assigned_civs[player].capitalize()}" for player in squadra1)
        team2_message = "\n".join(f"{player} - {assigned_civs[player].capitalize()}" for player in squadra2)
        lista_mappa = ["terreste", "marittima"]
        mappa_scelta = lista_mappa[random.randint(0, 1)]
        message = (
            "Matchmaking completato!\n\n"
            f"Mappa : {mappa_scelta} \n\n"
            f"**Squadra 1** (Totale punti: {punti_squadra1}):\n{team1_message}\n\n"
            f"**Squadra 2** (Totale punti: {punti_squadra2}):\n{team2_message}"
        )
        await interaction.response.send_message(message)
    except Exception as e:
        await interaction.response.send_message(f"Errore durante la creazione del matchmaking: {str(e)}")


# Comando /leaderboard
@bot.tree.command(name="leaderboard", description="Mostra la classifica dei giocatori")
async def leaderboard(interaction: discord.Interaction):
    c.execute("SELECT username, points, matches, wins, losses FROM players ORDER BY points DESC")
    leaderboard_data = c.fetchall()
    if leaderboard_data:
        leaderboard_message = "**Classifica Giocatori**\n```"
        leaderboard_message += f"{'Pos':<4}{'Nome':<15}{'Punti':<8}{'Partite':<10}{'Vittorie':<10}{'Sconfitte':<10}{'Winrate':<8}\n"
        leaderboard_message += "-" * 60 + "\n"

        for index, (name, points, matches, wins, losses) in enumerate(leaderboard_data, start=1):
            winrate = (wins / matches * 100) if matches > 0 else 0
            leaderboard_message += (f"{index:<4}{name:<15}{points:<8}{matches:<10}"
                                    f"{wins:<10}{losses:<10}{winrate:7.2f}%\n")

        leaderboard_message += "```"
        await interaction.response.send_message(leaderboard_message)
    else:
        await interaction.response.send_message("La classifica è vuota.")


# Comando /statsplayer
@bot.tree.command(name="statsplayer", description="Mostra le statistiche di un giocatore specifico")
async def statsplayer(interaction: discord.Interaction, username: str):
    username = username.strip().lower()
    c.execute("SELECT points, matches, wins, losses FROM players WHERE username = ?", (username,))
    player_data = c.fetchone()

    if player_data:
        points, matches, wins, losses = player_data
        winrate = (wins / matches * 100) if matches > 0 else 0

        stats_message = (
            f"**Statistiche di {username}**\n"
            f"Punti: {points}\n"
            f"Partite: {matches}\n"
            f"Vittorie: {wins}\n"
            f"Sconfitte: {losses}\n"
            f"Win Rate: {winrate:.2f}%"
        )
        await interaction.response.send_message(stats_message)
    else:
        await interaction.response.send_message(f"Nessun giocatore trovato con il nome {username}.")


# Comando /civstats
@bot.tree.command(name="civstats", description="Mostra le statistiche di una specifica civiltà per tutti i giocatori")
async def civstats(interaction: discord.Interaction, civilization: str):
    civilization = civilization.strip().lower()
    c.execute("SELECT username, matches, wins, losses FROM player_civ_stats WHERE civ = ?", (civilization,))
    stats = c.fetchall()

    if stats:
        total_matches = sum(stat[1] for stat in stats)
        total_wins = sum(stat[2] for stat in stats)
        total_losses = sum(stat[3] for stat in stats)
        total_winrate = (total_wins / total_matches * 100) if total_matches > 0 else 0

        stats_message = (
            f"**Statistiche Totali per la civiltà {civilization.capitalize()}**\n"
            f"Partite Totali: {total_matches}\n"
            f"Vittorie Totali: {total_wins}\n"
            f"Sconfitte Totali: {total_losses}\n"
            f"Win Rate Totale: {total_winrate:.2f}%\n\n"
            "**Statistiche per Giocatore (ordinate per Win Rate):**\n"
        )

        stats = sorted(stats, key=lambda x: (x[2] / x[1] * 100) if x[1] > 0 else 0, reverse=True)
        for stat in stats:
            username, matches, wins, losses = stat
            winrate = (wins / matches * 100) if matches > 0 else 0
            stats_message += (
                f"- {username}: Partite: {matches}, Vittorie: {wins}, Sconfitte: {losses}, "
                f"Win Rate: {winrate:.2f}%\n"
            )
        await interaction.response.send_message(stats_message)
    else:
        await interaction.response.send_message(f"Nessuna statistica trovata per la civiltà {civilization}.")


# Comando /allcivstats
@bot.tree.command(name="allcivstats", description="Mostra le statistiche totali di ogni civiltà ordinate per win rate")
async def allcivstats(interaction: discord.Interaction):
    c.execute("SELECT civ, SUM(matches), SUM(wins), SUM(losses) FROM player_civ_stats GROUP BY civ")
    stats = c.fetchall()

    if stats:
        stats = sorted(stats, key=lambda x: (x[2] / x[1] * 100) if x[1] > 0 else 0, reverse=True)
        stats_message = "**Statistiche Totali per tutte le Civiltà (ordinate per Win Rate):**\n"

        for stat in stats:
            civ, matches, wins, losses = stat
            winrate = (wins / matches * 100) if matches > 0 else 0
            stats_message += (
                f"- {civ.capitalize()}: Partite: {matches}, Vittorie: {wins}, Sconfitte: {losses}, "
                f"Win Rate: {winrate:.2f}%\n"
            )
        await interaction.response.send_message(stats_message)
    else:
        await interaction.response.send_message("Nessuna statistica trovata per le civiltà.")


@bot.tree.command(name="saveseed", description="Salva il seed della partita da riutilizzare in futuro")
async def saveseed(interaction: discord.Interaction, seed: int, type: str):
    try:
        # Controlla che il seed sia di 8 cifre
        if len(str(seed)) != 8:
            await interaction.response.send_message("Il seed deve essere un numero di esattamente 8 cifre.", ephemeral=True)
            return

        # Controlla che il tipo sia valido
        if type.lower() not in ["mare", "terra"]:
            await interaction.response.send_message('Il tipo deve essere "mare" o "terra".', ephemeral=True)
            return

        # Determina la tabella corretta
        table_name = "mare_seeds" if type.lower() == "mare" else "terra_seeds"

        # Salva il seed nella tabella corrispondente
        conn = sqlite3.connect("aoe4_tournament.db")
        c = conn.cursor()
        c.execute(f"INSERT INTO {table_name} (seed) VALUES (?)", (seed,))
        conn.commit()
        conn.close()

        await interaction.response.send_message(f"Seed {seed} salvato con successo nella lista {type}!", ephemeral=True)

    except Exception as e:
        await interaction.response.send_message(f"Errore durante il salvataggio del seed: {str(e)}", ephemeral=True)

@bot.tree.command(name="listseeds", description="Visualizza i seed salvati per mare o terra")
async def listseeds(interaction: discord.Interaction, type: str):
    try:
        # Controlla che il tipo sia valido
        if type.lower() not in ["mare", "terra"]:
            await interaction.response.send_message('Il tipo deve essere "mare" o "terra".', ephemeral=True)
            return

        # Determina la tabella corretta
        table_name = "mare_seeds" if type.lower() == "mare" else "terra_seeds"

        # Recupera i seed dalla tabella corrispondente
        conn = sqlite3.connect("aoe4_tournament.db")
        c = conn.cursor()
        c.execute(f"SELECT id, seed, timestamp FROM {table_name} ORDER BY id ASC")
        seeds = c.fetchall()
        conn.close()

        if seeds:
            seeds_list = "\n".join(f"ID: {seed[0]}, Seed: {seed[1]}, Salvato il: {seed[2]}" for seed in seeds)
            await interaction.response.send_message(f"Seed salvati nella lista {type}:\n{seeds_list}")
        else:
            await interaction.response.send_message(f"Non ci sono seed salvati nella lista {type}.")
    except Exception as e:
        await interaction.response.send_message(f"Errore durante il recupero dei seed: {str(e)}")



# Comando /sveglia
@bot.tree.command(name="sveglia", description="Invia un messaggio per svegliare @massimi25")
async def sveglia(interaction: discord.Interaction, nome: str):
    await interaction.response.send_message(f"{nome} SVEGLIAAAAAAAAA")




#Sezione Prenotazione

# Variabile globale per tenere traccia delle prenotazioni
prenotazioni = []  # Contiene i nomi degli utenti che hanno reagito
prenotazione_message_id = None  # Salva l'ID del messaggio di prenotazione


@bot.tree.command(name="prenotazione", description="Crea un messaggio di prenotazione per la ZozzaRoyale.")
async def prenotazione(interaction: discord.Interaction, ora: str):
    global prenotazione_message_id, prenotazione_ora
    try:
        # Salva l'ora specificata
        prenotazione_ora = ora

        # Invia il messaggio di prenotazione
        message = await interaction.channel.send(
            f"Prenotati alla ZozzaRoyale di oggi alle {ora}. Reagisci con 🐷 per partecipare!"
        )
        prenotazione_message_id = message.id  # Salva l'ID del messaggio per monitorare le reazioni

        await message.add_reaction("🐷")  # Aggiungi automaticamente la reazione "pig face"
        await interaction.response.send_message("Messaggio di prenotazione creato!", ephemeral=True)
    except Exception as e:
        await interaction.response.send_message(f"Errore durante la creazione della prenotazione: {str(e)}", ephemeral=True)

@bot.event
async def on_reaction_add(reaction, user):
    global prenotazioni, prenotazione_message_id
    print(f"Reazione aggiunta da {user.name} sul messaggio ID {reaction.message.id} con emoji {reaction.emoji}")
    # Ignora le reazioni del bot stesso
    if user.bot:
        return

    # Controlla che la reazione sia sul messaggio di prenotazione e che sia una "pig face"
    if reaction.message.id == prenotazione_message_id and str(reaction.emoji) == "🐷":
        now = datetime.now().strftime("%H:%M:%S")  # Salva l'ora attuale
        if user.name not in [p[0] for p in prenotazioni]:  # Controlla che il nome non sia già nella lista
            prenotazioni.append((user.name, now))  # Salva il nome e l'ora
            print(f"{user.name} si è prenotato alle {now}!")  # Debug


@bot.event
async def on_reaction_remove(reaction, user):
    global prenotazioni, prenotazione_message_id
    print(f"Rimozione reazione: {user.name}, emoji: {reaction.emoji}, message ID: {reaction.message.id}")
    print(f"Lista attuale dei prenotati: {prenotazioni}")
    # Ignora le reazioni del bot stesso
    if user.bot:
        return

    # Controlla che la reazione sia sul messaggio di prenotazione e che sia una "pig face"
    if reaction.message.id == prenotazione_message_id and str(reaction.emoji) == "🐷":
        # Trova e rimuovi l'utente dalla lista prenotazioni
        initial_len = len(prenotazioni)  # Lunghezza iniziale della lista per debug
        prenotazioni = [p for p in prenotazioni if p[0] != user.name]

        # Verifica se qualcosa è stato rimosso
        if len(prenotazioni) < initial_len:
            print(f"{user.name} è stato rimosso dalla lista prenotati.")
        else:
            print(f"{user.name} non era nella lista prenotati, nessuna rimozione effettuata.")



@bot.tree.command(name="listaprenotati", description="Mostra la lista dei giocatori prenotati con l'ora della prenotazione.")
async def listaprenotati(interaction: discord.Interaction):
    global prenotazioni, prenotazione_ora

    # Verifica se il comando /prenotazione è stato eseguito
    if not prenotazione_ora:
        await interaction.response.send_message(
            "Nessuna prenotazione attiva. Usa il comando `/prenotazione` per avviare una prenotazione.",
            ephemeral=True
        )
        return

    # Se ci sono prenotazioni
    if prenotazioni:
        # Lista completa con indice e orario
        lista_completa = "\n".join(f"{index + 1}. {name} - {time}" for index, (name, time) in enumerate(prenotazioni))

        # Estrai i primi 8 prenotati per il matchmaking
        primi_otto = " ".join([name for name, time in prenotazioni[:8]])

        await interaction.response.send_message(
            f"**Giocatori prenotati per la partita delle {prenotazione_ora}:**\n```\n{lista_completa}\n```\n"
            f"**Primi 8 giocatori per il matchmaking:**\n```\n{primi_otto}\n```"
        )
    else:
        # Se non ci sono prenotazioni, ma il comando /prenotazione è stato eseguito
        await interaction.response.send_message(f"**Giocatori prenotati per la partita delle {prenotazione_ora}:**\nNessun giocatore si è ancora prenotato.")

# Comando /test
@bot.tree.command(name="test", description="Controlla lo stato del bot e la sua versione")
async def test(interaction: discord.Interaction):
    await interaction.response.send_message(
        "Il bot è online e funzionante! v0.5.2d\n"
        "- Modifiche apportate:\n"
        "Aggiunto sistema prenotazione\n"
        "Modificato comando sveglia\n"
    )

# Esegui il bot
bot.run(TOKEN)
