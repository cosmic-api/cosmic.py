from unittest2 import TestCase
from werkzeug.wrappers import Response
from werkzeug.test import Client as TestClient

from cosmic.http import Server
from cosmic.models import Cosmos
from words import words


class TestWords(TestCase):

    def setUp(self):

        self.cosmos = Cosmos()
        self.cosmos.__enter__()

        app = Server(words).wsgi_app
        self.client = TestClient(app, response_wrapper=Response)

    def test_pluralize_okay(self):
        resp = self.client.post('/actions/pluralize',
                                content_type='application/json', data='"pony"')
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.data, '"ponies"')

