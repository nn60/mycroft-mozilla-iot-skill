from collections import defaultdict
from typing import List, Dict, Union, Optional, Any
import requests
import json

from mycroft.skills.common_iot_skill import (
    CommonIoTSkill,
    IoTRequest,
    IoTRequestVersion,
    Thing,
    Action,
    Attribute,
    State,
)
from mycroft.skills.core import FallbackSkill
from mycroft.util.log import getLogger

LOG = getLogger()

ThingType = Dict[Any, Any]  # replace if there's a good type for a Thing response


# map to help to convert some actions to "set" requests on properties
ACTION_TO_PROPERTY = {Action.ON: "on", Action.OFF: "off"}

# actions that are "set" type actions
SET_ACTIONS = (Action.SET, Action.ON, Action.OFF)

# synonyms
SYNONYMS = [("light", "lamp", "lights")]


def normalize(name: str) -> str:
    return name.lower().strip()


def get_alternate_names(name: str) -> List[str]:
    """
    replace words with synonyms to create alternate names. This should allow
    for flexibility in naming of Things
    """
    sp = name.split(" ")
    out = []
    for synset in SYNONYMS:
        for word in synset:
            if word in sp:
                for replacement in [w for w in synset if w != word]:
                    other = sp.copy()
                    other[other.index(word)] = replacement
                    out.append(normalize(" ".join(other)))
    return out


class MozillaIoTClient:
    def __init__(self, host: str, token: str):
        """
        Client for interacting with the Mozilla IoT API
        """
        LOG.info("init'd client")
        if host[-1] == "/":
            host = host[:-1]
        self.host = host
        self.headers = {
            "Authorization": "Bearer {}".format(token),
            "Content-Type": "application/json",
        }
        LOG.info("client get_things()")
        self.things = self.get_things()
        self.entity_names: Dict[str, ThingType] = {}
        for thing in self.things:
            name = normalize(thing["title"])
            self.entity_names[name] = thing
            # add synonyms if relevant
            alternates = get_alternate_names(name)
            for other_name in alternates:
                self.entity_names[other_name] = thing
        LOG.info("finished client init")

    def request(self, method: str, endpoint: str, data: dict = None):

        url = self.host + endpoint
        LOG.info(url)
        response = requests.request(method, url, json=data, headers=self.headers)
        try:
            response.raise_for_status()
        except requests.exceptions.HTTPError as e:
            print("caught: ", e)

        return response

    def get_things(self):
        if self.host:
            resp = self.request("GET", "/things/")
            print(resp)
            return resp.json()
        return []

    def resolve_entity(self, entity_value: str) -> ThingType:
        """
        Given an input entity value from the NLU, return the a matched
        name if available. For instance, if the resolved entity is
        "kitchen lights" but the closest Thing is "kitchen light" return
        the kitchen light Thing
        """
        thing = self.entity_names.get(normalize(entity_value), None)
        LOG.info(json.dumps(thing, indent=2))
        return thing

    def get_set_value_request(
        self,
        thing: ThingType,
        attribute: Optional[str],
        value: Union[str, int, float, None],
    ):
        """
        Attempt to set a thing's property value
        """

        for prop, prop_dict in thing.get("properties", {}).items():
            LOG.info(f"considering {prop}, comparing to {attribute}")
            if attribute in (normalize(prop), normalize(prop_dict["title"])):
                LOG.info(f"matched {prop}")
                url = prop_dict.get("links", [{}])[0].get("href", "")
                data = {prop: value}
                cb = {"url": url, "data": data, "method": "PUT"}
                return True, cb
        return False, {}


class MozillaIoTSkill(CommonIoTSkill, FallbackSkill):
    def __init__(self):
        LOG.info("init'd skill")
        super().__init__(name="MozillaIoTSkill")

        self._client: MozillaIoTClient = None
        self._entities: List[ThingType] = []
        self._scenes: List[str] = []

    def initialize(self):
        LOG.info("beginning initialize")

        self.settings_change_callback = self.on_websettings_changed
        self._setup()

    def _setup(self):
        self._client = MozillaIoTClient(
            token=self.settings.get("token"), host=self.settings.get("host")
        )
        print("client initialized")
        self._entities: List[str] = self._client.entity_names.keys()
        self._scenes = []
        LOG.info(f"Entities Registered: {self._entities}")
        self.register_entities_and_scenes()

    def on_websettings_changed(self):
        self._setup()

    def get_entities(self):
        return self._entities

    def get_scenes(self):
        return []

    @property
    def supported_request_version(self) -> IoTRequestVersion:
        return IoTRequestVersion.V3

    def resolve_nicknames(self, name: str) -> str:
        """
        Allow for creating a nickname mapping

        TODO: implement
        """
        return name

    def can_handle(self, request):
        LOG.info("Mozilla IoT was consulted")
        LOG.info(request)
        can_handle = False
        callback = {}
        entity_name = self.resolve_nicknames(request.entity)
        thing = self._client.resolve_entity(entity_name)
        if thing is None:
            LOG.info(f"mozilla-iot: no such thing as {request.entity}")
            return False, {}
        if request.action in SET_ACTIONS:
            # 'on/off' action and the like become 'set' of a property
            attribute = ACTION_TO_PROPERTY.get(request.action, request.attribute)
            can_handle, callback = self._client.get_set_value_request(
                thing, attribute, request.value
            )

        return can_handle, callback

    def run_request(self, request, cb):
        LOG.info(str(request), request)
        LOG.info(cb)
        self._client.request(cb["method"], cb["url"], cb["data"])


def create_skill():
    return MozillaIoTSkill()
