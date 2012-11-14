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
		mock_post.return_value.json = True
		assert cookbook.client.register_api(cookbook) == True


