import traceback
from typing import Any, Final
from pathlib import Path
import logging

from prompt_toolkit.application import create_app_session
from prompt_toolkit.input import create_pipe_input
import voluptuous as vol

from homeassistant.core import HomeAssistant, callback
from homeassistant.components import panel_custom, websocket_api
from homeassistant.components.http import StaticPathConfig

from .const import DATA_SESSIONS, DOMAIN
from .repl import run_repl
from .session import ConsoleOutput, ConsoleSession

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
        webcomponent_name="terminal-element",
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

    logger = _LOGGER.getChild(session_id)

    def stdout(data: str):
        connection.send_event(msg_id, data)

    async def interact():
        logger.info('Initializing session')

        _output = ConsoleOutput(stdout)
        with create_pipe_input() as _input:
            with create_app_session(input=_input, output=_output) as _app_session:
                @callback
                def unload() -> None:
                    logger.info('Connection lost')
                    _input.close()

                connection.subscriptions[msg_id] = unload

                hass.data[DATA_SESSIONS][session_id] = ConsoleSession(
                    input=_input, output=_output, app_session=_app_session
                )
                try:
                    await run_repl(hass)
                except BaseException:
                    traceback.print_exc()
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

    logger = _LOGGER.getChild(session_id)

    if (session := hass.data[DATA_SESSIONS].get(session_id)):
        logger.debug(f'Receved input: {data}')
        session.data_received(data)
    else:
        logger.debug(f'No session, ignoring msg: {msg}')


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

    logger = _LOGGER.getChild(session_id)

    if (session := hass.data[DATA_SESSIONS].get(session_id)):
        logger.debug(f'Terminal resize: ({cols}, {rows})')
        session.terminal_size_changed(cols, rows)
    else:
        logger.debug(f'No session, ignoring msg: {msg}')
