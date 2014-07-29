from __future__ import unicode_literals

class SpecError(Exception):
    pass

class HTTPError(Exception):
	def __init__(self, code, message, remote=False):
		self.code = code
		self.message = message
		self.remote = remote
		super(HTTPError, self).__init__(code, message, remote)
