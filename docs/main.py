import selectors
import socket
import uuid
import types
import threading

class Member:
    def __init__(self, host, port):
        self.host = host
        self.port = port
        self.member_id = uuid.uuid4().hex[:8]
        self.sel = selectors.DefaultSelector
        self.is_socket_running = False
        # Listening socket
        self.lsock = None

    def create_listening_socket(self):
        """
        Creates listening socket with TCP connection
        Options set so that address can be reused without error
        Non-blocking socket
        """
        lsock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        # Prevents "Address already in use" errors
        self.listening_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        lsock.bind((self.host, self.port))
        # Member can only listen for 5 peers at a time 
        lsock.listen(5)
        lsock.setblocking(False)
        self.sel.register(lsock, selectors.EVENT_READ, data="LISTEN")
        print(f"Listening socket created for member {self.member_id}")

    def start_listening(self):
        """
        Listening socket checks for whether incoming request is by previous client or a new client
        """
        try:
            while self.is_socket_running:
                events = self.sel.select()
                for key, mask in events:
                    if key.data == "LISTEN":
                        self.accept_new_connection(key)
                    else:
                        self.service_request(key, mask)
        except:
            print("ERROR: listen socket couldn't listen")

    def accept_new_connection(self):
        try:
            new_socket, address = socket.accept()
            new_socket.setblocking(False)
            data = MemberConnection(new_socket, address)
            self.sel.register(new_socket, selectors.EVENT_READ | selectors.EVENT_WRITE, data = data)
        except:
            print("ERROR: new connection not accepted")

    def service_connection(self, key, mask):
        socket_data = key.data
        sock = key.fileobj

        if mask & selectors.EVENT_READ:
            # Reading 4096 bytes as it is common due to its balance between effeciency and performance
            chunk_read = sock.recv(4096)

            if chunk_read:
                socket_data.inbound_data += chunk_read
            else:
                self.sel.unregister()
                sock.close()

    def start_server(self):
        self.create_listening_socket()
        self.running = True

        # Daemon thread terminates thread when the main porgram is terminated
        self.connection_thread = threading.Thread(target=self.start_listening, daemon=True)
        self.connection_thread.start()

class MemberConnection:
    def __init__(self, sock, address):
        self.socket = sock
        self.address = address
        self.inbound_buffer = b""
        self.outbound_buffer = b""

