import unittest
from app import app, get_db, init_db, search_database

class VoiceLocatorTestCase(unittest.TestCase):
    def setUp(self):
        """Set up test client and ensure test database state."""
        app.config['TESTING'] = True
        self.client = app.test_client()
        init_db()

    def login(self, ip="127.0.0.1"):
        """Helper to establish an authenticated owner session bound to an IP."""
        import time
        with self.client.session_transaction() as sess:
            sess['logged_in'] = True
            sess['username'] = 'admin'
            sess['bound_ip'] = ip
            sess['last_activity'] = time.time()

    def test_15_ip_binding_and_hijack_prevention(self):
        """Test strict IP address binding and automatic anti-hijack session destruction."""
        # 1. Login with legitimate IP 192.168.1.100
        self.login(ip="192.168.1.100")
        
        # Request from legitimate IP succeeds
        res = self.client.get('/api/check-auth', environ_base={'REMOTE_ADDR': '192.168.1.100'})
        self.assertEqual(res.status_code, 200)
        self.assertTrue(res.get_json()['authenticated'])
        
        # 2. Attacker attempts to use session from a different IP 203.0.113.50
        hijack_res = self.client.get('/api/check-auth', environ_base={'REMOTE_ADDR': '203.0.113.50'})
        self.assertEqual(hijack_res.status_code, 401)
        self.assertEqual(hijack_res.get_json()['reason'], 'ip_mismatch')
        
        # Verify session was destroyed
        subsequent_res = self.client.get('/api/check-auth', environ_base={'REMOTE_ADDR': '192.168.1.100'})
        self.assertEqual(subsequent_res.status_code, 200)
        self.assertFalse(subsequent_res.get_json()['authenticated'])

    def test_16_idle_timeout_expiration(self):
        """Test 10-minute (600s) sliding inactivity idle timeout."""
        import time
        # Establish session with last activity 601 seconds in the past
        with self.client.session_transaction() as sess:
            sess['logged_in'] = True
            sess['bound_ip'] = '127.0.0.1'
            sess['last_activity'] = time.time() - 601  # Inactive > 10 mins

        # Request should be rejected due to idle timeout
        res = self.client.get('/api/check-auth')
        self.assertEqual(res.status_code, 401)
        self.assertEqual(res.get_json()['reason'], 'idle_timeout')

    def test_17_secure_data_import_api(self):
        """Test secure data import endpoint with validation and parameterized transactions."""
        self.login()
        test_import_payload = {
            "items": [
                {
                    "title": "Smart Irrigation Controller",
                    "author": "IoT Tech",
                    "category": "Smart Home",
                    "shelf_location": "Zone C",
                    "available": True,
                    "description": "Automated lawn and garden irrigation controller."
                },
                {
                    "title": "Tankless Water Heater Installation",
                    "author": "Plumbing Pro",
                    "category": "Plumbing",
                    "shelf_location": "All Zones",
                    "available": True,
                    "description": "Energy efficient continuous hot water installation."
                }
            ]
        }
        res = self.client.post('/api/import-data', json=test_import_payload)
        self.assertEqual(res.status_code, 200)
        data = res.get_json()
        self.assertTrue(data['success'])
        self.assertEqual(data['imported_count'], 2)

    def test_18_security_headers(self):
        """Test browser security headers, HSTS, and Content-Security-Policy on HTTP responses."""
        res = self.client.get('/login')
        self.assertEqual(res.status_code, 200)
        self.assertEqual(res.headers.get("X-Frame-Options"), "DENY")
        self.assertEqual(res.headers.get("X-Content-Type-Options"), "nosniff")
        self.assertIn("Strict-Transport-Security", res.headers)

    def test_19_rate_limiting_defense(self):
        """Test rate limiting prevents brute force attacks (blocks after 5 attempts)."""
        from app import LOGIN_ATTEMPTS
        LOGIN_ATTEMPTS.clear()
        
        # 5 failed attempts
        for i in range(5):
            res = self.client.post('/api/login', json={"username": "attacker", "password": "wrong_pwd"})
            self.assertEqual(res.status_code, 401)
            self.assertIn("Invalid credentials", res.get_json()["error"])
            
        # 6th attempt should be blocked with HTTP 429 Too Many Requests
        rate_blocked_res = self.client.post('/api/login', json={"username": "attacker", "password": "wrong_pwd"})
        self.assertEqual(rate_blocked_res.status_code, 429)
        self.assertIn("Too many failed login attempts", rate_blocked_res.get_json()["error"])
        LOGIN_ATTEMPTS.clear()

    def test_20_mfa_2fa_verification(self):
        """Test 2FA multi-factor authentication token verification."""
        # 1. Invalid 2FA code rejected
        invalid_res = self.client.post('/api/verify-2fa', json={"username": "admin", "code": "000000"})
        self.assertEqual(invalid_res.status_code, 401)
        
        # 2. Valid 2FA code accepted and grants session
        valid_res = self.client.post('/api/verify-2fa', json={"username": "admin", "code": "123456"})
        self.assertEqual(valid_res.status_code, 200)
        self.assertTrue(valid_res.get_json()["success"])




    def test_01_index_page(self):
        """Test homepage loads HTML correctly based on authentication."""
        # 1. Unauthenticated request - should load login page
        response = self.client.get('/')
        self.assertEqual(response.status_code, 200)
        self.assertIn(b'Owner Portal Access', response.data)
        
        # 2. Authenticated request - should load dashboard index page
        self.login()
        response = self.client.get('/')
        self.assertEqual(response.status_code, 200)
        self.assertIn(b'VoiceLocator', response.data)

    def test_02_database_search(self):
        """Test SQL database keyword search algorithm."""
        results = search_database("Plumbing")
        self.assertTrue(len(results) > 0)
        self.assertEqual(results[0]['title'], "Emergency Pipe Leak Repair")

    def test_03_security_authentication_barrier(self):
        """Test that unauthorized users & hackers cannot access internal pages/APIs without logging in."""
        # Unauthenticated access to /call-center-dashboard should redirect to login
        res = self.client.get('/call-center-dashboard')
        self.assertEqual(res.status_code, 302)
        
        # Unauthenticated access to /monitor should redirect to login
        res = self.client.get('/monitor')
        self.assertEqual(res.status_code, 302)
        
        # Unauthenticated access to internal REST APIs should return 401 Unauthorized
        res = self.client.get('/api/books')
        self.assertEqual(res.status_code, 401)
        self.assertFalse(res.get_json()['success'])
        
        res = self.client.get('/api/customers')
        self.assertEqual(res.status_code, 401)

    def test_04_api_search_endpoint(self):
        """Test /api/search REST endpoint for Web Speech API and multi-turn prompt."""
        self.login()
        # Question query
        res = self.client.post('/api/search', json={"query": "HVAC", "channel": "Unit Test"})
        self.assertEqual(res.status_code, 200)
        data = res.get_json()
        self.assertTrue(data['success'])
        self.assertIn("Air Conditioner", data['best_match']['title'])
        self.assertIn("questions or doubts", data['spoken_response'])
        self.assertFalse(data['call_ended'])

        # Exit query (User says "No", "No doubts", "Bye")
        exit_res = self.client.post('/api/search', json={"query": "No doubts", "channel": "Unit Test"})
        self.assertEqual(exit_res.status_code, 200)
        exit_data = exit_res.get_json()
        self.assertTrue(exit_data['success'])
        self.assertTrue(exit_data['call_ended'])
        self.assertIn("Goodbye", exit_data['spoken_response'])

    def test_05_api_books_crud(self):
        """Test inventory listing and adding new book."""
        self.login()
        # Get books
        res = self.client.get('/api/books')
        self.assertEqual(res.status_code, 200)
        
        # Add new book
        new_book = {
            "title": "Quantum Mechanics Intro",
            "author": "Richard Feynman",
            "category": "Science",
            "shelf_location": "Section A, Shelf 9",
            "available": True,
            "description": "Fundamental principles of quantum mechanics."
        }
        post_res = self.client.post('/api/books', json=new_book)
        self.assertEqual(post_res.status_code, 200)
        self.assertTrue(post_res.get_json()['success'])

    def test_06_api_customers(self):
        """Test customer contact management."""
        self.login()
        res = self.client.get('/api/customers')
        self.assertEqual(res.status_code, 200)
        data = res.get_json()
        self.assertTrue(len(data['customers']) > 0)

    def test_07_twilio_voice_webhook(self):
        """Test Twilio voice call webhook TwiML XML output."""
        res = self.client.post('/voice')
        self.assertEqual(res.status_code, 200)
        self.assertIn(b'<Response>', response_data := res.data)
        self.assertIn(b'<Gather', response_data)

    def test_08_twilio_multi_turn_speech_handler(self):
        """Test Twilio continuous multi-turn speech handling and exit intent."""
        # 1. User asks inquiry -> AI answers and loops with Gather to continue conversation
        res = self.client.post('/handle-speech', data={"From": "+15551112222", "SpeechResult": "Plumbing"})
        self.assertEqual(res.status_code, 200)
        self.assertIn(b'<Say', res.data)
        self.assertIn(b'Emergency Pipe Leak Repair', res.data)
        self.assertIn(b'<Gather', res.data) # Continues conversation loop!

        # 2. User says "No" / "No doubts" -> AI gracefully says goodbye and hangs up
        exit_res = self.client.post('/handle-speech', data={"From": "+15551112222", "SpeechResult": "No, that's all thank you"})
        self.assertEqual(exit_res.status_code, 200)
        self.assertIn(b'Goodbye', exit_res.data)
        self.assertIn(b'<Hangup', exit_res.data)


    def test_09_twilio_sms_webhook(self):
        """Test Twilio SMS handler webhook output."""
        res = self.client.post('/sms', data={"From": "+15551112222", "Body": "Cleaning"})
        self.assertEqual(res.status_code, 200)
        self.assertIn(b'<Message>', res.data)
        self.assertIn(b'Deep Cleaning', res.data)

    def test_10_outbound_greeting(self):
        """Test outbound greeting TwiML route."""
        res = self.client.get('/outbound-greeting?name=John&topic=HVAC')
        self.assertEqual(res.status_code, 200)
        self.assertIn(b'Hello John', res.data)

    def test_11_trigger_outbound_call(self):
        """Test outbound call campaign trigger API."""
        self.login()
        res = self.client.post('/api/trigger-outbound-call', json={"customer_id": 1})
        self.assertEqual(res.status_code, 200)
        data = res.get_json()
        self.assertTrue(data['success'])

    def test_12_convergence_monitor(self):
        """Test Worker Cells Convergence Monitor route and telemetry API."""
        self.login()
        res = self.client.get('/monitor')
        self.assertEqual(res.status_code, 200)
        self.assertIn(b'Worker cells', res.data)
        
        api_res = self.client.get('/api/convergence-metrics')
        self.assertEqual(api_res.status_code, 200)
        data = api_res.get_json()
        self.assertTrue(data['success'])
        self.assertIn('current_score', data)
        self.assertIn('active_cells', data)

    def test_13_execute_outbound_call(self):
        """Test interactive one-by-one outbound AI call execution endpoint."""
        self.login()
        res = self.client.post('/api/execute-outbound-call', json={"customer_id": 1})
        self.assertEqual(res.status_code, 200)
        data = res.get_json()
        self.assertTrue(data['success'])
        self.assertIn('spoken_script', data)

    def test_14_pytorch_nlp_intent_model(self):
        """Test PyTorch NLP Intent Classification model pipeline."""
        from nlp_intent_model import predict_intent
        res = predict_intent("I have a bathroom pipe leak")
        self.assertIn(res["tag"], ["plumbing", "ac_repair", "unknown"])
        self.assertGreater(res["confidence"], 0.0)

if __name__ == '__main__':
    unittest.main()




