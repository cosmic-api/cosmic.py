import requests

from mock import patch
from unittest2 import TestCase

from cosmic import api
from tests.api_test import registry_spec, cookbook_spec

class TestAPIImport(TestCase):

    def setUp(self):
        api.cosmic_registry = api.API.normalize(registry_spec)

    def tearDown(self):
        api.clear_module_cache()

    def test_import_actions(self):
        with patch.object(requests, 'post') as mock_post:
            mock_post.return_value.status_code = 200
            mock_post.return_value.json = cookbook_spec
            from cosmic.registry.cookbook import actions
            self.assertEqual(actions.cabbage.serialize(), cookbook_spec['actions'][0])

    def test_import_specific_action(self):
        with patch.object(requests, 'post') as mock_post:
            mock_post.return_value.status_code = 200
            mock_post.return_value.json = cookbook_spec
            from cosmic.registry.cookbook.actions import cabbage
            self.assertEqual(cabbage.serialize(), cookbook_spec['actions'][0])

    def test_import_too_specific(self):
        with patch.object(requests, 'post') as mock_post:
            mock_post.return_value.status_code = 200
            mock_post.return_value.json = cookbook_spec
            with self.assertRaises(ImportError):
                from cosmic.registry.cookbook.actions.cabbage import spec

    def test_import_all_actions(self):
        with patch.object(requests, 'post') as mock_post:
            mock_post.return_value.status_code = 200
            mock_post.return_value.json = cookbook_spec
            from cosmic.registry.cookbook.actions import *
            self.assertEqual(cabbage.serialize(), cookbook_spec['actions'][0])
            self.assertEqual(noop.serialize(), cookbook_spec['actions'][1])

    def test_import_non_actions(self):
        with patch.object(requests, 'post') as mock_post:
            mock_post.return_value.status_code = 200
            mock_post.return_value.json = cookbook_spec
            with self.assertRaises(ImportError):
                from cosmic.registry.cookbook import aktions
