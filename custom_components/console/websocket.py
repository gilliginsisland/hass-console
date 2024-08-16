import traceback
from typing import Any, Final
from pathlib import Path
import logging

import voluptuous as vol

from homeassistant.core import HomeAssistant, callback
from homeassistant.components import panel_custom, websocket_api
from homeassistant.components.http import StaticPathConfig

from .const import DATA_SESSIONS, DOMAIN
from .repl import run_repl
from .session import create_console_session

URL_BASE: Final = "/console_static"
PATH_BASE: Final = str(Path(__file__).parent / 'frontend')

_LOGGER = logging.getLogger(__name__)


async def register_panel(hass: HomeAssistant) -> None:
    websocket_api.async_register_command(hass, ws_create_session)
    websocket_api.async_register_command(hass, ws_session_input)
    websocket_api.async_register_command(hass, ws_session_resize)

    await hass.http.async_register_static_paths(
        [
            StaticPathConfig(
                url_path=f'{URL_BASE}',
                path=f'{PATH_BASE}',
                cache_headers=True,
            )
        ]
    )
    await panel_custom.async_register_panel(
        hass=hass,
        frontend_url_path=DOMAIN,
        webcomponent_name="terminal-panel",
        sidebar_title=DOMAIN.title(),
        sidebar_icon="mdi:console",
        module_url=f'{URL_BASE}/entrypoint.mjs',
        embed_iframe=False,
        require_admin=True,
    )


@websocket_api.require_admin
@websocket_api.websocket_command(
    {
        vol.Required("type"): "console/create_session",
        vol.Required("session_id"): str,
    }
)
@callback
def ws_create_session(
    hass: HomeAssistant,
    connection: websocket_api.ActiveConnection,
    msg: dict[str, Any],
) -> None:
    """Initialize a repl session."""

    msg_id: int = msg["id"]
    session_id: str = msg["session_id"]

    def writer(data: str):
        connection.send_event(msg_id, data)

    async def interact():
        with create_console_session(writer) as session:
            connection.subscriptions[msg_id] = session.close

            hass.data[DATA_SESSIONS][session_id] = session
            try:
                await run_repl(hass)
            except BaseException:
                writer(traceback.format_exc())
                _LOGGER.exception('Error running repl')
            finally:
                hass.data[DATA_SESSIONS].pop(session_id)

    hass.loop.create_task(interact())

    connection.send_result(msg_id)


@websocket_api.require_admin
@websocket_api.websocket_command(
    {
        vol.Required("type"): "console/input",
        vol.Required("session_id"): str,
        vol.Required("data"): str,
    }
)
@callback
def ws_session_input(
    hass: HomeAssistant,
    connection: websocket_api.ActiveConnection,
    msg: dict[str, Any],
) -> None:
    """Initialize a repl session."""

    session_id: str = msg["session_id"]
    data = msg["data"]

    if not (session := hass.data[DATA_SESSIONS].get(session_id)):
        _LOGGER.debug(f'No session, ignoring msg: {msg}')
        return

    session.data_received(data)


@websocket_api.require_admin
@websocket_api.websocket_command(
    {
        vol.Required("type"): "console/resize",
        vol.Required("session_id"): str,
        vol.Required("cols"): int,
        vol.Required("rows"): int,
    }
)
@callback
def ws_session_resize(
    hass: HomeAssistant,
    connection: websocket_api.ActiveConnection,
    msg: dict[str, Any],
) -> None:
    """Initialize a repl session."""

    session_id: str = msg["session_id"]
    cols: int = msg['cols']
    rows: int = msg['rows']

    if not (session := hass.data[DATA_SESSIONS].get(session_id)):
        _LOGGER.debug(f'No session, ignoring msg: {msg}')
        return

    session.terminal_size_changed(cols, rows)
