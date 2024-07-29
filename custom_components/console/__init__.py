from enum import StrEnum
import logging

import voluptuous as vol
import asyncssh
from prompt_toolkit.contrib.ssh import (
    PromptToolkitSSHServer,
)

from homeassistant.core import HomeAssistant, Event
from homeassistant.const import (
    CONF_HOST,
    CONF_PORT,
    EVENT_HOMEASSISTANT_STOP,
)
import homeassistant.helpers.config_validation as cv
from homeassistant.helpers.typing import ConfigType

from .const import (
    DATA_SESSIONS,
    DEFAULT_HOST,
    DEFAULT_PORT,
    DOMAIN,
    KEY_DIR,
)
from .repl import run_repl
from .websocket import register_panel


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

    hass.data[DATA_SESSIONS] = {}

    await register_panel(hass)

    server = await _async_start_ssh_server(
        hass,
        host := config[DOMAIN].get(CONF_HOST),
        port := config[DOMAIN].get(CONF_PORT),
    )
    _LOGGER.info(f'Started console on {host}:{port}')

    async def _on_hass_stop(_: Event) -> None:
        """Shutdown console on HomeAssistant stop."""
        server.close()
        await server.wait_closed()

    hass.bus.async_listen_once(EVENT_HOMEASSISTANT_STOP, _on_hass_stop)

    return True


async def _async_start_ssh_server(hass: HomeAssistant, host: str, port: int) -> asyncssh.SSHAcceptor:
    return await asyncssh.listen(
        host=host, port=port,
        encoding="utf-8",
        server_host_keys=[
            hass.config.path(KEY_DIR, kt.filename) for kt in SSHKeyType
        ],
        server_factory=lambda: PromptToolkitSSHServer(lambda con: run_repl(hass)),
    )
