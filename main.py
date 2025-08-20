import selectors
import socket
import uuid
import json
import threading
from collections import deque
import time

class Peer:
    def __init__(self, host, port):
        self.host = host
        self.port = port
        self.peer_id = uuid.uuid4().hex[:8]
        self.sel = selectors.DefaultSelector()
        self.is_socket_running = False
        # Listening socket
        self.lsock = None
        self.router = Router(self.peer_id)
        self.known_peers = {}
        self.connections = {}
        self.seen_message = set()

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
                        self.accept_new_connection()
                    else:
                        self.service_connection(key, mask)
        except:
            print("ERROR: listen socket couldn't listen")

    def start_server(self):
        self.create_listening_socket()
        self.running = True

        # Daemon thread terminates thread when the main porgram is terminated
        self.connection_thread = threading.Thread(target=self.start_listening, daemon=True)
        self.connection_thread.start()

    def accept_new_connection(self):
        try:
            new_socket, address = self.lsock.accept()
            new_socket.setblocking(False)
            data = PeerConnection(new_socket, address)
            self.sel.register(new_socket, selectors.EVENT_READ | selectors.EVENT_WRITE, data = data)
        except:
            print("ERROR: new connection not accepted")

    def service_connection(self, key, mask):
        connection = key.data
        sock = key.fileobj

        if mask & selectors.EVENT_READ:
            # Reading 4096 bytes as it is common due to its balance between effeciency and performance
            chunk_read = sock.recv(4096)
            if chunk_read:
                connection.inbound_buffer += chunk_read
                # Call the message service
                self.process_message(connection)
                # if there is a message
                    # handle the message

            else:
                self.sel.unregister(sock)
                sock.close()

        if mask & selectors.EVENT_WRITE and connection.outbound_buffer:
            try:
                sent = sock.send(connection.outbound_buffer)
                connection.outbound_buffer = connection.outbound_buffer[sent:]
            except:
                print("Error sending data")

    def process_message(self, connection):
        # Check if there is a complete message
        while connection.is_message_complete():
            message = connection.extract_message()
            if message:
                self.handle_message(message, connection)

    def handle_message(self, message, connection):
        # Checking if message is already seen to prevent message getting stuck in loops
        if message.message_id in self.seen_message:
            print("Ignoring seen message")
            return
        
        self.seen_message.add(message.message_id)

        if message.message_type == "HANDSHAKE":
            self.handle_handshake(message, connection)
        elif message.message_type == "MESSAGE":
            self.handle_user_message(message)

    def handle_handshake(self, message, connection):
        """
        PSEUDOCODE:
            Get peer id
            Add peer id to connection
            send a handshake response only if they are not in known peers
            Add peer id to kown peers
            call functions to update the network
            send peer list
        """

        # Extract peer id from message
        other_peer_id = message.peer_id

        print(f"Handshake from {other_peer_id}")

        # Add peer to current conenctions
        self.connections[other_peer_id] = connection

        # Send handshake if the received handshake is the first one (This prevents a infinite state in which the handshake is continously sent between peers)
        if other_peer_id not in self.known_peers:
            handshake_message = Message(peer_id=self.peer_id, target_user_id = other_peer_id, message_type="HANDSHAKE", data={"host": self.host, "port": self.port}, time_stamp=time.time())
            self.send_message(handshake_message)

        # Known peers is updated
        self.known_peers[other_peer_id] = {
            "host": message.data.get("host"),
            "port": message.data.get("port"),
        }

        # Functions to update the network structure are called
        self.router.update_peer_graph(other_peer_id)
        self.router.update_routing_graph(self.known_peers)

        # Socket data is updated
        connection.peer_id = other_peer_id
        connection.is_handshake_complete = True

        # Peer list is sent
        peer_list_message = Message(peer_id=self.peer_id, target_user_id=other_peer_id, message_type="PEER_LIST", data=self.known_peers, time_stamp=time.time())
        self.send_message(peer_list_message)

    def handle_user_message(self, message):
        if message.target_user_id == self.peer_id:
            print(f"Message from {message.peer_id}: {message.data.get('content', '')}")
        else:
            self.route_message(message)

    def route_message(self, message):
        target = message.target_user_id
        send_to = self.router.routing_graph.get(target)
        if send_to is None:
            print("Enable to send message as")
            return None
        self.send_message(message)
    
    def send_message(self, message):
        send_to = message.target_user_id
        if send_to in self.connections:
            message.add_hop(self.peer_id)
            self.connections[send_to].queue_message(message)
        else:
            print(f"{send_to} is not in connections")

class PeerConnection:
    def __init__(self, sock, address):
        self.peer_id = None
        self.socket = sock
        self.address = address
        self.inbound_buffer = b""
        self.outbound_buffer = b""
        self.is_handshake_complete = False

    def queue_message(self, message):
        json_message = message.to_json()
        message_bytes = (json_message + "\n").encode("utf-8")
        self.outbound_buffer += message_bytes

    def is_message_complete(self):
        """
        Checks and returns True if the message is complete
        """
        complete = True if b"\n" in self.inbound_buffer else False
        return complete
    
    def extract_message(self):
        """
        Extracts a complete messages from the inbound buffer if there is one
        """
        if not self.is_message_complete():
            return None
        
        line, self.inbound_buffer = self.inbound_buffer.split(b"\n", 1)
        try:
            return Message.from_json(line.decode("utf-8"))
        except:
            print("Error extracting the message")
            return None

