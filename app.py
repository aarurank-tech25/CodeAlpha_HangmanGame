
from flask import Flask, render_template, request, redirect, url_for, session, flash
from werkzeug.security import generate_password_hash, check_password_hash
from functools import wraps
from database import get_connection, initialize_database, IntegrityError
from pathlib import Path
from datetime import date, timedelta
import random
import sqlite3
import time
import math
import os
from daily_leaderboard import daily_leaderboard_bp
from multiplayer import multiplayer_bp
from multiplayer_ranking import multiplayer_ranking_bp
from account_settings import account_settings_bp

app = Flask(__name__)
app.register_blueprint(daily_leaderboard_bp)
app.secret_key = os.environ.get("SECRET_KEY")

if not app.secret_key:
    raise RuntimeError("SECRET_KEY environment variable is not set.")
app.register_blueprint(multiplayer_bp)
initialize_database()
app.register_blueprint(multiplayer_ranking_bp)

app.register_blueprint(account_settings_bp)

# =======================================
# DAILY CHALLENGE DATABASE
# =======================================

def initialize_daily_database():

    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS daily_challenge_history (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            player_id INTEGER NOT NULL,
            challenge_date TEXT NOT NULL,
            word TEXT NOT NULL,
            result TEXT NOT NULL,
            score INTEGER NOT NULL DEFAULT 0,
            UNIQUE(player_id, challenge_date)
        )
    """)

    conn.commit()
    conn.close()


initialize_daily_database()


# =======================================
# RANDOM WORD BANK
# =======================================

WORD_BANK_PATH = (
    Path(__file__).resolve().parent
    / "data"
    / "word_bank.txt"
)

WORD_LENGTHS = {
    "easy": (3, 5),
    "medium": (6, 8),
    "hard": (9, 12)
}


def load_word_bank():

    if not WORD_BANK_PATH.is_file():
        raise FileNotFoundError(
            "Word bank not found. Check data/word_bank.txt"
        )

    words = []

    with WORD_BANK_PATH.open("r", encoding="utf-8") as file:

        for line in file:

            word = line.strip().upper()

            if word.isalpha() and 3 <= len(word) <= 12:
                words.append(word)

    words = sorted(set(words))

    if not words:
        raise ValueError("Word bank is empty!")

    return words


WORD_BANK = load_word_bank()


def get_random_word(difficulty, player_id):

    min_length, max_length = WORD_LENGTHS.get(
        difficulty,
        WORD_LENGTHS["medium"]
    )

    available_words = [
        word for word in WORD_BANK
        if min_length <= len(word) <= max_length
    ]

    if not available_words:
        raise ValueError(
            f"No words available for {difficulty} difficulty."
        )

    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute(
        """
        SELECT word
        FROM game_history
        WHERE player_id = ?
        ORDER BY id DESC
        LIMIT 15
        """,
        (player_id,)
    )

    recent_games = cursor.fetchall()
    conn.close()

    recent_words = set()

    for row in recent_games:

        if row["word"]:
            recent_words.add(row["word"].upper())

    fresh_words = [
        word for word in available_words
        if word not in recent_words
    ]

    if fresh_words:
        return random.choice(fresh_words)

    return random.choice(available_words)


# =======================================
# DAILY WORD SELECTION
# =======================================

def get_daily_word(challenge_date):

    daily_words = [
        word for word in WORD_BANK
        if 6 <= len(word) <= 8
    ]

    if not daily_words:
        raise ValueError("No words available for daily challenge.")

    # Every player receives the same word on the same date.

    word_index = challenge_date.toordinal() % len(daily_words)

    return daily_words[word_index]


# =======================================
# GAME SETTINGS
# =======================================

MAX_ATTEMPTS = {
    "easy": 8,
    "medium": 6,
    "hard": 4
}

TIME_LIMITS = {
    "easy": 60,
    "medium": 45,
    "hard": 30
}

DIFFICULTY_BONUS = {
    "easy": 0,
    "medium": 20,
    "hard": 40
}


# =======================================
# BADGE DETAILS
# =======================================

BADGE_DETAILS = [
    {
        "name": "First Victory",
        "icon": "🥇",
        "description": "Win your first Hangman game.",
        "condition": "Win 1 game"
    },
    {
        "name": "Rising Star",
        "icon": "⭐",
        "description": "Win five Hangman games.",
        "condition": "Win 5 games"
    },
    {
        "name": "Arena Legend",
        "icon": "⚔️",
        "description": "Win ten Hangman games.",
        "condition": "Win 10 games"
    },
    {
        "name": "Hard Mode Hero",
        "icon": "🔥",
        "description": "Win a game in Hard difficulty.",
        "condition": "Win 1 Hard game"
    },
    {
        "name": "Sharp Shooter",
        "icon": "🧠",
        "description": "Win without using a hint.",
        "condition": "Win without hint"
    },
    {
        "name": "XP Hunter",
        "icon": "💎",
        "description": "Earn at least 500 total XP.",
        "condition": "Reach 500 XP"
    }
]


# =======================================
# LOGIN REQUIRED
# =======================================

def login_required(function):

    @wraps(function)
    def wrapper(*args, **kwargs):

        if "player_id" not in session:
            return redirect(url_for("login"))

        return function(*args, **kwargs)

    return wrapper


# =======================================
# HOME PAGE
# =======================================

@app.route("/")
def index():

    if "player_id" in session:
        return redirect(url_for("dashboard"))

    return render_template("index.html")


# =======================================
# REGISTER
# =======================================

@app.route("/register", methods=["GET", "POST"])
def register():

    if request.method == "POST":

        username = request.form.get(
            "username", ""
        ).strip()

        password = request.form.get(
            "password", ""
        )

        if len(username) < 3:
            flash("Username must contain at least 3 characters.")
            return redirect(url_for("register"))

        if len(password) < 6:
            flash("Password must contain at least 6 characters.")
            return redirect(url_for("register"))

        hashed_password = generate_password_hash(password)

        conn = get_connection()
        cursor = conn.cursor()

        try:

            cursor.execute(
                """
                INSERT INTO players (username, password)
                VALUES (?, ?)
                """,
                (username, hashed_password)
            )

            conn.commit()

            flash("Registration successful! Please login.")

            return redirect(url_for("login"))

        except IntegrityError:

            flash("Username already exists!")

        finally:
            conn.close()

    return render_template("register.html")


# =======================================
# LOGIN
# =======================================

@app.route("/login", methods=["GET", "POST"])
def login():

    if request.method == "POST":

        username = request.form.get(
            "username", ""
        ).strip()

        password = request.form.get(
            "password", ""
        )

        conn = get_connection()
        cursor = conn.cursor()

        cursor.execute(
            """
            SELECT *
            FROM players
            WHERE username = ?
            """,
            (username,)
        )

        player = cursor.fetchone()
        conn.close()

        if player and check_password_hash(
            player["password"],
            password
        ):

            session.clear()

            session["player_id"] = player["id"]
            session["username"] = player["username"]

            return redirect(url_for("dashboard"))

        flash("Invalid username or password!")

    return render_template("login.html")


# =======================================
# DASHBOARD
# =======================================

@app.route("/dashboard")
@login_required
def dashboard():

    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute(
        """
        SELECT *
        FROM players
        WHERE id = ?
        """,
        (session["player_id"],)
    )

    player = cursor.fetchone()

    cursor.execute(
        """
        SELECT COUNT(*)
        FROM game_history
        WHERE player_id = ?
        """,
        (session["player_id"],)
    )

    total_games = cursor.fetchone()[0]

    cursor.execute(
        """
        SELECT COUNT(*)
        FROM game_history
        WHERE player_id = ? AND result = 'Win'
        """,
        (session["player_id"],)
    )

    total_wins = cursor.fetchone()[0]

    conn.close()

    return render_template(
        "dashboard.html",
        player=player,
        total_games=total_games,
        total_wins=total_wins
    )


# =======================================
# SAVE GAME AND AWARD BADGES
# =======================================

def save_game(result, score):

    conn = get_connection()
    cursor = conn.cursor()

    player_id = session["player_id"]

    cursor.execute(
        """
        INSERT INTO game_history
        (player_id, word, score, result)
        VALUES (?, ?, ?, ?)
        """,
        (
            player_id,
            session["word"],
            score,
            result
        )
    )

    # Add XP and update level

    if score > 0:

        cursor.execute(
            """
            UPDATE players
            SET xp = xp + ?,
                level = CAST((xp + ?) / 500 AS INTEGER) + 1
            WHERE id = ?
            """,
            (score, score, player_id)
        )

    # Save daily challenge result

    if session.get("is_daily"):

        cursor.execute(
            """
            INSERT OR IGNORE INTO daily_challenge_history
            (player_id, challenge_date, word, result, score)
            VALUES (?, ?, ?, ?, ?)
            """,
            (
                player_id,
                session["daily_date"],
                session["word"],
                result,
                score
            )
        )

    # Award badges after a win

    if result == "Win":

        cursor.execute(
            """
            SELECT COUNT(*)
            FROM game_history
            WHERE player_id = ? AND result = 'Win'
            """,
            (player_id,)
        )

        total_wins = cursor.fetchone()[0]

        cursor.execute(
            """
            SELECT xp
            FROM players
            WHERE id = ?
            """,
            (player_id,)
        )

        player = cursor.fetchone()
        player_xp = player["xp"]

        cursor.execute(
            """
            SELECT badge_name
            FROM badges
            WHERE player_id = ?
            """,
            (player_id,)
        )

        existing_badges = set()

        for row in cursor.fetchall():
            existing_badges.add(row["badge_name"])

        new_badges = []

        if total_wins >= 1:
            new_badges.append("First Victory")

        if total_wins >= 5:
            new_badges.append("Rising Star")

        if total_wins >= 10:
            new_badges.append("Arena Legend")

        if session.get("difficulty") == "hard":
            new_badges.append("Hard Mode Hero")

        if not session.get("hint_used"):
            new_badges.append("Sharp Shooter")

        if player_xp >= 500:
            new_badges.append("XP Hunter")

        for badge in new_badges:

            if badge not in existing_badges:

                cursor.execute(
                    """
                    INSERT INTO badges (player_id, badge_name)
                    VALUES (?, ?)
                    """,
                    (player_id, badge)
                )

    conn.commit()
    conn.close()


# =======================================
# CALCULATE SCORE
# =======================================

def calculate_score():

    difficulty = session.get(
        "difficulty",
        "medium"
    )

    if session.get("hint_used"):
        base_score = 80
    else:
        base_score = 100

    difficulty_bonus = DIFFICULTY_BONUS[difficulty]

    elapsed = time.time() - session["start_time"]

    time_limit = session["time_limit"]

    time_bonus = 0

    if elapsed <= time_limit / 2:
        time_bonus = 20

    return base_score + difficulty_bonus + time_bonus


# =======================================
# DIFFICULTY PAGE
# =======================================

@app.route("/difficulty")
@login_required
def difficulty():

    return render_template("difficulty.html")


# =======================================
# DAILY CHALLENGE PAGE
# =======================================

@app.route("/daily-challenge")
@login_required
def daily_challenge():

    player_id = session["player_id"]

    today = date.today()
    today_string = today.isoformat()

    conn = get_connection()
    cursor = conn.cursor()

    # Check today's attempt

    cursor.execute(
        """
        SELECT result, score
        FROM daily_challenge_history
        WHERE player_id = ? AND challenge_date = ?
        """,
        (player_id, today_string)
    )

    today_record = cursor.fetchone()

    # Get previous daily results

    cursor.execute(
        """
        SELECT challenge_date, result
        FROM daily_challenge_history
        WHERE player_id = ?
        ORDER BY challenge_date DESC
        """,
        (player_id,)
    )

    daily_records = cursor.fetchall()

    conn.close()

    # Calculate consecutive daily wins

    if today_record:
        expected_date = today
    else:
        expected_date = today - timedelta(days=1)

    win_streak = 0

    for record in daily_records:

        record_date = date.fromisoformat(
            record["challenge_date"]
        )

        if record_date == expected_date:

            if record["result"] == "Win":

                win_streak += 1

                expected_date -= timedelta(days=1)

            else:
                break

        elif record_date < expected_date:
            break

    return render_template(
        "daily_challenge.html",
        challenge_date=today.strftime("%d %B %Y"),
        played_today=today_record is not None,
        daily_result=today_record["result"] if today_record else None,
        daily_score=today_record["score"] if today_record else 0,
        win_streak=win_streak
    )


# =======================================
# HANGMAN GAME
# =======================================

@app.route("/game", methods=["GET", "POST"])
@login_required
def game():

    # Start a new game

    if request.method == "GET" or "word" not in session:

        is_daily = request.args.get("daily") == "1"

        if is_daily:

            today = date.today()
            today_string = today.isoformat()

            conn = get_connection()
            cursor = conn.cursor()

            cursor.execute(
                """
                SELECT id
                FROM daily_challenge_history
                WHERE player_id = ? AND challenge_date = ?
                """,
                (session["player_id"], today_string)
            )

            completed = cursor.fetchone()
            conn.close()

            if completed:
                flash("You have already completed today's challenge!")
                return redirect(url_for("daily_challenge"))

            selected_difficulty = "medium"

            session["is_daily"] = True
            session["daily_date"] = today_string

            session["word"] = get_daily_word(today)

        else:

            selected_difficulty = request.args.get(
                "difficulty",
                "medium"
            ).lower()

            if selected_difficulty not in WORD_LENGTHS:
                selected_difficulty = "medium"

            session["is_daily"] = False
            session["daily_date"] = None

            session["word"] = get_random_word(
                selected_difficulty,
                session["player_id"]
            )

        session["difficulty"] = selected_difficulty

        session["max_attempts"] = MAX_ATTEMPTS[
            selected_difficulty
        ]

        session["time_limit"] = TIME_LIMITS[
            selected_difficulty
        ]

        session["guessed"] = []
        session["wrong"] = 0
        session["game_over"] = False
        session["result"] = None
        session["hint_used"] = False
        session["game_saved"] = False
        session["score"] = 0

        session["start_time"] = time.time()

    if request.method == "POST" and not session.get("game_over"):

        elapsed = time.time() - session["start_time"]
        word = session.get("word", "")
        guessed = session.get("guessed", [])
        secret_letters = set(word.strip().upper()) if word else set()
        revealed_letters = set(str(l).strip().upper() for l in guessed)

        if elapsed >= session["time_limit"]:

            # Check if secret word was completed before declaring loss
            if secret_letters and secret_letters.issubset(revealed_letters):
                session["game_over"] = True
                session["result"] = "Win"

                if not session.get("game_saved"):
                    score = calculate_score()
                    session["score"] = score
                    save_game("Win", score)
                    session["game_saved"] = True
            else:
                session["game_over"] = True
                session["result"] = "Loss"
                session["score"] = 0

                if not session.get("game_saved"):
                    save_game("Loss", 0)
                    session["game_saved"] = True

        else:

            action = request.form.get(
                "action",
                "guess"
            )

            # Hint

            if action == "hint":

                if not session.get("hint_used", False):

                    word = session["word"]
                    guessed = session["guessed"]

                    guessed_upper = {str(g).strip().upper() for g in guessed}
                    hidden_letters = [
                        letter for letter in word
                        if letter.strip().upper() not in guessed_upper
                    ]

                    if hidden_letters:

                        hint_letter = random.choice(
                            hidden_letters
                        ).strip().upper()

                        if hint_letter not in guessed:
                            guessed.append(hint_letter)

                        session["hint_used"] = True
                        session.modified = True

            # Normal guess

            elif action == "guess":

                guess = request.form.get(
                    "guess",
                    ""
                ).strip().upper()

                if len(guess) == 1 and guess.isalpha():

                    guessed_upper = {str(g).strip().upper() for g in session["guessed"]}
                    if guess not in guessed_upper:

                        session["guessed"].append(guess)

                        if guess not in session["word"].upper():
                            session["wrong"] += 1

                        session.modified = True

            # Check win or loss immediately after processing guess / hint
            word = session.get("word", "")
            guessed = session.get("guessed", [])
            secret_letters = set(word.strip().upper()) if word else set()
            revealed_letters = set(str(l).strip().upper() for l in guessed)

            won = bool(secret_letters and secret_letters.issubset(revealed_letters))

            if won:
                session["game_over"] = True
                session["result"] = "Win"

                if not session.get("game_saved"):
                    score = calculate_score()
                    session["score"] = score
                    save_game("Win", score)
                    session["game_saved"] = True

            elif session.get("wrong", 0) >= session.get("max_attempts", 6):
                session["game_over"] = True
                session["result"] = "Loss"
                session["score"] = 0

                if not session.get("game_saved"):
                    save_game("Loss", 0)
                    session["game_saved"] = True

    # Calculate remaining time

    elapsed = time.time() - session["start_time"]

    remaining_time = max(
        0,
        math.ceil(session["time_limit"] - elapsed)
    )

    # Display word

    word = session.get("word", "")
    guessed = session.get("guessed", [])
    guessed_upper = {str(l).strip().upper() for l in guessed}

    display_word = " ".join(
        letter if letter.upper() in guessed_upper else "_"
        for letter in word
    )

    correct_guesses = [
        letter for letter in guessed
        if letter.upper() in word.upper()
    ]

    wrong_guesses = [
        letter for letter in guessed
        if letter.upper() not in word.upper()
    ]

    secret_letters = set(word.strip().upper()) if word else set()
    won = (session.get("result") == "Win") or bool(
        secret_letters and secret_letters.issubset(guessed_upper)
    )

    # Display daily challenge label

    display_difficulty = (
        "Daily Challenge"
        if session.get("is_daily")
        else session.get("difficulty", "medium")
    )

    return render_template(
        "game.html",
        display_word=display_word,
        guessed=guessed,
        correct_guesses=correct_guesses,
        wrong_guesses=wrong_guesses,
        wrong=session.get("wrong", 0),
        game_over=session.get("game_over", False),
        result=session.get("result"),
        won=won,
        word=word,
        answer=word if session.get("game_over") else None,
        hint_used=session.get("hint_used", False),
        score=session.get("score", 0),
        difficulty=display_difficulty,
        max_attempts=session.get("max_attempts", 6),
        remaining_lives=max(
            0,
            session.get("max_attempts", 6)
            - session.get("wrong", 0)
        ),
        time_limit=session.get("time_limit", 45),
        remaining_time=remaining_time,
        difficulty_bonus=DIFFICULTY_BONUS.get(
            session.get("difficulty", "medium"),
            20
        )
    )
    


# =======================================
# GLOBAL LEADERBOARD
# =======================================

@app.route("/leaderboard")
@login_required
def leaderboard():

    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute(
        """
        SELECT
            p.id,
            p.username,
            p.xp,
            p.level,
            COUNT(g.id) AS total_games,
            COALESCE(
                SUM(
                    CASE
                        WHEN g.result = 'Win' THEN 1
                        ELSE 0
                    END
                ),
                0
            ) AS total_wins
        FROM players p
        LEFT JOIN game_history g
            ON p.id = g.player_id
        GROUP BY
            p.id,
            p.username,
            p.xp,
            p.level
        ORDER BY
            p.xp DESC,
            p.level DESC
        LIMIT 20
        """
    )

    players = cursor.fetchall()
    conn.close()

    return render_template(
        "leaderboard.html",
        players=players,
        current_player=session["player_id"]
    )


# =======================================
# ACHIEVEMENTS PAGE
# =======================================

@app.route("/achievements")
@login_required
def achievements():

    player_id = session["player_id"]

    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute(
        """
        SELECT badge_name
        FROM badges
        WHERE player_id = ?
        """,
        (player_id,)
    )

    unlocked_rows = cursor.fetchall()

    cursor.execute(
        """
        SELECT xp
        FROM players
        WHERE id = ?
        """,
        (player_id,)
    )

    player = cursor.fetchone()

    cursor.execute(
        """
        SELECT COUNT(*)
        FROM game_history
        WHERE player_id = ? AND result = 'Win'
        """,
        (player_id,)
    )

    total_wins = cursor.fetchone()[0]

    conn.close()

    unlocked_names = set()

    for row in unlocked_rows:
        unlocked_names.add(row["badge_name"])

    player_xp = player["xp"] if player else 0

    badge_list = []

    for badge in BADGE_DETAILS:

        badge_data = badge.copy()

        badge_data["unlocked"] = (
            badge["name"] in unlocked_names
        )

        badge_list.append(badge_data)

    return render_template(
        "achievements.html",
        badges=badge_list,
        unlocked_count=len(unlocked_names),
        total_badges=len(BADGE_DETAILS),
        total_wins=total_wins,
        player_xp=player_xp
    )


# =======================================
# GAME HISTORY PAGE
# =======================================

@app.route("/game-history")
@login_required
def game_history():

    player_id = session["player_id"]

    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute(
        """
        SELECT id, word, score, result, played_at
        FROM game_history
        WHERE player_id = ?
        ORDER BY id DESC
        LIMIT 50
        """,
        (player_id,)
    )

    games = cursor.fetchall()

    cursor.execute(
        """
        SELECT COUNT(*)
        FROM game_history
        WHERE player_id = ?
        """,
        (player_id,)
    )

    total_games = cursor.fetchone()[0]

    cursor.execute(
        """
        SELECT COUNT(*)
        FROM game_history
        WHERE player_id = ? AND result = 'Win'
        """,
        (player_id,)
    )

    total_wins = cursor.fetchone()[0]

    cursor.execute(
        """
        SELECT COUNT(*)
        FROM game_history
        WHERE player_id = ? AND result = 'Loss'
        """,
        (player_id,)
    )

    total_losses = cursor.fetchone()[0]

    cursor.execute(
        """
        SELECT COALESCE(SUM(score), 0)
        FROM game_history
        WHERE player_id = ?
        """,
        (player_id,)
    )

    total_xp = cursor.fetchone()[0]

    conn.close()

    return render_template(
        "game_history.html",
        games=games,
        total_games=total_games,
        total_wins=total_wins,
        total_losses=total_losses,
        total_xp=total_xp
    )


# =======================================
# PLAYER PROFILE PAGE
# =======================================

@app.route("/profile")
@login_required
def profile():

    player_id = session["player_id"]

    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute(
        """
        SELECT id, username, xp, level, created_at
        FROM players
        WHERE id = ?
        """,
        (player_id,)
    )

    player = cursor.fetchone()

    cursor.execute(
        """
        SELECT COUNT(*)
        FROM game_history
        WHERE player_id = ?
        """,
        (player_id,)
    )

    total_games = cursor.fetchone()[0]

    cursor.execute(
        """
        SELECT COUNT(*)
        FROM game_history
        WHERE player_id = ? AND result = 'Win'
        """,
        (player_id,)
    )

    total_wins = cursor.fetchone()[0]

    cursor.execute(
        """
        SELECT COUNT(*)
        FROM game_history
        WHERE player_id = ? AND result = 'Loss'
        """,
        (player_id,)
    )

    total_losses = cursor.fetchone()[0]

    cursor.execute(
        """
        SELECT id, word, score, result, played_at
        FROM game_history
        WHERE player_id = ?
        ORDER BY id DESC
        LIMIT 5
        """,
        (player_id,)
    )

    recent_games = cursor.fetchall()

    cursor.execute(
        """
        SELECT badge_name
        FROM badges
        WHERE player_id = ?
        """,
        (player_id,)
    )

    badge_rows = cursor.fetchall()

    conn.close()

    unlocked_names = set()

    for row in badge_rows:
        unlocked_names.add(row["badge_name"])

    unlocked_badges = []

    for badge in BADGE_DETAILS:

        if badge["name"] in unlocked_names:
            unlocked_badges.append(badge)

    win_rate = 0

    if total_games > 0:
        win_rate = round(
            (total_wins / total_games) * 100,
            1
        )

    return render_template(
        "profile.html",
        player=player,
        total_games=total_games,
        total_wins=total_wins,
        total_losses=total_losses,
        win_rate=win_rate,
        recent_games=recent_games,
        unlocked_badges=unlocked_badges,
        badge_count=len(unlocked_badges)
    )


# =======================================
# LOGOUT
# =======================================

@app.route("/logout")
def logout():

    session.clear()

    return redirect(url_for("index"))


# =======================================
# RUN APPLICATION
# =======================================

if __name__ == "__main__":

    print("------------------------------------")
    print("          HANGMAN ARENA")
    print("------------------------------------")
    print("Word bank loaded:", len(WORD_BANK), "words")
    print("Daily Challenge: Enabled")
    print("Server starting...")
    print("Open: http://127.0.0.1:5000")
    print("------------------------------------")

    app.run(debug=True)