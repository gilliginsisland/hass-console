from typing import Any

from ptpython.repl import PythonRepl

from homeassistant.core import HomeAssistant


async def run_repl(hass: HomeAssistant) -> None:
    namespace: dict[str, Any] = {
        'hass': hass,
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

    namespace['reveal'] = repl._show_result

    # Run REPL interface.
    await repl.run_async()
