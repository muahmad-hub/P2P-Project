import socket
import sys
import selectors
import types

sel = selectors.DefaultSelector()
messages = [b"Hello", b"World"]

def start_connections(host, port, num_conn):
    server_address = (host, port)
    for i in range(num_conn):
        conn_id = i + 1
        print(f"Starting connection with id {conn_id} to {server_address}")
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        # Don't need to bind socket as your the client, your don't listening to any sockets
        sock.setblocking(False)
        sock.connect_ex(server_address)
        events = selectors.EVENT_READ | selectors.EVENT_WRITE
        data = types.SimpleNamespace(
            conn_id=conn_id,
            messge_total=sum(len(m) for m in messages),
            recv_total=0,
            messages=messages.copy(),
            outb=b"",
        )
        sel.register(sock, events, data=data)

def service_connection(key, mask):
    sock = key.fileobj
    data = key.data

    if mask & selectors.EVENT_READ:
        # Reads the data
        recv_data = sock.recv(1024)
        # If there was data, then updates the amount received
        if recv_data:
            print(f"Received {recv_data!r} from connection id {data.conn_id}")
            data.recv_total += len(recv_data)
        # If either data sent was empty (server sent message to disconnect) or all the message is received, then close the connection
        if not recv_data or data.recv_total == data.message_total:
            print(f"Clossing connection with id {data.conn_id}")
            sel.unregister(sock)
            sock.close()
    if mask & selectors.EVENT_WRITE:
        # Checks if buffer is empty and there are still messages left to send
        if not data.outb and data.messages:
            # Loads the message into the buffer
            data.outb = data.messages.pop(0)
        if data.outb:
            print(f"Sending {data.outb!r} to server through connection id {data.conn_id}")
            sent = sock.send(data.outb)
            data.outb = data.outb[sent:]

if len(sys.argv) != 4:
    print(f"Usage: {sys.argv[0]} <host> <port> <number_connections>")
    sys.exit(1)

HOST = sys.argv[1]
PORT = sys.argv[2]
NUM_CONN = sys.argv[3]

start_connections(HOST, PORT, NUM_CONN)

try:
    while True:
        # Makes the socket wait for one second
        events = sel.select(timeout=1)
        if events:
            for key, mask in events:
                service_connection(key, map)
        # Checks if there still are any sockets
        if not sel.get_map():
            break
except KeyboardInterrupt:
    print("Keyborad Interrupt, closing...")
finally:
    sel.close()
