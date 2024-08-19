from typing import Any
from typing_extensions import Final

from ptpython.repl import PythonRepl

from homeassistant.core import HomeAssistant


_HaBanner: Final = r'''
       ▄██▄           _   _
     ▄██████▄        | | | | ___  _ __ ___   ___
   ▄████▀▀████▄      | |_| |/ _ \| '_ ` _ \ / _ \
 ▄█████    █████▄    |  _  | (_) | | | | | |  __/
▄██████▄  ▄██████▄   |_| |_|\___/|_| |_| |_|\___|          _
████████  ██▀  ▀██      / \   ___ ___(_)___| |_ __ _ _ __ | |_
███▀▀███  ██   ▄██     / _ \ / __/ __| / __| __/ _` | '_ \| __|
██    ██  ▀ ▄█████    / ___ \\__ \__ \ \__ \ || (_| | | | | |_
███▄▄ ▀█  ▄███████   /_/   \_\___/___/_|___/\__\__,_|_| |_|\__|
▀█████▄   ███████▀

Welcome to the Home Assistant REPL.
'''


async def run_repl(hass: HomeAssistant) -> None:
    namespace: dict[str, Any] = {
        'hass': hass,
    }

    def get_namespace() -> dict[str, Any]:
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

    namespace['reveal'] = repl._show_result

    repl.app.output.write(_HaBanner)

    # Run REPL interface.
    await repl.run_async()
