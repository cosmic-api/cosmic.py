def quickstart():

    from cosmic.api import API
    cookbook = API.create('cookbook')

    @cookbook.action(returns={"type": "string"})
    def cabbage(spicy=False):
        if spicy:
            return "kimchi"
        else:
            return "sauerkraut"

    cookbook.run(port=9873)





from multiprocessing import Process
import time

import requests

def quickstart_test():

    p = Process(target=quickstart)
    p.start()
    time.sleep(0.2)
    headers = { 'Content-Type': 'application/json' }
    res = requests.post('http://localhost:9873/actions/cabbage', data='{"spicy": true}', headers=headers)
    assert res.json == "kimchi"
    p.terminate()

