import time
import socket
import sys
from ..packet.writer import writeDisconnect

server = socket.socket(socket.AF_INET, socket.SOCK_STREAM)

server.bind(("127.0.0.1", 25565))

# Make accept() timeout periodically so KeyboardInterrupt can be handled reliably
server.settimeout(0.1)
server.listen(2)

try:
    while True:
        try:
            client, _ = server.accept()
        except socket.timeout:
            # loop back and check for KeyboardInterrupt
            continue

        message = writeDisconnect('{text: "Server is starting, please wait.", color: "green"}')
        time.sleep(1)
        client.sendall(message)
        print("Message sent!")

except KeyboardInterrupt:
    # allow Ctrl+C to stop the server
    print('\nKeyboardInterrupt received, shutting down...')
finally:
    try:
        server.close()
    except Exception:
        pass
    sys.exit(0)