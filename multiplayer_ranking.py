
from flask import Blueprint, render_template, session, redirect, url_for
from functools import wraps
from database import get_connection


multiplayer_ranking_bp = Blueprint(
    "multiplayer_ranking",
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
# MULTIPLAYER LEADERBOARD
# =======================================

@multiplayer_ranking_bp.route("/multiplayer-leaderboard")
@login_required
def leaderboard():

    player_id = session["player_id"]

    conn = get_connection()
    cursor = conn.cursor()

    try:

        # Player rankings
        cursor.execute(
            """
            SELECT
                p.id AS player_id,
                p.username,
                p.level,
                p.xp,

                COALESCE(
                    SUM(
                        CASE
                            WHEN r.status = 'completed'
                             AND r.winner_id = p.id
                            THEN 1
                            ELSE 0
                        END
                    ),
                    0
                ) AS multiplayer_wins,

                COALESCE(
                    SUM(
                        CASE
                            WHEN r.status = 'completed'
                             AND r.winner_id = p.id
                            THEN r.xp_reward
                            ELSE 0
                        END
                    ),
                    0
                ) AS multiplayer_xp,

                COALESCE(
                    SUM(
                        CASE
                            WHEN r.status = 'completed'
                             AND (
                                 r.host_id = p.id
                                 OR r.guest_id = p.id
                             )
                            THEN 1
                            ELSE 0
                        END
                    ),
                    0
                ) AS matches_played

            FROM players p

            LEFT JOIN multiplayer_rooms r
                ON (
                    r.host_id = p.id
                    OR r.guest_id = p.id
                )

            GROUP BY
                p.id,
                p.username,
                p.level,
                p.xp

            HAVING SUM(
                CASE
                    WHEN r.status = 'completed'
                     AND (
                         r.host_id = p.id
                         OR r.guest_id = p.id
                     )
                    THEN 1
                    ELSE 0
                END
            ) > 0

            ORDER BY
                multiplayer_wins DESC,
                multiplayer_xp DESC,
                p.xp DESC,
                p.id ASC

            LIMIT 50
            """
        )

        players = cursor.fetchall()

        # Overall completed matches
        cursor.execute(
            """
            SELECT COUNT(*)
            FROM multiplayer_rooms
            WHERE status = 'completed'
              AND winner_id IS NOT NULL
            """
        )

        total_matches = cursor.fetchone()[0]

        # Total participating players
        cursor.execute(
            """
            SELECT COUNT(*)
            FROM players p

            WHERE EXISTS (
                SELECT 1
                FROM multiplayer_rooms r

                WHERE r.status = 'completed'
                  AND (
                      r.host_id = p.id
                      OR r.guest_id = p.id
                  )
            )
            """
        )

        total_players = cursor.fetchone()[0]

    finally:
        conn.close()

    # Current player's statistics
    current_player_rank = None
    current_player_wins = 0
    current_player_xp = 0
    current_player_matches = 0

    for index, player in enumerate(players):

        if player["player_id"] == player_id:

            current_player_rank = index + 1

            current_player_wins = player["multiplayer_wins"]

            current_player_xp = player["multiplayer_xp"]

            current_player_matches = player["matches_played"]

    # Top player's wins
    top_wins = 0

    if players:
        top_wins = players[0]["multiplayer_wins"]

    return render_template(
        "multiplayer_leaderboard.html",

        players=players,

        current_player=player_id,

        current_player_rank=current_player_rank,

        current_player_wins=current_player_wins,

        current_player_xp=current_player_xp,

        current_player_matches=current_player_matches,

        total_matches=total_matches,

        total_players=total_players,

        top_wins=top_wins
    )
