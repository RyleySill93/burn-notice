# This has to get called first
from src.network.http.telemetry import instrument_server

instrument_server()

from src import setup

setup.run()

from src.network.http.server import server as http_server

# Called from makefile which actually boots the server
server = http_server
