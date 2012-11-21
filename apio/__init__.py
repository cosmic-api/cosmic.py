import imp
import sys
from api import API

class DynamicLoader(object):
    def find_module(self, name, path=None):
        names = name.split('.')
        if names[0] != 'apio':
            return None
        # If we are trying to import apio.x where x is not a real module
        if len(names) == 2 and names[1] not in ['api', 'exceptions']:
            return self
        return None
    def load_module(self, fullname):
        names = fullname.split('.')
        api = API.load(names[1])
        mod = sys.modules.setdefault(fullname, api)
        mod.__file__ = "<%s>" % names[1]
        mod.__loader__ = self
        mod.__package__ = 'apio'
        return mod

sys.meta_path.append(DynamicLoader())

del DynamicLoader
