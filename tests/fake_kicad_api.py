"""A stand-in for KiCad's IPC API server, for running the IPC plugin without
KiCad (see TESTING.md). It answers GetVersion (10.0.6) and GetOpenDocuments
(one board open in the PCB Editor, the Schematic Editor closed) with
kicad-python's own protobuf messages over a real NNG socket, checks the
token the way KiCad does, and prints every request it gets.

Needs kicad-python, so run it with the plugin's venv Python:

    python tests/fake_kicad_api.py tcp://127.0.0.1:5555 /path/to/board.kicad_pcb <token>

then start ipc_main.py with KICAD_API_SOCKET=tcp://127.0.0.1:5555 and
KICAD_API_TOKEN=<token>. (A tcp:// address avoids macOS's ~104-character
limit on ipc:// socket paths; the plugin doesn't care which it gets.)
"""
import sys
from pathlib import Path

import pynng
from kipy.proto.common import ApiRequest, ApiResponse, ApiStatusCode, commands
from kipy.proto.common.types import DocumentType


def answer(request, board: Path, token: str):
    name = request.message.TypeName().rsplit(".", 1)[-1]
    reply = ApiResponse()
    reply.header.kicad_token = token
    sent = request.header.kicad_token
    print(f"request {name} token={'ok' if sent == token else sent or '(empty)'}", flush=True)
    if sent and sent != token:                  # as common/api/api_server.cpp does
        reply.status.status = ApiStatusCode.AS_TOKEN_MISMATCH
        return reply
    if name == "GetVersion":
        body = commands.GetVersionResponse()
        body.version.major, body.version.minor, body.version.patch = 10, 0, 6
        body.version.full_version = "10.0.6 (stand-in)"
    elif name == "GetOpenDocuments":
        command = commands.GetOpenDocuments()
        request.message.Unpack(command)
        if command.type != DocumentType.DOCTYPE_PCB:
            reply.status.status = ApiStatusCode.AS_UNHANDLED
            reply.status.error_message = "no handler (editor not open)"
            return reply
        body = commands.GetOpenDocumentsResponse()
        doc = body.documents.add()
        doc.type = DocumentType.DOCTYPE_PCB
        doc.board_filename = board.name
        doc.project.name = board.stem
        doc.project.path = str(board.parent)
    else:
        reply.status.status = ApiStatusCode.AS_UNHANDLED
        return reply
    reply.status.status = ApiStatusCode.AS_OK
    reply.message.Pack(body)
    return reply


def main(argv) -> int:
    if len(argv) != 4:
        print(__doc__.strip(), file=sys.stderr)
        return 2
    url, board, token = argv[1], Path(argv[2]).resolve(), argv[3]
    with pynng.Rep0(listen=url) as rep:
        print("listening", url, flush=True)
        while True:
            request = ApiRequest.FromString(rep.recv())
            rep.send(answer(request, board, token).SerializeToString())


if __name__ == "__main__":
    sys.exit(main(sys.argv))
