class Type(object):
	schema = {}
	def __init__(self, *args, **kwargs):
		self.schema = kwargs
	def serialize(self):
		return self.schema

class String(Type):
	def __init__(self, *args, **kwargs):
		super(String, self).__init__(*args, **kwargs)
		self.schema['type'] = 'string'

class Boolean(Type):
	def __init__(self, *args, **kwargs):
		super(Boolean, self).__init__(*args, **kwargs)
		self.schema['type'] = 'boolean'
