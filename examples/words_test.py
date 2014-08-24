from unittest2 import TestCase
from multiprocessing import Process

from werkzeug.wrappers import Response
from werkzeug.test import Client as TestClient

from cosmic.http import Server
from cosmic.globals import cosmos
from cosmic.client import APIClient, ClientLoggingMixin
from cosmic.testing import served_api, Wildcard
from cosmic.types import *
from words import words


class TestWords(TestCase):

    def setUp(self):
        self._old_cosmos = cosmos.data
        cosmos.data = {}

        app = Server(words).wsgi_app
        self.client = TestClient(app, response_wrapper=Response)

    def tearDown(self):
        cosmos.data = self._old_cosmos

    def test_pluralize_okay(self):
        resp = self.client.post('/actions/pluralize',
                                content_type='application/json', data='"pony"')
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.data, '"ponies"')


class TestWordsSystem(TestCase):

    def test_single_thread(self):
        with served_api(words, 5003):

            class WordsClient(APIClient):
                base_url = 'http://127.0.0.1:5003'

            c = WordsClient()
            p = Process(target=c.actions.lock_thread, args=(1,))
            p.start()
            self.assertEqual(c.actions.count_letters((None, {"letters": "rabbit"})), 6)
            p.terminate()

    def test_multi_thread(self):
        with served_api(words, 5002, threaded=True):

            class WordsClient(APIClient):
                base_url = 'http://127.0.0.1:5002'

            c = WordsClient()
            p = Process(target=c.actions.lock_thread, args=(1,))
            p.start()
            self.assertEqual(c.actions.count_letters((None, {"letters": "rabbit"})), 6)
            p.terminate()

    def test_system(self):
        with served_api(words, 5000):

            class WordsClient(APIClient):
                base_url = 'http://127.0.0.1:5000'

            c = WordsClient()
            self.assertEqual(APISpec.to_json(c.spec), APISpec.to_json(words.spec))

    def test_logging(self):
        with served_api(words, 5001):

            class WordsClient(ClientLoggingMixin, APIClient):
                base_url = 'http://127.0.0.1:5001'

            c = WordsClient()
            c.actions.pluralize('pencil')
            self.assertEqual(c.log[-1][0], {
                'method': 'POST',
                'data': '"pencil"',
                'headers': [('Content-Type', 'application/json')],
                'url': u'/actions/pluralize'
            })
            self.assertEqual(c.log[-1][1], {
                'status_code': 200,
                'data': u'"pencils"',
                'headers': [
                    ('Content-Length', '9'),
                    ('Content-Type', 'application/json'),
                    ('Date', Wildcard),
                    ('Server', Wildcard),
                ]
            })





