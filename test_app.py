import unittest
from app import app, get_db, init_db, search_database

class VoiceLocatorTestCase(unittest.TestCase):
    def setUp(self):
        """Set up test client and ensure test database state."""
        app.config['TESTING'] = True
        self.client = app.test_client()
        init_db()

    def test_01_index_page(self):
        """Test homepage loads HTML correctly."""
        response = self.client.get('/')
        self.assertEqual(response.status_code, 200)
        self.assertIn(b'VoiceLocator', response.data)

    def test_02_database_search(self):
        """Test SQL database keyword search algorithm."""
        results = search_database("Physics")
        self.assertTrue(len(results) > 0)
        self.assertEqual(results[0]['title'], "Physics for Scientists and Engineers")

    def test_03_api_search_endpoint(self):
        """Test /api/search REST endpoint for Web Speech API."""
        res = self.client.post('/api/search', json={"query": "Calculus", "channel": "Unit Test"})
        self.assertEqual(res.status_code, 200)
        data = res.get_json()
        self.assertTrue(data['success'])
        self.assertIn("Calculus", data['best_match']['title'])

    def test_04_api_books_crud(self):
        """Test inventory listing and adding new book."""
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

    def test_05_api_customers(self):
        """Test customer contact management."""
        res = self.client.get('/api/customers')
        self.assertEqual(res.status_code, 200)
        data = res.get_json()
        self.assertTrue(len(data['customers']) > 0)

    def test_06_twilio_voice_webhook(self):
        """Test Twilio voice call webhook TwiML XML output."""
        res = self.client.post('/voice')
        self.assertEqual(res.status_code, 200)
        self.assertIn(b'<Response>', response_data := res.data)
        self.assertIn(b'<Gather', response_data)

    def test_07_twilio_speech_handler(self):
        """Test Twilio speech transcription handler TwiML output."""
        res = self.client.post('/handle-speech', data={"From": "+15551112222", "SpeechResult": "Algorithms"})
        self.assertEqual(res.status_code, 200)
        self.assertIn(b'<Say', res.data)
        self.assertIn(b'Introduction to Algorithms', res.data)

    def test_08_twilio_sms_webhook(self):
        """Test Twilio SMS handler webhook output."""
        res = self.client.post('/sms', data={"From": "+15551112222", "Body": "History"})
        self.assertEqual(res.status_code, 200)
        self.assertIn(b'<Message>', res.data)

    def test_09_outbound_greeting(self):
        """Test outbound greeting TwiML route."""
        res = self.client.get('/outbound-greeting?name=John&topic=Physics')
        self.assertEqual(res.status_code, 200)
        self.assertIn(b'Hello John', res.data)

    def test_10_trigger_outbound_call(self):
        """Test outbound call campaign trigger API."""
        res = self.client.post('/api/trigger-outbound-call', json={"customer_id": 1})
        self.assertEqual(res.status_code, 200)
        data = res.get_json()
        self.assertTrue(data['success'])

    def test_11_convergence_monitor(self):
        """Test Worker Cells Convergence Monitor route and telemetry API."""
        res = self.client.get('/monitor')
        self.assertEqual(res.status_code, 200)
        self.assertIn(b'Worker cells', res.data)
        
        api_res = self.client.get('/api/convergence-metrics')
        self.assertEqual(api_res.status_code, 200)
        data = api_res.get_json()
        self.assertTrue(data['success'])
        self.assertIn('current_score', data)
        self.assertIn('active_cells', data)

if __name__ == '__main__':
    unittest.main()

