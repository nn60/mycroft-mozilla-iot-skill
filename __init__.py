from collections import defaultdict
from typing import List

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
LOG.INFO("BEGUN")

from .mozilla_client import MozillaIoTClient

LOG.INFO("MADE IT PAST LOAD")

_MAX_BRIGHTNESS = 254


class MozillaIoTSkill(CommonIoTSkill, FallbackSkill):
    def __init__(self):
        super().__init__(name="MozillaIoTSkill")
        self._client: MozillaIoTClient = None
        self._entities = dict()
        self._scenes: List[str] = []
        LOG.INFO("init")

    def initialize(self):
        self.settings.set_changed_callback(self.on_websettings_changed)
        self._setup()
        self._entities: List[str] = self._client.entity_names
        self._scenes = []
        LOG.INFO("ABOUT TO REGISTER")
        self.register_entities_and_scenes()

    def _setup(self):
        self._client = MozillaIoTClient(
            token=self.settings.get("token"), host=self.settings.get("host")
        )

    def on_websettings_changed(self):
        self._setup()

    def get_entities(self):
        return self._entities

    def get_scenes(self):
        return []

    @property
    def supported_request_version(self) -> IoTRequestVersion:
        return IoTRequestVersion.V3
