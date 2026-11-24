
from flask import Blueprint, render_template, request, redirect, url_for, session, flash
from functools import wraps
from werkzeug.security import check_password_hash, generate_password_hash
from database import get_connection


account_settings_bp = Blueprint(
    "account_settings",
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
# ACCOUNT SETTINGS
# =======================================

@account_settings_bp.route("/settings", methods=["GET", "POST"])
@login_required
def settings():

    player_id = session["player_id"]

    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute(
        """
        SELECT id, username, password, xp, level, created_at
        FROM players
        WHERE id = ?
        """,
        (player_id,)
    )

    player = cursor.fetchone()

    if not player:

        conn.close()
        session.clear()

        flash("Account not found. Please login again.")

        return redirect(url_for("login"))

    if request.method == "POST":

        current_password = request.form.get(
            "current_password",
            ""
        )

        new_password = request.form.get(
            "new_password",
            ""
        )

        confirm_password = request.form.get(
            "confirm_password",
            ""
        )

        # Check current password

        if not check_password_hash(
            player["password"],
            current_password
        ):

            flash("Current password is incorrect.")

        # Validate new password length

        elif len(new_password) < 6:

            flash("New password must contain at least 6 characters.")

        # Validate matching passwords

        elif new_password != confirm_password:

            flash("New password and confirm password do not match.")

        # Prevent keeping the same password

        elif check_password_hash(
            player["password"],
            new_password
        ):

            flash("New password must be different from the current password.")

        else:

            new_hashed_password = generate_password_hash(
                new_password
            )

            cursor.execute(
                """
                UPDATE players
                SET password = ?
                WHERE id = ?
                """,
                (
                    new_hashed_password,
                    player_id
                )
            )

            conn.commit()

            conn.close()

            flash("Password changed successfully!")

            return redirect(
                url_for("account_settings.settings")
            )

    conn.close()

    return render_template(
        "settings.html",
        player=player
    )
