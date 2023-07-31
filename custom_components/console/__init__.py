from enum import StrEnum
import logging
import functools as ft

import voluptuous as vol

import asyncssh
from prompt_toolkit.contrib.ssh import (
    PromptToolkitSSHServer,
    PromptToolkitSSHSession,
)
from ptpython.repl import PythonRepl

from homeassistant.core import Event, HomeAssistant
from homeassistant.const import (
    CONF_HOST,
    CONF_PORT,
    EVENT_HOMEASSISTANT_STOP,
)
import homeassistant.helpers.config_validation as cv
from homeassistant.helpers.typing import ConfigType

DEFAULT_HOST = "127.0.0.1"
DEFAULT_PORT = 50101

KEY_DIR = 'keys'

DOMAIN = 'console'

CONFIG_SCHEMA = vol.Schema(
    {
        DOMAIN: vol.Schema({
            vol.Optional(CONF_HOST, default=DEFAULT_HOST): cv.string,
            vol.Optional(CONF_PORT, default=DEFAULT_PORT): cv.port,
        }),
    },
    extra=vol.ALLOW_EXTRA,
)

_LOGGER = logging.getLogger(__name__)


class SSHKeyType(StrEnum):
    DSA = 'dsa'
    ECDSA = 'ecdsa'
    ED25519 = 'ed25519'
    RSA = 'rsa'

    @property
    def filename(self):
        return f'ssh_host_{self.value}_key'


async def async_setup(hass: HomeAssistant, config: ConfigType) -> bool:
    if DOMAIN not in config:
        return True

    host: str = config[DOMAIN].get(CONF_HOST)
    port: int = config[DOMAIN].get(CONF_PORT)

    server = await asyncssh.create_server(
        lambda: PromptToolkitSSHServer(ft.partial(interact, hass)),
        host=host, port=port,
        encoding="utf-8",
        server_host_keys=[
            hass.config.path(KEY_DIR, kt.filename) for kt in SSHKeyType
        ],
    )
    _LOGGER.info(f'Started console on {host}:{port}')

    async def _on_hass_stop(_: Event) -> None:
        """Shutdown console on HomeAssistant stop."""
        server.close()
        await server.wait_closed()

    hass.bus.async_listen_once(EVENT_HOMEASSISTANT_STOP, _on_hass_stop)

    return True


async def interact(
    hass: HomeAssistant,
    session: PromptToolkitSSHSession,
) -> None:
    def print_(*data, sep=" ", end="\n", file=None) -> None:
        """
        Alternative 'print' function that prints back into the SSH channel.
        """
        data = sep.join(map(str, data))
        session.stdout.write(data + end)

    namespace = {
        'hass': hass,
        'session': session,
        'print': print_,
    }

    def get_namespace():
        return namespace

    repl = PythonRepl(
        get_globals=get_namespace,
        get_locals=get_namespace,
    )

    # Disable open-in-editor and system prompt. Because it would run and
    # display these commands on the server side, rather than in the SSH
    # client.
    repl.enable_open_in_editor = False
    repl.enable_system_bindings = False

    namespace['reveal'] = repl.show_result

    # Run REPL interface.
    await repl.run_async()
