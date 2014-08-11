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
	def __init__(self, code, message):
		self.code = code
		self.message = message
		super(HTTPError, self).__init__(code, message)

class RemoteHTTPError(HTTPError):
	pass