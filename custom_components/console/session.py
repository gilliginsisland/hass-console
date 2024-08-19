import contextlib
from typing import Any, Callable, Generator, TextIO, cast

from prompt_toolkit.application import AppSession, create_app_session
from prompt_toolkit.data_structures import Size
from prompt_toolkit.input import PipeInput, create_pipe_input
from prompt_toolkit.output.vt100 import Vt100_Output


class ConsoleOutput(Vt100_Output):
    def __init__(
        self,
        writer: Callable[[str], Any],
    ) -> None:
        self.writer = writer
        self.size: Size = Size(rows=20, columns=79)

        class Stdout:
            encoding = "utf-8"

            def write(stdout, data: str) -> None:
                self.writer(data.replace("\n", "\r\n"))

            def isatty(stdout) -> bool:
                return True

            def flush(stdout) -> None:
                pass

        super().__init__(cast(TextIO, Stdout()), self.get_size)

    def get_size(self) -> Size:
        return self.size


class ConsoleSession():
    def __init__(
        self,
        input: PipeInput,
        output: ConsoleOutput,
        app_session: AppSession,
    ) -> None:
        self._input = input
        self._output = output
        self._app_session = app_session

    def data_received(self, data: str) -> None:
        self._input.send_text(data)

    def terminal_size_changed(self, width: int, height: int) -> None:
        self._output.size = Size(height, width)

        # Send resize event to the current application.
        if (app := self._app_session.app):
            app._on_resize()

    def close(self) -> None:
        self._input.close()


@contextlib.contextmanager
def create_console_session(
    writer: Callable[[str], Any]
) -> Generator[ConsoleSession,None, None]:
    _output = ConsoleOutput(writer)
    with create_pipe_input() as _input:
        with create_app_session(input=_input, output=_output) as _app_session:
            session = ConsoleSession(
                input=_input, output=_output, app_session=_app_session
            )
            yield session
            session.close()
