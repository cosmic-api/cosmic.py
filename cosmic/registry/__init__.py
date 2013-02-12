from __future__ import absolute_import

import sys
import imp
from ..api import API

class DynamicLoader(object):

    def find_module(self, name, path=None):
        names = name.split('.')
        if not name.startswith('cosmic.registry'):
            return None
        # If we are trying to import cosmic.registry.x
        if len(names) >= 3:
            return self
        return None

    def get_package(self, api_name):
        package_name = "cosmic.registry.%s" % api_name
        # Fetch the base package
        if package_name in sys.modules.keys():
            package = sys.modules[package_name]
        else:
            api = API.load(api_name)
            package = sys.modules.setdefault(package_name, api)
            package.__file__ = "<%s>" % package_name
            package.__loader__ = self
            package.__path__ = []
        return package

    def load_module(self, fullname):
        names = fullname.split('.')
        api_name = names[2]
        package = self.get_package(api_name)
        # Do we need to go deeper?
        if len(names) == 3:
            return package
        # Yes we do!
        if names[3] != 'actions':
            raise ImportError()
        # We just want actions
        package.actions.__file__ = "<%s>" % fullname
        package.actions.__loader__ = self
        sys.modules.setdefault(fullname, package.actions)
        return package.actions

sys.meta_path.append(DynamicLoader())

del DynamicLoader