from unittest2 import TestCase

import requests
from mock import patch

from werkzeug.exceptions import Unauthorized, BadRequest, InternalServerError
from flask import Flask

from cosmic.models import Cosmos
from cosmic.actions import *
from cosmic.tools import *
from cosmic.http import *

from teleport import *

class TestURLParams(TestCase):

    def setUp(self):

        self.schema = URLParams([
            optional("foo", String),
            required("bars", Array(Integer))
        ])

    def test_okay(self):
        self.assertEqual(self.schema.from_json('foo="Wha"&bars=1'), {
            "foo": "Wha",
            "bars": [1]
        })
        self.assertEqual(self.schema.from_json('foo="Wha"&bars=1&bars=2&bars=3'), {
            "foo": "Wha",
            "bars": [1, 2, 3]
        })
        self.assertEqual(self.schema.from_json('bars=1&bars=2&bars=3'), {
            "bars": [1, 2, 3]
        })

    def test_wrong_deep_type(self):
        with self.assertRaisesRegexp(ValidationError, "Invalid Integer"):
            self.schema.from_json('foo="Wha"&bars=1&bars=1.2')

    def test_unexpected_array(self):
        with self.assertRaises(ValidationError):
            self.schema.from_json('foo="Wha"&bars=1&foo="Bing"')


class TestActionCallable(TestCase):

    @classmethod
    def setUpClass(cls):
        from cosmic.api import API
        from cosmic.http import RequestsPlugin

        cls.cosmos = Cosmos()
        cls.cosmos.__enter__()

        cls.a = API('a')
        cls.a._request = RequestsPlugin("http://example.com")
        cls.function = Function(Integer, Boolean)
        cls.callable = FlaskViewAction(cls.function, "/actions/even", cls.a)

    @classmethod
    def tearDownClass(cls):
        cls.cosmos.__exit__(None, None, None)

    def test_call_okay(self):
        with patch.object(requests, 'request') as mock_post:
            mock_post.return_value.status_code = 200
            mock_post.return_value.text = "true"
            mock_post.return_value.json = True
            self.assertEqual(self.callable(1), True)

    def test_call_okay_no_response(self):
        with patch.object(requests, 'request') as mock_post:
            mock_post.return_value.status_code = 200
            mock_post.return_value.text = ""
            mock_post.return_value.json = None
            self.assertEqual(self.callable(1), None)

    def test_call_server_sent_wrong_type(self):
        with patch.object(requests, 'request') as mock_post:
            mock_post.return_value.status_code = 200
            mock_post.return_value.text = "1"
            mock_post.return_value.json = 1
            with self.assertRaises(InternalServerError) as cm:
                self.callable(1)
            self.assertRegexpMatches(cm.exception.description, "invalid value")

    def test_call_error_no_message(self):
        with patch.object(requests, 'request') as mock_post:
            mock_post.return_value.status_code = 400
            mock_post.return_value.text = "WTF"
            mock_post.return_value.json = None
            with self.assertRaises(InternalServerError):
                self.callable(1)

    def test_call_error_with_message(self):
        with patch.object(requests, 'request') as mock_post:
            mock_post.return_value.status_code = 500
            mock_post.return_value.text = '{"error": "your mama"}'
            mock_post.return_value.json = {"error": "your mama"}
            with self.assertRaises(InternalServerError) as cm:
                self.callable(1)
            self.assertRegexpMatches(cm.exception.description, "your mama")
