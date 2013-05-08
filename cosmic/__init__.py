from werkzeug.local import Local

context = Local()

from api import APISerializer, APIModelSerializer
from actions import ActionSerializer

from teleport import types

types["cosmic.API"] = APISerializer
types["cosmic.APIModel"] = APIModelSerializer
types["cosmic.Action"] = ActionSerializer
