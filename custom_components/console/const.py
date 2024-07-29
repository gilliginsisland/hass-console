from homeassistant.util.hass_dict import HassKey

from .session import ConsoleSession


DEFAULT_HOST = "127.0.0.1"
DEFAULT_PORT = 50101

KEY_DIR = 'keys'

DOMAIN = 'console'

DATA_SESSIONS: HassKey[dict[str, ConsoleSession]] = HassKey(DOMAIN)