class Message:
    """
    Stores:
    - Receiver and sender's peer_id
    - Message type
    - Message time stamp
    - Message id
    """
    def __init__(self, peer_id, target_user_id, message_type, data, time_stamp):
        self.peer_id = peer_id
        self.target_user_id = target_user_id
        self.message_type = message_type
        self.data = data
        self.time_stamp = time_stamp or time.time()
        self.message_id = uuid.uuid4().hex[:8]
        self.hop_count = 0
        self.path = [self.peer_id]

    def to_json(self):
        return json.dumps({
            "peer_id": self.peer_id,
            "target_user_id": self.target_user_id,
            "message_type": self.message_type,
            "data": self.data,
            "time_stamp": self.time_stamp,
            "message_id": self.message_id
        })
    
    @classmethod
    def from_json(cls, json_str):
        data = json.loads(json_str)
        message = cls(data["peer_id"], data["target_user_id"], data["message_type"], data["data"], data["time_stamp"])
        message.message_id = data["message_id"]
        return message
    
    def add_hop(self, peer_id):
        self.hop_count += 1
        self.path.append(peer_id)

class Router:
    def __init__(self, peer_id):
        # Dictionary of the which peer to route to depending on the target peer
        self.routing_graph = {}
        # Adjacency matrix of all the connected peer of each peer
        self.peer_graph = {}
        self.peer_id = peer_id

    def BFS_path_finding(self, target_peer_id):
        """
        Breadth-first search used to find the shortest path (with the smallest hops)

        PSEUDOCODE:
            var start node
            add start node to frontier


            while frontier is not empty
                pop node and path from frontier (BFS is FIFO)
                if node was already explored then skip loop
                is the node the target node, if yes then return else keep going
                find neighbours
                append neirbours to the frontier along with the updated path
        """

        frontier = deque()
        explored_nodes = set()

        start_node = self.peer_id
        frontier.append((start_node, [start_node]))

        while frontier:
            current_node, current_path = frontier.popleft()
            if current_node in explored_nodes:
                continue
            explored_nodes.add(current_node)
            if current_node == target_peer_id:
                return current_path
            neighbors = self.peer_graph.get(current_node, set())
            for neighbor in neighbors:
                if neighbor not in explored_nodes:
                    frontier.append((neighbor, current_path + [neighbor]))
        return None
    
    def get_next_hop(self, current_node, path, update_path=False):
        try:
            index = path.index(current_node)
            if index + 1 >= len(path):
                return None
            next_node = path[index + 1]

            if update_path:
                new_path = path[:index] + path[index+1:]
                return next_node, new_path

            return next_node
        except:
            return None


    def update_routing_graph(self, known_peers):
        """
        Precomputes the routing procedure using BFS

        PSEUDOCODE:
            function
                loop over all known peers
                    if peer is itself then skip loop
                    run the bfs
                    get the next hop from start node
                    update the table as this 'to get to': 'send to'

        """
        self.routing_graph = {}
        for target_peer in known_peers:
            if target_peer == self.peer_id:
                continue
            path = self.BFS_path_finding(target_peer)
            if path:
                next_hop = self.get_next_hop(self.peer_id, path)
                if next_hop:
                    self.routing_graph[target_peer] = next_hop

    def update_peer_graph(self, other_peer_id):
        if self.peer_id not in self.peer_graph:
            self.peer_graph[self.peer_id] = set()
        if other_peer_id not in self.peer_graph:
            self.peer_graph[other_peer_id] = set()

        self.peer_graph[self.peer_id].add(other_peer_id)
        self.peer_graph[other_peer_id].add(self.peer_id)
             
if __name__ == "__main__":
    peer1 = Peer("localhost", 8001)
    peer1.is_socket_running = True
    peer1.start_server()
    print(f"Peer1 started: {peer1.peer_id}")
    
    peer2 = Peer("localhost", 8002)
    peer2.is_socket_running = True
    peer2.start_server()
    print(f"Peer2 started: {peer2.peer_id}")
    
    time.sleep(0.5)
    
    try:
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.connect(("localhost", 8001))
        
        handshake = Message(peer2.peer_id, peer1.peer_id, "HANDSHAKE", 
                          {"host": "localhost", "port": 8002}, time.time())
        sock.send((handshake.to_json() + "\\n").encode())
        
        print("Handshake sent!")
        time.sleep(2)
        
        print(f"Peer1 knows: {list(peer1.known_peers.keys())}")
        print(f"Peer2 knows: {list(peer2.known_peers.keys())}")
        
    except Exception as e:
        print(f"Connection test failed: {e}")
    
    time.sleep(1)
    print("Test complete")