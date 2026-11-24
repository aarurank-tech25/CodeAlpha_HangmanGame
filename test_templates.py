import jinja2, sys

env = jinja2.Environment(loader=jinja2.FileSystemLoader('templates'), undefined=jinja2.Undefined)
env.globals['url_for'] = lambda endpoint, **kwargs: f'/{endpoint}'
env.globals['get_flashed_messages'] = lambda **kw: []

ctx = {
    'player': {'username': 'TestPlayer', 'level': 5, 'xp': 1250, 'created_at': '2026-01-01', 'id': 1, 'email': 'test@example.com'},
    'username': 'TestPlayer', 'level': 5, 'xp': 1250, 'player_xp': 1250, 'xp_to_next': 500,
    'next_level_xp': 1500, 'xp_progress': 65,
    'total_games': 42, 'total_wins': 28, 'wins': 28, 'win_rate': 67, 'best_score': 320,
    'recent_games': [{'id':1,'word':'PYTHON','result':'Win','score':150,'difficulty':'Medium','date':'2026-01-01'}],
    'leaderboard': [{'rank':1,'username':'Alpha','level':10,'score':500,'player_id':1}],
    'current_player': 1,
    'achievements': [{'name':'First Win','description':'Win your first game','icon':'trophy','earned':True,'earned_date':'2026-01-01'}],
    'unlocked_count': 3, 'total_achievements': 10, 'total_badges': 3,
    'history': [{'id':1,'word':'PYTHON','result':'Win','score':150,'difficulty':'Medium','date':'2026-01-01','time_taken':45,'hints_used':0}],
    'page': 1, 'total_pages': 3,
    'player_id': 1, 'join_date': '2026-01-01', 'games_played': 42, 'win_percentage': 67,
    'daily_wins': 5, 'total_xp': 2500, 'recent_history': [],
    'has_played_today': False, 'today_result': None, 'today_score': 0,
    'daily_word': 'ARENA', 'daily_category': 'Gaming',
    'display_word': '_ _ _ _ _', 'wrong': 2, 'remaining_lives': 4, 'max_attempts': 6,
    'remaining_time': 60, 'difficulty': 'Medium', 'game_over': True, 'result': 'Win',
    'guessed': ['A','B'], 'correct_guesses': ['A'], 'wrong_guesses': ['B'],
    'hint_used': False, 'score': 180, 'difficulty_bonus': 50, 'answer': 'ARENA',
    'rooms': [{'room_code':'ABC123','player1':'Alpha','player2':'Beta','status':'waiting'}],
    'room': {
        'room_code':'ABC123','player1_id':1,'player2_id':2,
        'player1_username':'Alpha','player2_username':'Beta',
        'display_word':'_ _ _ _ _','wrong':0,'max_attempts':6,
        'remaining_lives':6,'difficulty':'Medium','game_over':False,
        'result':None,'current_turn':1,'turn_username':'Alpha',
        'guessed':[],'correct_guesses':[],'wrong_guesses':[],'hint_used':False
    },
    'mp_leaderboard': [{'rank':1,'username':'Alpha','wins':10,'losses':2,'win_rate':83,'player_id':1}],
    'challenge_date': '2026-01-15', 'total_players': 50, 'total_winners': 32,
    'top_score': 400, 'players': [{'player_id':1,'username':'Alpha','result':'Win','score':400,'level':10}],
    'total_losses': 14, 'daily_xp': 500, 'average_xp': 100,
    'daily_games': 15, 'max_recent_score': 300,
    'email': 'test@example.com',
}

templates = [
    'index.html','login.html','register.html','dashboard.html',
    'difficulty.html','game.html','leaderboard.html','achievements.html',
    'game_history.html','profile.html','daily_challenge.html',
    'daily_leaderboard.html','analytics.html','multiplayer.html',
    'multiplayer_game.html','multiplayer_leaderboard.html','settings.html'
]

ok = 0; fail = 0
for t in templates:
    try:
        tpl = env.get_template(t)
        tpl.render(**ctx)
        print(f'  OK   {t}')
        ok += 1
    except Exception as e:
        print(f'  FAIL {t} -> {e}')
        fail += 1

print(f'\n=== Jinja Standalone: {ok} passed, {fail} failed ===')

# Also verify using Flask real test_request_context for URL resolution
try:
    from app import app
    from flask import render_template
    flask_ok = 0
    flask_fail = 0
    with app.test_request_context():
        for t in templates:
            try:
                render_template(t, **ctx)
                flask_ok += 1
            except Exception as e:
                print(f'  Flask url_for FAIL: {t} -> {e}')
                flask_fail += 1
    print(f'=== Flask Request Context: {flask_ok} passed, {flask_fail} failed ===\n')
    if flask_fail > 0:
        fail += flask_fail
except Exception as e:
    print(f'Could not run Flask context test: {e}')

sys.exit(0 if fail == 0 else 1)
