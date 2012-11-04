class Type(object):
	schema = {}
	def __init__(self, *args, **kwargs):
		self.schema = kwargs
	def serialize(self):
		return self.schema

class Any(Type):
	def __init__(self, *args, **kwargs):
		super(Any, self).__init__(*args, **kwargs)
		self.schema['type'] = 'any'

class String(Type):
	def __init__(self, *args, **kwargs):
		super(String, self).__init__(*args, **kwargs)
		self.schema['type'] = 'string'

class Boolean(Type):
	def __init__(self, *args, **kwargs):
		super(Boolean, self).__init__(*args, **kwargs)
		self.schema['type'] = 'boolean'

class Array(Type):
	def __init__(self, item, *args, **kwargs):
		super(Array, self).__init__(*args, **kwargs)
		self.schema['type'] = 'array'
		self.schema['items'] = item.serialize()
