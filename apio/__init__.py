import imp
import sys
from api import API

class DynamicLoader(object):

    def find_module(self, name, path=None):
        names = name.split('.')
        if names[0] != 'apio':
            return None
        # If we are trying to import apio.x where x is not a real module
        if len(names) >= 2 and names[1] not in ['api', 'exceptions']:
            return self
        return None

    def get_package(self, api_name):
        package_name = "apio.%s" % api_name
        # Fetch the base package
        if package_name in sys.modules.keys():
            package = sys.modules[package_name]
        else:
            api = API.load(api_name)
            package = sys.modules.setdefault(package_name, api)
            package.__file__ = "<apio.%s>" % api_name
            package.__loader__ = self
            package.__path__ = []
            package.__package__ = package_name
        return package

    def load_module(self, fullname):
        print "LOADING %s" % fullname
        names = fullname.split('.')
        api_name = names[1]
        package = self.get_package(api_name)
        # Do we need to go deeper?
        specifics = names[2:]
        if not specifics: return package
        # Yes we do!
        if specifics[0] != 'actions':
            raise ImportError()
        # We just want actions
        if len(specifics) == 1:
            return package.actions
        elif len(specifics) == 2:
            return package.actions.__getattr__(specifics[1])
        else:
            raise ImportError()

sys.meta_path.append(DynamicLoader())

del DynamicLoader
