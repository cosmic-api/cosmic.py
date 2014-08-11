from __future__ import unicode_literals

class Either(object):
	def __init__(self, exception=None, value=None):
		if exception is not None and value is not None:
			raise RuntimeError("Impossible Either")
		self.exception = exception
		self.value = value

class SpecError(Exception):
    pass

class NotFound(Exception):
	pass

class HTTPError(Exception):
	def __init__(self, code, message, remote=False):
		self.code = code
		self.message = message
		self.remote = remote
		super(HTTPError, self).__init__(code, message, remote)
