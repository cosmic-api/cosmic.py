from time import sleep
from unittest2 import TestCase
from threading import Thread

from cosmic.globals import *
from cosmic.globals import storage

class TestSwappableDict(TestCase):

    def test_dict_methods(self):
        s = SwappableDict()
        s['a'] = 1
        self.assertEqual(s['a'], 1)
        self.assertEqual(len(s), 1)
        del s['a']
        self.assertEqual(len(s), 0)

    def test_swap(self):
        s = SwappableDict()
        s.update({'a': 1})
        self.assertEqual(dict(s), {'a': 1})
        with s.swap({'b': 2}):
            self.assertEqual(dict(s), {'b': 2})
        self.assertEqual(dict(s), {'a': 1})

class TestThreadLocalDict(TestCase):

    def test_unbound(self):
        s = ThreadLocalDict()
        with self.assertRaises(Exception):
            s['a'] = 1

    def test_threads(self):

        s = ThreadLocalDict()

        def run():
            sleep(0.2)
            with thread_local():
                self.assertEqual(dict(s), {})
                s['a'] = 1
                self.assertEqual(dict(s), {'a': 1})
                del s['a']
                self.assertEqual(dict(s), {})
                sleep(0.2)

        threads = []
        for i in range(10):
            thread = Thread(target=run)
            thread.start()
            threads.append(thread)

        for thread in threads:
            thread.join()

        self.assertEqual(storage, {})
