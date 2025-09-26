import socket
import sys
import os
from dotenv import load_dotenv
from pathlib import Path
from ..packet.packet import Packet
from ..packet.packet import Null
from ..packet.packet import Status 
from ..packet.packet import Login
from ..packet.packet import intent

load_dotenv(Path(__file__).resolve().parents[2] / ".env", override=True)

PORT=25565
TIMEOUT_TIME=1
CLIENTS=1
PACKET_SIZE=2097152

server = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
server.bind((os.environ.get('IP'), PORT))

server.settimeout(TIMEOUT_TIME)
server.listen(CLIENTS)

# --------------------------------------------------
# Debug loop

try:
    while True:
        try:
            client, addr = server.accept()
        except socket.timeout:
            # loop back and check for KeyboardInterrupt
            continue

        try:
            received = Packet('r', client)
            print(received.data)

            # If the first packet was a handshake, then the client will immedietly send a status request
            if isinstance(received.data[1], Null.inbound) and received.data[5] == intent.Status:
                received = Packet('r', client)
                print(received.data)

            if isinstance(received.data[1], Null.inbound) and received.data[5] == intent.Login:
                received = Packet('r', client)
                print(received.data)

            if Packet.state == intent.Status:
                if isinstance(received.data[1], Status.inbound):
                    match received.data[1]:
                        case Status.inbound.status_request:
                            response = Packet('w', client, Packet.write_status_response())
                        case Status.inbound.ping_request:
                            response = Packet('w', client, received.write_pong_response())
            
            elif Packet.state == intent.Login:
                if isinstance(received.data[1], Login.inbound):
                    response = Packet('w', 
                                      client, 
                                      Packet.writeDisconnect(
                                          '{text: "Server is starting, please wait.", color: "green"}'))
                    Packet.updateState(intent.Status)
        except Exception as e:
            print(e)

except KeyboardInterrupt:
    # allow Ctrl+C to stop the server
    print('\nKeyboardInterrupt received, shutting down...')
finally:
    try:
        server.close()
    except Exception:
        pass
    sys.exit(0)

# --------------------------------------------------