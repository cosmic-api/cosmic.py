
def quickstart():

    from apio import API
    cookbook = API('cookbook')

    @cookbook.action()
    def cabbage(spicy=False):
        if spicy:
            return "Kimchi"
        else:
            return "Sauerkraut"

    cookbook.run(port=9873)





from multiprocessing import Process
import urllib2
import time

def quickstart_test():

    p = Process(target=quickstart)
    p.start()
    time.sleep(0.2)
    assert urllib2.urlopen('http://localhost:9873/actions/cabbage').read().strip() == "Sauerkraut"
    p.terminate()

