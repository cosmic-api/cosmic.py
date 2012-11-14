import json
import requests
from mock import patch

import apio

def test_client():
    with patch.object(requests, 'post') as mock_post:
        mock_post.return_value.json = {
            'url': 'http://api.apio.io',
            'name': 'apio-index',
            'actions': {
                'register_api': {
                    'returns': {'type': 'any'},
                    'accepts': {'type': 'any'}
                },
                'get_spec': {
                    'returns': {'type': 'any'},
                    'accepts': {'type': 'any'}
                }
            }
        }
        cookbook = apio.API('cookbook', 'http://example.com')

        index = apio.API.load('apio-index')
        mock_post.assert_called_with("http://api.apio.io/actions/get_spec", data=json.dumps("apio-index"))

        index.call('register_api', cookbook.serialize())
        mock_post.assert_called_with("http://api.apio.io/actions/register_api", data=json.dumps(cookbook.serialize()))


