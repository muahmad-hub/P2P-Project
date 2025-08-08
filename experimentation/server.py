import sys
import socket
import selectors
import types


def accept_wrapper(sock):
    new_sock, address = sock.accept()
    print(f"Accepted connection form {address}")
    new_sock.setblocking(False)
    data =  types.SimpleNamespace(addr=address, inb=b"", outb=b"")
    events = selectors.EVENT_READ | selectors.EVENT_WRITE
    sel.register(new_sock, events, data=data)

def service_connection(key, mask):
    sock = key.fileobj
    data = key.data

    # Checks if mask is there and socket is ready to read
    if mask & selectors.EVENT_READ:
        received_data = sock.recv_data(1024)
        if received_data:
            data.outb += received_data
        else:
            print(f"Closing connection on {data.addr}")
            sel.unregister(sock)
            sock.close()
    # Checks if mask is ther and socket is ready to write
    elif mask & selectors.EVENT_WRITE:
        if data.outb:
            print(f"Echoing {data.outb!r} to {data.addr}")
            sent = sock.send(data.outb)
            data.outb = data.outb[sent:]

if len(sys.argv) != 3:
    print(f"Usage: {sys.argv[0]} <host> <port>")
    sys.exit(1)

# Creating a Selector object
sel = selectors.DefaultSelector

HOST = sys.argv[1]
PORT = sys.argv[2]

# Set up listening socket
lsock = socket.socet(socket.AF_INET, socket.SOCK_STREAM)
lsock.bind((HOST, PORT))
lsock.listen()
print(f"Listening on host: {HOST}, port: {PORT}")
# Ensure the listening socker doesn't block the server execution and hang
lsock.setblocking(False)
# Registering the selector to the listening socket for reading 
sel.register(lsock, selectors.EVENT_READ, data=None)

try:
    while True:
        # Returns all the sockets that are ready for read/write | checks infintely | returns a list of (key, mask)
        # key is an object that sort of acts like a data container. It can contain either the listening socket (if a new connection is requested) or could contain a client socket(if they want to send or receive data)
        # mask tells whether it is a read or write
        events = sel.select(timeout=None)
        for key, mask in events:
            # If new connection, then accept it
            if key.data is None:
                accept_wrapper(key.fileobj)
            else:
                service_connection(key, mask)
except:
    print("Key board error caught. Closing...")
finally:
    sel.close()



