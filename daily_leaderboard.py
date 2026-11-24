
from flask import Blueprint, render_template, session, redirect, url_for
from functools import wraps
from datetime import date
from database import get_connection


daily_leaderboard_bp = Blueprint(
    "daily_leaderboard",
    __name__
)


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
# DAILY LEADERBOARD
# =======================================

@daily_leaderboard_bp.route("/daily-leaderboard")
@login_required
def daily_leaderboard():

    today = date.today()
    today_string = today.isoformat()

    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute(
        """
        SELECT
            d.player_id,
            p.username,
            p.level,
            d.result,
            d.score,
            d.challenge_date
        FROM daily_challenge_history d
        JOIN players p
            ON d.player_id = p.id
        WHERE d.challenge_date = ?
        ORDER BY
            CASE
                WHEN d.result = 'Win' THEN 0
                ELSE 1
            END,
            d.score DESC,
            d.player_id ASC
        LIMIT 50
        """,
        (today_string,)
    )

    players = cursor.fetchall()
    conn.close()

    total_players = len(players)
    total_winners = 0
    top_score = 0
    current_player_rank = None

    for index, player in enumerate(players):

        if player["result"] == "Win":
            total_winners += 1

        if index == 0:
            top_score = player["score"]

        if player["player_id"] == session["player_id"]:
            current_player_rank = index + 1

    return render_template(
        "daily_leaderboard.html",
        players=players,
        current_player=session["player_id"],
        total_players=total_players,
        total_winners=total_winners,
        top_score=top_score,
        current_player_rank=current_player_rank,
        challenge_date=today.strftime("%d %B %Y")
    )


# =======================================
# PLAYER PERFORMANCE ANALYTICS
# =======================================

@daily_leaderboard_bp.route("/analytics")
@login_required
def analytics():

    player_id = session["player_id"]

    conn = get_connection()
    cursor = conn.cursor()

    # Overall game statistics

    cursor.execute(
        """
        SELECT
            COUNT(*) AS total_games,

            COALESCE(
                SUM(
                    CASE
                        WHEN result = 'Win' THEN 1
                        ELSE 0
                    END
                ),
                0
            ) AS total_wins,

            COALESCE(
                SUM(
                    CASE
                        WHEN result = 'Loss' THEN 1
                        ELSE 0
                    END
                ),
                0
            ) AS total_losses,

            COALESCE(SUM(score), 0) AS total_xp,

            COALESCE(MAX(score), 0) AS best_score

        FROM game_history
        WHERE player_id = ?
        """,
        (player_id,)
    )

    stats = cursor.fetchone()

    total_games = stats["total_games"]
    total_wins = stats["total_wins"]
    total_losses = stats["total_losses"]
    total_xp = stats["total_xp"]
    best_score = stats["best_score"]

    # Daily challenge statistics

    cursor.execute(
        """
        SELECT
            COUNT(*) AS daily_games,

            COALESCE(
                SUM(
                    CASE
                        WHEN result = 'Win' THEN 1
                        ELSE 0
                    END
                ),
                0
            ) AS daily_wins,

            COALESCE(SUM(score), 0) AS daily_xp

        FROM daily_challenge_history
        WHERE player_id = ?
        """,
        (player_id,)
    )

    daily_stats = cursor.fetchone()

    daily_games = daily_stats["daily_games"]
    daily_wins = daily_stats["daily_wins"]
    daily_xp = daily_stats["daily_xp"]

    # Latest 10 games

    cursor.execute(
        """
        SELECT
            id,
            word,
            score,
            result,
            played_at
        FROM game_history
        WHERE player_id = ?
        ORDER BY id DESC
        LIMIT 10
        """,
        (player_id,)
    )

    recent_games = cursor.fetchall()

    conn.close()

    # Calculate win percentage

    win_rate = 0

    if total_games > 0:
        win_rate = round(
            (total_wins / total_games) * 100,
            1
        )

    # Calculate average XP per win

    average_xp = 0

    if total_wins > 0:
        average_xp = round(
            total_xp / total_wins,
            1
        )

    # Find highest recent score

    max_recent_score = 0

    for game in recent_games:

        if game["score"] > max_recent_score:
            max_recent_score = game["score"]

    return render_template(
        "analytics.html",
        total_games=total_games,
        total_wins=total_wins,
        total_losses=total_losses,
        total_xp=total_xp,
        best_score=best_score,
        win_rate=win_rate,
        average_xp=average_xp,
        daily_games=daily_games,
        daily_wins=daily_wins,
        daily_xp=daily_xp,
        recent_games=recent_games,
        max_recent_score=max_recent_score
    )
