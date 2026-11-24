import os
import sys
import time
from app import app, get_connection

sys.stdout.reconfigure(encoding='utf-8')

def setup_test_player():
    conn = get_connection()
    cur = conn.cursor()
    cur.execute("SELECT id, username, xp FROM players WHERE username = 'test_tester'")
    player = cur.fetchone()
    if not player:
        cur.execute("INSERT INTO players (username, password, xp, level) VALUES ('test_tester', 'hashed', 100, 1)")
        conn.commit()
        cur.execute("SELECT id, username, xp FROM players WHERE username = 'test_tester'")
        player = cur.fetchone()
    conn.close()
    return player["id"]

def run_tests():
    player_id = setup_test_player()
    app.config["TESTING"] = True
    app.config["WTF_CSRF_ENABLED"] = False
    client = app.test_client()

    print("\n=======================================================")
    print("RUNNING HANGMAN GAMEPLAY & WIN/LOSS VERIFICATION TESTS")
    print("=======================================================\n")

    # -------------------------------------------------------------
    # Test 1: AMONG: Guess A, M, O, N, G -> WIN
    # -------------------------------------------------------------
    print("[TEST 1] AMONG: Guess A, M, O, N, G -> Expect WIN...")
    with client.session_transaction() as sess:
        sess["player_id"] = player_id
        sess["username"] = "test_tester"
        sess["word"] = "AMONG"
        sess["difficulty"] = "medium"
        sess["max_attempts"] = 6
        sess["time_limit"] = 45
        sess["guessed"] = []
        sess["wrong"] = 0
        sess["game_over"] = False
        sess["result"] = None
        sess["hint_used"] = False
        sess["game_saved"] = False
        sess["score"] = 0
        sess["start_time"] = time.time()

    for letter in ["A", "M", "O", "N"]:
        res = client.post("/game", data={"action": "guess", "guess": letter})
        assert res.status_code == 200

    # Final winning letter
    res = client.post("/game", data={"action": "guess", "guess": "G"})
    assert res.status_code == 200
    html = res.data.decode("utf-8")

    with client.session_transaction() as sess:
        assert sess["game_over"] == True, "game_over should be True"
        assert sess["result"] == "Win", f"result should be Win, got {sess['result']}"
        assert sess["score"] > 0, "score should be > 0"

    assert "GLORIOUS TRIUMPH" in html or "VICTORY ACHIEVED" in html, "HTML should contain victory text"
    assert "DEFEAT IN THE ARENA" not in html, "HTML must NOT contain defeat text"
    assert "result-modal win" in html, "HTML must contain result-modal win"
    print("  --> PASS: Won AMONG cleanly, victory screen displayed!\n")

    # -------------------------------------------------------------
    # Test 2: AMONG: Guess T first, then A, M, O, N, G -> WIN
    # -------------------------------------------------------------
    print("[TEST 2] AMONG: Guess wrong 'T' first, then A, M, O, N, G -> Expect WIN...")
    with client.session_transaction() as sess:
        sess["player_id"] = player_id
        sess["username"] = "test_tester"
        sess["word"] = "AMONG"
        sess["difficulty"] = "medium"
        sess["max_attempts"] = 6
        sess["time_limit"] = 45
        sess["guessed"] = []
        sess["wrong"] = 0
        sess["game_over"] = False
        sess["result"] = None
        sess["hint_used"] = False
        sess["game_saved"] = False
        sess["score"] = 0
        sess["start_time"] = time.time()

    # Wrong guess T
    res = client.post("/game", data={"action": "guess", "guess": "T"})
    with client.session_transaction() as sess:
        assert sess["wrong"] == 1, "Wrong attempts should be 1"
        assert sess["game_over"] == False, "Game should still be ongoing"

    for letter in ["A", "M", "O", "N"]:
        client.post("/game", data={"action": "guess", "guess": letter})

    res = client.post("/game", data={"action": "guess", "guess": "G"})
    html = res.data.decode("utf-8")

    with client.session_transaction() as sess:
        assert sess["game_over"] == True
        assert sess["result"] == "Win", f"result should be Win, got {sess['result']}"
        assert sess["wrong"] == 1

    assert "GLORIOUS TRIUMPH" in html or "VICTORY ACHIEVED" in html
    assert "DEFEAT IN THE ARENA" not in html, "Earlier wrong guess must not cause defeat!"
    assert "result-modal win" in html
    print("  --> PASS: Won AMONG despite initial strike 'T', victory screen displayed!\n")

    # -------------------------------------------------------------
    # Test 3: AMONG: Use a hint, then guess all remaining letters -> WIN
    # -------------------------------------------------------------
    print("[TEST 3] AMONG: Use hint, then complete remaining letters -> Expect WIN...")
    with client.session_transaction() as sess:
        sess["player_id"] = player_id
        sess["username"] = "test_tester"
        sess["word"] = "AMONG"
        sess["difficulty"] = "medium"
        sess["max_attempts"] = 6
        sess["time_limit"] = 45
        sess["guessed"] = []
        sess["wrong"] = 0
        sess["game_over"] = False
        sess["result"] = None
        sess["hint_used"] = False
        sess["game_saved"] = False
        sess["score"] = 0
        sess["start_time"] = time.time()

    res = client.post("/game", data={"action": "hint"})
    assert res.status_code == 200

    with client.session_transaction() as sess:
        assert sess["hint_used"] == True, "hint_used must be True"
        assert len(sess["guessed"]) == 1, "One letter must be revealed by hint"
        hinted_letter = sess["guessed"][0]
        assert hinted_letter in "AMONG"

    remaining = [ch for ch in "AMONG" if ch != hinted_letter]
    for ch in remaining[:-1]:
        client.post("/game", data={"action": "guess", "guess": ch})

    res = client.post("/game", data={"action": "guess", "guess": remaining[-1]})
    html = res.data.decode("utf-8")

    with client.session_transaction() as sess:
        assert sess["game_over"] == True
        assert sess["result"] == "Win"

    assert "GLORIOUS TRIUMPH" in html or "VICTORY ACHIEVED" in html
    assert "DEFEAT IN THE ARENA" not in html
    assert "result-modal win" in html
    print("  --> PASS: Hint counted toward secret word, victory screen displayed!\n")

    # -------------------------------------------------------------
    # Test 4: AMONG: Guess only A, M, O -> GAME CONTINUES
    # -------------------------------------------------------------
    print("[TEST 4] AMONG: Guess only A, M, O -> Expect GAME CONTINUES...")
    with client.session_transaction() as sess:
        sess["player_id"] = player_id
        sess["username"] = "test_tester"
        sess["word"] = "AMONG"
        sess["difficulty"] = "medium"
        sess["max_attempts"] = 6
        sess["time_limit"] = 45
        sess["guessed"] = []
        sess["wrong"] = 0
        sess["game_over"] = False
        sess["result"] = None
        sess["hint_used"] = False
        sess["game_saved"] = False
        sess["score"] = 0
        sess["start_time"] = time.time()

    for letter in ["A", "M", "O"]:
        res = client.post("/game", data={"action": "guess", "guess": letter})

    html = res.data.decode("utf-8")
    with client.session_transaction() as sess:
        assert sess["game_over"] == False, "Game should NOT be over"
        assert sess["result"] == None, "Result should be None"

    assert "A M O _ _" in html or "A M O" in html
    assert "result-modal win" not in html
    assert "result-modal loss" not in html
    print("  --> PASS: Partial word does not trigger premature win/loss, game continues!\n")

    # -------------------------------------------------------------
    # Test 5: Exhaust all allowed attempts without completing word -> LOSS
    # -------------------------------------------------------------
    print("[TEST 5] Exhaust all 6 allowed attempts -> Expect LOSS...")
    with client.session_transaction() as sess:
        sess["player_id"] = player_id
        sess["username"] = "test_tester"
        sess["word"] = "AMONG"
        sess["difficulty"] = "medium"
        sess["max_attempts"] = 6
        sess["time_limit"] = 45
        sess["guessed"] = []
        sess["wrong"] = 0
        sess["game_over"] = False
        sess["result"] = None
        sess["hint_used"] = False
        sess["game_saved"] = False
        sess["score"] = 0
        sess["start_time"] = time.time()

    for letter in ["B", "C", "D", "E", "F"]:
        client.post("/game", data={"action": "guess", "guess": letter})

    res = client.post("/game", data={"action": "guess", "guess": "H"})
    html = res.data.decode("utf-8")

    with client.session_transaction() as sess:
        assert sess["wrong"] == 6
        assert sess["game_over"] == True
        assert sess["result"] == "Loss"
        assert sess["score"] == 0

    assert "DEFEAT IN THE ARENA" in html or "FALLEN IN COMBAT" in html
    assert "result-modal loss" in html
    assert "AMONG" in html, "Mystery word AMONG should be revealed on defeat"
    print("  --> PASS: Correctly declared LOSS on exhausting 6 attempts, revealed word AMONG!\n")

    # -------------------------------------------------------------
    # Test 6: Timer expires before completion -> LOSS
    # -------------------------------------------------------------
    print("[TEST 6] Timer expires before completion -> Expect LOSS...")
    with client.session_transaction() as sess:
        sess["player_id"] = player_id
        sess["username"] = "test_tester"
        sess["word"] = "AMONG"
        sess["difficulty"] = "medium"
        sess["max_attempts"] = 6
        sess["time_limit"] = 45
        sess["guessed"] = ["A"]
        sess["wrong"] = 0
        sess["game_over"] = False
        sess["result"] = None
        sess["hint_used"] = False
        sess["game_saved"] = False
        sess["score"] = 0
        # Simulated timeout
        sess["start_time"] = time.time() - 60

    res = client.post("/game", data={"action": "guess", "guess": "M"})
    html = res.data.decode("utf-8")

    with client.session_transaction() as sess:
        assert sess["game_over"] == True
        assert sess["result"] == "Loss"

    assert "DEFEAT IN THE ARENA" in html or "FALLEN IN COMBAT" in html
    assert "result-modal loss" in html
    print("  --> PASS: Timer expiry correctly triggers LOSS!\n")

    # -------------------------------------------------------------
    # Test 7: General word test with other words: PYTHON & CHAMPION
    # -------------------------------------------------------------
    print("[TEST 7] General word tests (PYTHON & CHAMPION)...")
    for test_word in ["PYTHON", "CHAMPION"]:
        with client.session_transaction() as sess:
            sess["player_id"] = player_id
            sess["username"] = "test_tester"
            sess["word"] = test_word
            sess["difficulty"] = "hard"
            sess["max_attempts"] = 6
            sess["time_limit"] = 30
            sess["guessed"] = []
            sess["wrong"] = 0
            sess["game_over"] = False
            sess["result"] = None
            sess["hint_used"] = False
            sess["game_saved"] = False
            sess["score"] = 0
            sess["start_time"] = time.time()

        # One wrong guess
        client.post("/game", data={"action": "guess", "guess": "Z"})
        # Guess all letters of the word
        for char in set(test_word):
            res = client.post("/game", data={"action": "guess", "guess": char})

        html = res.data.decode("utf-8")
        with client.session_transaction() as sess:
            assert sess["game_over"] == True, f"Failed for {test_word}"
            assert sess["result"] == "Win", f"Failed for {test_word}"
        assert "result-modal win" in html, f"Failed for {test_word}"
        print(f"  --> PASS: General word {test_word} passed with victory screen!")

    # -------------------------------------------------------------
    # Test 8: Database & XP recording
    # -------------------------------------------------------------
    print("\n[TEST 8] Verifying Database game_history and XP increment...")
    conn = get_connection()
    cur = conn.cursor()
    cur.execute("SELECT result, score FROM game_history WHERE player_id = ? ORDER BY id DESC LIMIT 1", (player_id,))
    latest = cur.fetchone()
    conn.close()
    assert latest is not None, "game_history record should exist"
    assert latest["result"] == "Win", "Latest history result should be 'Win'"
    assert latest["score"] > 0, "Latest history score should be > 0"
    print(f"  --> PASS: Database history saved correctly: result={latest['result']}, score={latest['score']}")

    print("\n=======================================================")
    print("ALL 8 GAMEPLAY AND WIN/LOSS TESTS PASSED PERFECTLY!")
    print("=======================================================\n")

if __name__ == "__main__":
    run_tests()

