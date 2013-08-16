import random

from cosmic.api import API
from cosmic.models import Model, Cosmos
from teleport import *

def make_zodiac():

    zodiac = API("zodiac")

    @zodiac.model
    class Sign(Model):
        properties = [
            required("name", String)
        ]

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
        def validate(cls, datum):
            if datum["name"] not in cls.SIGNS:
                raise ValidationError("Unknown zodiac sign", datum["name"])

    @zodiac.action(accepts=Sign, returns=String)
    def predict(sign):
        ret = "For %s, now is a good time to " % sign.name
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

    return zodiac


if __name__ == "__main__":
    with Cosmos():
        make_zodiac().run()
