import socket
from ..packet.reader import readDisconnect

client = socket.socket(socket.AF_INET, socket.SOCK_STREAM)

client.connect(("127.0.0.1", 25565))

print(readDisconnect(client.recv(1024)))