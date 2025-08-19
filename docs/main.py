import selectors
import socket
import uuid
import json
import threading

class Peer:
    def __init__(self, host, port):
        self.host = host
        self.port = port
        self.peer_id = uuid.uuid4().hex[:8]
        self.sel = selectors.DefaultSelector
        self.is_socket_running = False
        # Listening socket
        self.lsock = None
        self.router = Router()

    def create_listening_socket(self):
        """
        Creates listening socket with TCP connection
        Options set so that address can be reused without error
        Non-blocking socket
        """
        self.lsock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        # Prevents "Address already in use" errors
        self.lsock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        self.lsock.bind((self.host, self.port))
        # Member can only listen for 5 peers at a time 
        self.lsock.listen(5)
        self.lsock.setblocking(False)
        self.sel.register(self.lsock, selectors.EVENT_READ, data="LISTEN")
        print(f"Listening socket created for member {self.peer_id}")

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
            data = PeerConnection(new_socket, address)
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
                # Call the message service
                self.process_message(socket_data)
                # if there is a message
                    # handle the message

            else:
                self.sel.unregister()
                sock.close()

    # Function to process message
    def process_message(self, socket_data):
        # Check if there is a complete message
        while socket_data.is_message_complete:
            message = socket_data.extract_message
            if message:
                self.handle_message(message, socket_data)


    # Handle different messages
    def handle_message(self, message, socket_data):
        if message.type == "HANDSHAKE":
            self.handle_handshake(message, socket_data)


    # Handshake handler
        # get the peer id of the other person
        # Add it to the peer network
        # Add both as ti is an adjacency matrix

    def handle_handshake(self, message, socket_data):
        other_peer_id = message.peer_id

        print(f"Handshake from {other_peer_id}")

        self.router.peer_graph[self.peer_id].add(other_peer_id)
        self.router.peer_graph[other_peer_id].add(self.peer_id)

        socket_data.peer_id = other_peer_id
        socket_data.is_handshake_complete = True



        



    def start_server(self):
        self.create_listening_socket()
        self.running = True

        # Daemon thread terminates thread when the main porgram is terminated
        self.connection_thread = threading.Thread(target=self.start_listening, daemon=True)
        self.connection_thread.start()

class PeerConnection:
    def __init__(self, sock, address):
        self.peer_id = None
        self.socket = sock
        self.address = address
        self.inbound_buffer = b""
        self.outbound_buffer = b""
        self.is_handshake_complete = False

    # Checks and returns True if the message is complete
    def is_message_complete(self):
        complete = True if b"\n" in self.inbound_buffer else False
        return complete
    
    def extract_message(self):
        if not self.is_message_complete():
            return None
        
        line, self.inbound_buffer = self.inbound_buffer.split(b"\n", 1)
        try:
            return Message.from_json(line.decode("utf-8"))
        except:
            print("Error extracting the message")
            return None

# Stores:
    # - Receiver and sender's peer_id
    # - Message type
    # - Message time stamp
    # - Message id
class Message:
    def __init__(self, peer_id, target_user_id, message_type, data, time_stamp, message_id):
        self.peer_id = peer_id
        self.target_user_id = target_user_id
        self.type = message_type
        self.data = data
        self.time_stamp = time_stamp
        self.message_id = message_id

    def to_json(self, message):
        return json.dumps({
            "peer_id": self.peer_id,
            "target_user_id": self.target_user_id,
            "type": self.type,
            "data": self.data,
            "time_stamp": self.time_stamp,
            "message_id": self.message_id
        })
    
    @classmethod
    def from_json(cls, json_str):
        data = json.loads(json_str)
        message = cls(data["type"], data["peer_id"], data["message_type"], data["data"])
        message.timestamp = data["timestamp"]
        message.message_id = data["message_id"]
        return message

'''
# Class Router
#     BFS
#     Get the next node to travel to 
#     Update the routing table

'''

class Router():
    def __init__(self):
        # Adjacency matrix
        self.routing_graph = None
        self.peer_graph = {}


    
