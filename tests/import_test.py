import requests

from mock import patch
from unittest2 import TestCase

from apio import api
from tests.api_test import index_spec, cookbook_spec

class TestAPIImport(TestCase):

    def setUp(self):
        api.apio_index = api.RemoteAPI(index_spec)

    def tearDown(self):
        api.clear_module_cache()

    def test_import_actions(self):
        with patch.object(requests, 'post') as mock_post:
            mock_post.return_value.status_code = 200
            mock_post.return_value.json = cookbook_spec
            from apio.index.cookbook import actions
            self.assertEqual(actions.specs, cookbook_spec['actions'])
    
    def test_import_specific_action(self):
        with patch.object(requests, 'post') as mock_post:
            mock_post.return_value.status_code = 200
            mock_post.return_value.json = cookbook_spec
            from apio.index.cookbook.actions import cabbage
            self.assertEqual(cabbage.spec, cookbook_spec['actions'][0])

    def test_import_too_specific(self):
        with patch.object(requests, 'post') as mock_post:
            mock_post.return_value.status_code = 200
            mock_post.return_value.json = cookbook_spec
            with self.assertRaises(ImportError):
                from apio.index.cookbook.actions.cabbage import spec

    def test_import_all_actions(self):
        with patch.object(requests, 'post') as mock_post:
            mock_post.return_value.status_code = 200
            mock_post.return_value.json = cookbook_spec
            from apio.index.cookbook.actions import *
            self.assertEqual(cabbage.spec, cookbook_spec['actions'][0])
            self.assertEqual(noop.spec, cookbook_spec['actions'][1])

    def test_import_non_actions(self):
        with patch.object(requests, 'post') as mock_post:
            mock_post.return_value.status_code = 200
            mock_post.return_value.json = cookbook_spec
            with self.assertRaises(ImportError):
                from apio.index.cookbook import aktions