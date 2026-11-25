
from flask import (
    Blueprint,
    render_template,
    request,
    redirect,
    url_for,
    session,
    flash
)
from functools import wraps
from database import get_connection, is_postgres
from pathlib import Path
import random
import string


multiplayer_bp = Blueprint(
    "multiplayer",
    __name__
)


WINNER_REWARD = 150
MAX_WRONG_GUESSES = 6


# =======================================
# DATABASE INITIALIZATION
# =======================================

@multiplayer_bp.before_request
def initialize_multiplayer_database():

    conn = get_connection()
    cursor = conn.cursor()

    try:
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS multiplayer_rooms (

                id INTEGER PRIMARY KEY AUTOINCREMENT,

                room_code TEXT UNIQUE NOT NULL,

                host_id INTEGER NOT NULL,

                guest_id INTEGER,

                word TEXT NOT NULL,

                guessed_letters TEXT DEFAULT '',

                wrong INTEGER DEFAULT 0,

                max_attempts INTEGER DEFAULT 6,

                status TEXT DEFAULT 'waiting',

                turn_player_id INTEGER,

                last_guess TEXT,

                last_guess_player_id INTEGER,

                last_guess_correct INTEGER,

                winner_id INTEGER,

                xp_reward INTEGER DEFAULT 150,

                created_at TEXT DEFAULT CURRENT_TIMESTAMP,

                updated_at TEXT DEFAULT CURRENT_TIMESTAMP

            )
        """)

        conn.commit()

    except Exception:
        conn.rollback()
        raise

    finally:
        conn.close()


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
# LOAD WORD BANK
# =======================================

def get_multiplayer_word():

    word_path = (
        Path(__file__).resolve().parent
        / "data"
        / "word_bank.txt"
    )

    if not word_path.is_file():
        raise FileNotFoundError(
            "Word bank not found. Check data/word_bank.txt"
        )

    words = []

    with word_path.open("r", encoding="utf-8") as file:

        for line in file:

            word = line.strip().upper()

            if word.isalpha() and 6 <= len(word) <= 8:
                words.append(word)

    words = sorted(set(words))

    if not words:
        raise ValueError(
            "No multiplayer words available."
        )

    return random.choice(words)


# =======================================
# GENERATE ROOM CODE
# =======================================

def generate_room_code():

    characters = string.ascii_uppercase + string.digits

    return "".join(
        random.choice(characters)
        for _ in range(6)
    )


# =======================================
# AWARD MULTIPLAYER BADGES
# =======================================

def award_multiplayer_badges(cursor, player_id):

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

    if not player:
        return

    player_xp = player["xp"]

    cursor.execute(
        """
        SELECT badge_name
        FROM badges
        WHERE player_id = ?
        """,
        (player_id,)
    )

    existing_badges = {
        row["badge_name"]
        for row in cursor.fetchall()
    }

    new_badges = []

    if total_wins >= 1:
        new_badges.append("First Victory")

    if total_wins >= 5:
        new_badges.append("Rising Star")

    if total_wins >= 10:
        new_badges.append("Arena Legend")

    if player_xp >= 500:
        new_badges.append("XP Hunter")

    for badge in new_badges:

        if badge not in existing_badges:

            cursor.execute(
                """
                INSERT INTO badges
                (player_id, badge_name)
                VALUES (?, ?)
                """,
                (player_id, badge)
            )


# =======================================
# MULTIPLAYER HOME PAGE
# =======================================

@multiplayer_bp.route("/multiplayer")
@login_required
def lobby():

    player_id = session["player_id"]

    conn = get_connection()
    cursor = conn.cursor()

    try:
        cursor.execute(
            """
            SELECT
                r.room_code,
                r.status,
                r.created_at,
                p1.username AS host_username,
                p2.username AS guest_username

            FROM multiplayer_rooms r

            JOIN players p1
                ON r.host_id = p1.id

            LEFT JOIN players p2
                ON r.guest_id = p2.id

            WHERE r.host_id = ? OR r.guest_id = ?

            ORDER BY r.id DESC

            LIMIT 10
            """,
            (player_id, player_id)
        )

        rooms = cursor.fetchall()

    finally:
        conn.close()

    return render_template(
        "multiplayer.html",
        rooms=rooms
    )


# =======================================
# CREATE ROOM
# =======================================

@multiplayer_bp.route(
    "/multiplayer/create",
    methods=["POST"]
)
@login_required
def create_room():

    player_id = session["player_id"]

    word = get_multiplayer_word()

    conn = get_connection()
    cursor = conn.cursor()

    room_code = None

    try:
        for attempt in range(10):

            candidate = generate_room_code()

            try:
                cursor.execute(
                    """
                    INSERT INTO multiplayer_rooms
                    (
                        room_code,
                        host_id,
                        word,
                        guessed_letters,
                        wrong,
                        max_attempts,
                        status,
                        turn_player_id
                    )
                    VALUES (?, ?, ?, '', 0, ?, 'waiting', ?)
                    """,
                    (
                        candidate,
                        player_id,
                        word,
                        MAX_WRONG_GUESSES,
                        player_id
                    )
                )

                room_code = candidate
                break

            except Exception:

                conn.rollback()

        if not room_code:

            flash("Unable to create room. Please try again.")

            return redirect(
                url_for("multiplayer.lobby")
            )

        conn.commit()

    except Exception:
        conn.rollback()
        raise

    finally:
        conn.close()

    flash("Room created! Share the invite code with your friend.")

    return redirect(
        url_for(
            "multiplayer.room",
            room_code=room_code
        )
    )


# =======================================
# JOIN ROOM
# =======================================

@multiplayer_bp.route(
    "/multiplayer/join",
    methods=["POST"]
)
@login_required
def join_room():

    player_id = session["player_id"]

    room_code = request.form.get(
        "room_code",
        ""
    ).strip().upper()

    if len(room_code) != 6:

        flash("Please enter a valid 6-character room code.")

        return redirect(url_for("multiplayer.lobby"))

    conn = get_connection()
    cursor = conn.cursor()

    try:
        cursor.execute(
            """
            SELECT *
            FROM multiplayer_rooms
            WHERE room_code = ?
            """,
            (room_code,)
        )

        room = cursor.fetchone()

        if not room:

            flash("Room not found. Check the invite code.")

            return redirect(url_for("multiplayer.lobby"))

        if room["host_id"] == player_id:

            return redirect(
                url_for(
                    "multiplayer.room",
                    room_code=room_code
                )
            )

        if (
            room["status"] != "waiting"
            or room["guest_id"] is not None
        ):

            flash("This room is already full or finished.")

            return redirect(url_for("multiplayer.lobby"))

        cursor.execute(
            """
            UPDATE multiplayer_rooms

            SET guest_id = ?,
                status = 'active',
                turn_player_id = host_id,
                updated_at = CURRENT_TIMESTAMP

            WHERE room_code = ?
              AND status = 'waiting'
              AND guest_id IS NULL
            """,
            (player_id, room_code)
        )

        if cursor.rowcount != 1:

            conn.rollback()

            flash("This room is no longer available.")

            return redirect(url_for("multiplayer.lobby"))

        conn.commit()

    except Exception:
        conn.rollback()
        raise

    finally:
        conn.close()

    flash("You joined the multiplayer room!")

    return redirect(
        url_for(
            "multiplayer.room",
            room_code=room_code
        )
    )


# =======================================
# MULTIPLAYER GAME ROOM
# =======================================

@multiplayer_bp.route(
    "/multiplayer/room/<room_code>",
    methods=["GET", "POST"]
)
@login_required
def room(room_code):

    player_id = session["player_id"]

    conn = get_connection()
    cursor = conn.cursor()

    try:

        # -----------------------------------
        # HANDLE PLAYER GUESS
        # -----------------------------------

        if request.method == "POST":

            guess = request.form.get(
                "guess",
                ""
            ).strip().upper()

            # SQLite and PostgreSQL use different
            # transaction locking mechanisms.
            if not is_postgres():
                cursor.execute("BEGIN IMMEDIATE")

            room_query = """
                SELECT *
                FROM multiplayer_rooms
                WHERE room_code = ?
            """

            # Lock the selected room row so two players
            # cannot update the same turn simultaneously.
            if is_postgres():
                room_query += " FOR UPDATE"

            cursor.execute(
                room_query,
                (room_code.upper(),)
            )

            room_data = cursor.fetchone()

            if not room_data:

                conn.rollback()

                flash("Room not found.")

                return redirect(url_for("multiplayer.lobby"))

            if player_id not in (
                room_data["host_id"],
                room_data["guest_id"]
            ):

                conn.rollback()

                flash("You are not a member of this room.")

                return redirect(url_for("multiplayer.lobby"))

            if room_data["status"] != "active":

                conn.rollback()

                flash("This game is not active.")

                return redirect(
                    url_for(
                        "multiplayer.room",
                        room_code=room_code
                    )
                )

            if room_data["turn_player_id"] != player_id:

                conn.rollback()

                flash("Wait for your turn.")

                return redirect(
                    url_for(
                        "multiplayer.room",
                        room_code=room_code
                    )
                )

            if (
                len(guess) != 1
                or guess not in string.ascii_uppercase
            ):

                conn.rollback()

                flash("Please select a valid letter.")

                return redirect(
                    url_for(
                        "multiplayer.room",
                        room_code=room_code
                    )
                )

            old_guesses = room_data["guessed_letters"] or ""

            if guess in old_guesses:

                conn.rollback()

                flash("This letter was already guessed.")

                return redirect(
                    url_for(
                        "multiplayer.room",
                        room_code=room_code
                    )
                )

            word = room_data["word"]

            new_guesses = old_guesses + guess

            wrong = room_data["wrong"]

            is_correct = guess in word

            if not is_correct:
                wrong += 1

            if room_data["host_id"] == player_id:
                opponent_id = room_data["guest_id"]
            else:
                opponent_id = room_data["host_id"]

            # Check whether every unique letter is revealed.
            has_won = set(word.upper()).issubset(
                set(new_guesses.upper())
            )

            has_lost = wrong >= room_data["max_attempts"]

            winner_id = None
            new_status = "active"
            next_turn = opponent_id

            # Victory has priority over defeat.
            if has_won:

                winner_id = player_id
                new_status = "completed"

            elif has_lost:

                winner_id = opponent_id
                new_status = "completed"

            # --------------------------------
            # FINISH MATCH
            # --------------------------------

            if new_status == "completed":

                cursor.execute(
                    """
                    UPDATE multiplayer_rooms

                    SET guessed_letters = ?,
                        wrong = ?,
                        status = 'completed',
                        winner_id = ?,
                        last_guess = ?,
                        last_guess_player_id = ?,
                        last_guess_correct = ?,
                        updated_at = CURRENT_TIMESTAMP

                    WHERE id = ?
                    """,
                    (
                        new_guesses,
                        wrong,
                        winner_id,
                        guess,
                        player_id,
                        1 if is_correct else 0,
                        room_data["id"]
                    )
                )

                loser_id = (
                    room_data["guest_id"]
                    if winner_id == room_data["host_id"]
                    else room_data["host_id"]
                )

                # Save winner's history.
                cursor.execute(
                    """
                    INSERT INTO game_history
                    (player_id, word, score, result)
                    VALUES (?, ?, ?, 'Win')
                    """,
                    (
                        winner_id,
                        word,
                        WINNER_REWARD
                    )
                )

                # Save loser's history.
                cursor.execute(
                    """
                    INSERT INTO game_history
                    (player_id, word, score, result)
                    VALUES (?, ?, 0, 'Loss')
                    """,
                    (
                        loser_id,
                        word
                    )
                )

                # Award XP to winner.
                cursor.execute(
                    """
                    UPDATE players

                    SET xp = xp + ?,
                        level = CAST((xp + ?) / 500 AS INTEGER) + 1

                    WHERE id = ?
                    """,
                    (
                        WINNER_REWARD,
                        WINNER_REWARD,
                        winner_id
                    )
                )

                award_multiplayer_badges(
                    cursor,
                    winner_id
                )

                flash("Multiplayer match completed!")

            else:

                # --------------------------------
                # PASS TURN TO OPPONENT
                # --------------------------------

                cursor.execute(
                    """
                    UPDATE multiplayer_rooms

                    SET guessed_letters = ?,
                        wrong = ?,
                        turn_player_id = ?,
                        last_guess = ?,
                        last_guess_player_id = ?,
                        last_guess_correct = ?,
                        updated_at = CURRENT_TIMESTAMP

                    WHERE id = ?
                    """,
                    (
                        new_guesses,
                        wrong,
                        next_turn,
                        guess,
                        player_id,
                        1 if is_correct else 0,
                        room_data["id"]
                    )
                )

            conn.commit()

            return redirect(
                url_for(
                    "multiplayer.room",
                    room_code=room_code
                )
            )

        # -----------------------------------
        # DISPLAY ROOM
        # -----------------------------------

        cursor.execute(
            """
            SELECT
                r.*,

                p1.username AS host_username,

                p2.username AS guest_username,

                p3.username AS turn_username,

                p4.username AS winner_username

            FROM multiplayer_rooms r

            JOIN players p1
                ON r.host_id = p1.id

            LEFT JOIN players p2
                ON r.guest_id = p2.id

            LEFT JOIN players p3
                ON r.turn_player_id = p3.id

            LEFT JOIN players p4
                ON r.winner_id = p4.id

            WHERE r.room_code = ?
            """,
            (room_code.upper(),)
        )

        room_data = cursor.fetchone()

        if not room_data:

            flash("Room not found.")

            return redirect(url_for("multiplayer.lobby"))

        if player_id not in (
            room_data["host_id"],
            room_data["guest_id"]
        ):

            flash("You are not allowed to access this room.")

            return redirect(url_for("multiplayer.lobby"))

        guessed = room_data["guessed_letters"] or ""

        if room_data["status"] == "waiting":

            display_word = ""

        else:

            display_word = " ".join(
                letter if letter in guessed else "_"
                for letter in room_data["word"]
            )

        correct_guesses = [
            letter for letter in guessed
            if letter in room_data["word"]
        ]

        wrong_guesses = [
            letter for letter in guessed
            if letter not in room_data["word"]
        ]

        is_my_turn = (
            room_data["status"] == "active"
            and room_data["turn_player_id"] == player_id
        )

        is_winner = room_data["winner_id"] == player_id

        if player_id == room_data["host_id"]:
            opponent_name = room_data["guest_username"]
        else:
            opponent_name = room_data["host_username"]

        return render_template(
            "multiplayer_game.html",
            room=room_data,
            display_word=display_word,
            guessed=guessed,
            correct_guesses=correct_guesses,
            wrong_guesses=wrong_guesses,
            is_my_turn=is_my_turn,
            is_winner=is_winner,
            opponent_name=opponent_name,
            current_player_id=player_id
        )

    except Exception:
        conn.rollback()
        raise

    finally:
        conn.close()
