from unittest2 import TestCase

from multiprocessing import Process
import time
import requests

from horoscope import horoscope

def run_horoscope():
    horoscope.run(port=9873)

class TestRun(TestCase):

    def test_blah(self):

        p = Process(target=run_horoscope)
        p.start()
        time.sleep(0.2)
        headers = { 'Content-Type': 'application/json' }
        res = requests.post('http://localhost:9873/actions/predict', data='"leo"', headers=headers)
        self.assertRegexpMatches(res.json, "handsome stranger")
        p.terminate()

