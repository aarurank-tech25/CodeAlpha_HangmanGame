import sys
import os
import unittest
import uuid

from app import app
from flask import url_for
from database import get_connection

class HangmanArenaIntegrationTest(unittest.TestCase):
    def setUp(self):
        app.config['TESTING'] = True
        app.config['WTF_CSRF_ENABLED'] = False
        self.client = app.test_client()

    def test_public_pages(self):
        response = self.client.get('/')
        self.assertEqual(response.status_code, 200)
        self.assertIn(b'HANGMAN ARENA', response.data)

        response = self.client.get('/login')
        self.assertEqual(response.status_code, 200)
        self.assertIn(b'WELCOME BACK', response.data)

        response = self.client.get('/register')
        self.assertEqual(response.status_code, 200)
        self.assertIn(b'JOIN THE ARENA', response.data)

    def test_auth_and_protected_pages(self):
        protected_endpoints = [
            'dashboard', 'difficulty', 'leaderboard', 'achievements',
            'game_history', 'profile', 'daily_challenge',
            'daily_leaderboard.daily_leaderboard', 'daily_leaderboard.analytics',
            'multiplayer.lobby', 'multiplayer_ranking.leaderboard',
            'account_settings.settings'
        ]

        with app.test_request_context():
            urls = [url_for(ep) for ep in protected_endpoints]

        # Unauthenticated redirects to login
        for url in urls:
            resp = self.client.get(url)
            self.assertEqual(resp.status_code, 302, f"Failed unauth 302 check for {url}")

        # Check existing user in DB
        conn = get_connection()
        user = conn.execute("SELECT * FROM players LIMIT 1").fetchone()
        conn.close()

        if user:
            # Login with test user session
            with self.client.session_transaction() as sess:
                sess['player_id'] = user['id']
                sess['username'] = user['username']

            # Test all protected pages when logged in
            for url in urls:
                resp = self.client.get(url)
                self.assertEqual(resp.status_code, 200, f"Failed logged-in 200 check for {url} (status: {resp.status_code})")
                print(f"  OK (200) {url}")

            # Test game page
            with app.test_request_context():
                game_url = url_for('game', difficulty='easy')
            resp = self.client.get(game_url)
            self.assertEqual(resp.status_code, 200)
            print(f"  OK (200) {game_url}")

            # Test logout
            with app.test_request_context():
                logout_url = url_for('logout')
            resp = self.client.get(logout_url)
            self.assertEqual(resp.status_code, 302)
            print(f"  OK (302) {logout_url}")

    def test_full_auth_flow(self):
        # 1. Invalid login
        resp = self.client.post('/login', data={'username': 'non_existent_user_xyz', 'password': 'wrongpassword'}, follow_redirects=True)
        self.assertEqual(resp.status_code, 200)
        self.assertIn(b'Invalid username or password', resp.data)
        print("  OK (Auth) Invalid login returns error flash")

        # 2. Register temporary user
        rand_suffix = uuid.uuid4().hex[:6]
        test_user = f"temp_gladiator_{rand_suffix}"
        test_pass = "SecurePass123!"

        resp = self.client.post('/register', data={'username': test_user, 'password': test_pass}, follow_redirects=True)
        self.assertEqual(resp.status_code, 200)
        self.assertIn(b'Registration successful', resp.data)
        print("  OK (Auth) Registration successful")

        # 3. Login with newly created user
        resp = self.client.post('/login', data={'username': test_user, 'password': test_pass}, follow_redirects=False)
        self.assertEqual(resp.status_code, 302)
        self.assertIn('/dashboard', resp.headers.get('Location', ''))
        print("  OK (Auth) Valid login redirects to /dashboard")

        # 4. Follow redirect to /dashboard
        resp = self.client.get('/dashboard')
        self.assertEqual(resp.status_code, 200)
        self.assertIn(test_user.encode(), resp.data)
        print(f"  OK (Auth) Logged-in dashboard renders {test_user}")

        # Clean up temporary test user from db to avoid clutter
        conn = get_connection()
        conn.execute("DELETE FROM players WHERE username = ?", (test_user,))
        conn.commit()
        conn.close()
        print("  OK (Auth) Temp user cleaned up")

if __name__ == '__main__':
    unittest.main()
