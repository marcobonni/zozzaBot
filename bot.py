import random
import discord
from discord import app_commands
from discord.ext import commands
import sqlite3
import token
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

        message = (
            "Matchmaking completato!\n\n"
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


# Comando /massimi
@bot.tree.command(name="massimi", description="Invia un messaggio per svegliare @massimi25")
async def massimi(interaction: discord.Interaction):
    await interaction.response.send_message("massimi25 SVEGLIAAAAAAAAA")


# Comando /test
@bot.tree.command(name="test", description="Controlla lo stato del bot e la sua versione")
async def test(interaction: discord.Interaction):
    await interaction.response.send_message(
        "Il bot è online e funzionante! v0.4\n"
        "- Modifiche apportate:\n"
        "  1. Creato il comando `/statsplayer` per visualizzare le statistiche di un giocatore specifico.\n"
        "  2. Creato il comando `/civstats` per visualizzare le statistiche di una specifica civiltà.\n"
        "  3. Creato il comando `/allcivstats` per visualizzare le statistiche totali di tutte le civiltà.\n"
        "  4. Migliorato il comando `/leaderboard` con un formato tabellare."
    )


# Esegui il bot
bot.run(TOKEN)