import random

from cosmic.api import API
from cosmic.models import Model, ModelSerializer
from teleport import *

horoscope = API("horoscope")

@horoscope.model
class Sign(Model):
    schema = String()

    SIGNS = [
        "aries",
        "taurus",
        "gemini",
        "cancer",
        "leo",
        "virgo",
        "libra",
        "scorpio",
        "sagittarius",
        "capricorn",
        "aquarius",
        "pisces"
    ]

    @classmethod
    def instantiate(cls, datum):
        if datum not in cls.SIGNS:
            raise ValidationError("Unknown zodiac sign", datum)
        return cls(datum)

@horoscope.action(
    accepts=ModelSerializer(Sign),
    returns=String())
def predict(sign):
    ret = "For %s, now is a good time to " % sign.data
    ret += random.choice([
        "build an API.",
        "mow the lawn.",
        "buy Bitcoin.",
        "get a snake tatoo."
    ])
    ret += " It is " + random.choice([
        "probable",
        "not improbable",
        "conceivable",
        "not entirely out of the question"
    ]) + " that you will meet a handsome stranger."
    return ret

if __name__ == "__main__":
    horoscope.run()
