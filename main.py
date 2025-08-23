import selectors
import socket
import uuid
import json
import threading
from collections import deque
import time
import sys

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
        self.seen_messages = set()

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
                events = self.sel.select(timeout=1)
                for key, mask in events:
                    if key.data == "LISTEN":
                        self.accept_new_connection()
                    else:
                        self.service_connection(key, mask)
        except:
            print("ERROR: listen socket couldn't listen")

    def start_server(self):
        self.create_listening_socket()
        self.is_socket_running = True

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
            try: 
                # Reading 4096 bytes as it is common due to its balance between effeciency and performance
                chunk_read = sock.recv(4096)
                if chunk_read:
                    connection.inbound_buffer += chunk_read
                    self.process_message(connection)
                else:
                    # If no data is passed (like b""), it means peer is requesting to close connection
                    self.cleanup_connection(connection, sock)
            except (BlockingIOError, ConnectionResetError):
                self.cleanup_connection(connection, sock)

        if mask & selectors.EVENT_WRITE and connection.outbound_buffer:
            result = connection.send_buffered_data()
            # Cleans up connection if it ended
            if result is None:
                self.cleanup_connection(connection, sock)

    def process_message(self, connection):
        # Check if there is a complete message
        while connection.is_message_complete():
            message = connection.extract_message()
            if message:
                self.handle_message(message, connection)

    def handle_message(self, message, connection):
        # Checking if message is already seen to prevent message getting stuck in loops
        if message.message_id in self.seen_messages:
            print("Ignoring seen message")
            return
        
        self.seen_messages.add(message.message_id)

        if message.message_type == "HANDSHAKE":
            self.handle_handshake(message, connection)
        elif message.message_type == "MESSAGE":
            self.handle_user_message(message)
        elif message.message_type == "PEER_LIST":
            self.handle_peer_list(message)
        elif message.message_type == "NETWORK_UPDATE":
            self.handle_network_structure_message(message)

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
            connection.queue_message(handshake_message)

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
        connection.queue_message(peer_list_message)
        network_message = Message(
            peer_id=self.peer_id,
            target_user_id=other_peer_id,
            message_type="NETWORK_UPDATE",
            data={"peer_graph": {key: list(value) for key, value in self.router.peer_graph.items()}},
            time_stamp=time.time()
        )
        connection.queue_message(network_message)
        for existing_peer_id, existing_connection in self.connections.items():
            if existing_peer_id != other_peer_id and existing_connection.is_handshake_complete:
                # Send the updated known_peers list to existing connections
                updated_peer_list = Message(
                    peer_id=self.peer_id,
                    target_user_id=existing_peer_id,
                    message_type="PEER_LIST",
                    data=self.known_peers,
                    time_stamp=time.time()
                )
                existing_connection.queue_message(updated_peer_list)
                updated_network = Message(
                    peer_id=self.peer_id,
                    target_user_id=existing_peer_id,
                    message_type="NETWORK_UPDATE",
                    data={"peer_graph": {key: list(value) for key, value in self.router.peer_graph.items()}},
                    time_stamp=time.time()
                )
                existing_connection.queue_message(updated_network)

    def handle_user_message(self, message):
        if message.target_user_id == self.peer_id:
            print(f"Message from {message.peer_id}: {message.data.get('content', '')}")
        else:
            self.route_message(message)

    def handle_peer_list(self, message):
        peer_list = message.data
        new_discoveries = 0
        
        for peer_id, peer_info in peer_list.items():
            if peer_id != self.peer_id and peer_id not in self.known_peers:
                self.known_peers[peer_id] = peer_info
                new_discoveries += 1
        
        if new_discoveries > 0:
            print(f"Peer {self.peer_id} discovered {new_discoveries} new peers")
            self.router.update_routing_graph(self.known_peers)

    def handle_network_structure_message(self, message):
        """
        Handles updated network structure information from peers
        This is to allow the BFS to carry out accurate routing
        """
        received_graph = message.data.get("peer_graph")
        network_updated = False

        for peer_id, neighbors in received_graph.items():
            if peer_id not in self.router.peer_graph:
                self.router.peer_graph[peer_id] = set()
                network_updated = True

            for neighbor in neighbors:
                if neighbor not in self.router.peer_graph:
                    self.router.peer_graph[neighbor] = set()

                    if neighbor not in self.router.peer_graph[peer_id]:
                        self.router.peer_graph[peer_id].add(neighbor)
                        network_updated = True
                        if peer_id not in self.router.peer_graph[neighbor]:
                            self.router.peer_graph[neighbor].add(peer_id)
                            network_updated = True
            
            if network_updated:
                print("Network updated")
                self.router.update_routing_graph(self.known_peers)

    def route_message(self, message):
        target = message.target_user_id

        # Gets the next hop on the path
        next_hop = self.router.routing_graph.get(target)
        
        if next_hop is None:
            print(f"No route to {target}")
            return False
        
        if next_hop in self.connections:
            message.add_hop(self.peer_id)
            self.connections[next_hop].queue_message(message) 
            print(f"Forwarded message for {target} via {next_hop}")
            return True
        else:
            print(f"Next hop {next_hop} not connected")
            return False

    def send_message(self, message):
        target = message.target_user_id
        
        if target in self.connections and target != self.peer_id:
            message.add_hop(self.peer_id)
            self.connections[target].queue_message(message)
            print(f"Sent direct message to {target}")
            return True
        else:
            return self.route_message(message)

    def connect_to_peer(self, host, port):
        try:
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            sock.setblocking(False)
            
            result = sock.connect_ex((host, port))
            if result != 0 and result != 10035:
                sock.close()
                print(f"Failed to connect to {host}:{port}")
                return False
            
            # Creating connection and registeingr with selector
            connection = PeerConnection(sock, address=(host, port))
            self.sel.register(sock, selectors.EVENT_READ | selectors.EVENT_WRITE, data=connection)
            
            # Send handshake
            handshake = Message(self.peer_id, None, "HANDSHAKE", {"host": self.host, "port": self.port}, time.time())
            connection.queue_message(handshake)
            
            print(f"Connecting to {host}:{port}...")
            return True
            
        except Exception as e:
            print(f"Connection error: {e}")
            return False
        
    def cleanup_connection(self, connection, sock):
        """
        Removes connection and peer from memeory and from router
        """
        self.sel.unregister(sock)
        sock.close()
        if connection.peer_id:
            self.connections.pop(connection.peer_id, None)
            self.known_peers.pop(connection.peer_id, None)
            self.router.remove_peer(connection.peer_id)
        print(f"Cleaned up connection {connection.address}")
   
    def close_current_peer(self):
        """
        Closes the current peer
        """
        print("Closing down peer...")
        self.is_socket_running = False
        
        # Close all peer connections with current peer
        for connection in list(self.connections.values()):
            try:
                connection.socket.close()
            except:
                pass
        
        # Closes listening socket
        if self.lsock:
            try:
                self.sel.unregister(self.lsock)
                self.lsock.close()
            except:
                pass
        
        # Closes selector
        try:
            self.sel.close()
        except:
            pass
        
        print("Peer closing complete")

class PeerConnection:
    # Setting maximum buffer size as 1 MB
    MAX_BUFFER_SIZE = 1024 * 1024

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

        # Handling maximum buffer size overflow
        if len(self.outbound_buffer) + len(message_bytes) > self.MAX_BUFFER_SIZE:
            print(f"Maximum buffer sized reached on outbound buffer for {self.address}")
            return False
        
        self.outbound_buffer += message_bytes
        return True

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
        
        try:
            line, self.inbound_buffer = self.inbound_buffer.split(b"\n", 1)
            return Message.from_json(line.decode("utf-8"))
        except Exception as e:
            print(f"Error extracting the message: {e}")
            return None
        
    def send_buffered_data(self):
        """
        Sends data in the outbound buffer with Error handling
        Returns the following:
            True: if the outbound buffer is empty
            False: if there is still data left in the buffer
            None: if connection closed or broke
        """
        # Checks if outbound buffer is empty (all the data is already sent)
        if not self.outbound_buffer:
            return True
        
        try:
            sent = self.socket.send(self.outbound_buffer)
            self.outbound_buffer = self.outbound_buffer[sent:]
            # Returning False to signal data is still left to be sent in the bufer
            return True if not self.outbound_buffer else False
        except BlockingIOError:
            # Returning False to signal to try later as OS send buffer is full
            return False
        except ConnectionResetError:
            # Returning None to indicate that connection has closed
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
            "message_id": self.message_id,
            "hop_count": self.hop_count,
            "path": self.path,
        })
    
    @classmethod
    def from_json(cls, json_str):
        # Error handling incase Json throws an error, prevents whole network from crashing
        try:
            data = json.loads(json_str)
        except json.JSONDecodeError:
            return None
        
        # Checking required fields so no malicious, corrupted, or wrong data is parsed and sent
        required_fields = ["peer_id", "target_user_id", "message_type", "data", "time_stamp", "message_id"]
        if not all(field in data for field in required_fields):
            return None
        
        # Checking types for each message's attribute to prevent malicious or corrupted data
        if not isinstance(data["peer_id"], str): return None
        if not isinstance(data["target_user_id"], (str, type(None))): return None
        if not isinstance(data["message_type"], str): return None
        if not isinstance(data["data"], dict): return None
        if not isinstance(data["time_stamp"], (int, float)): return None
        if not isinstance(data["message_id"], str): return None
        if not isinstance(data.get("hop_count", 0), int): return None
        if not isinstance(data.get("path", []), list): return None

        # Adding another check to prevent message being sent in loops (Each peer already had a seen_messages list)
        if data.get("hop_count", 0) > 10:
            return None

        message = cls(data["peer_id"], data["target_user_id"], data["message_type"], data["data"], data["time_stamp"])
        message.message_id = data["message_id"]
        message.hop_count = data.get("hop_count", 0)
        message.path = data.get("path", [data["peer_id"]])
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

        # Handling edge cases
        if target_peer_id == self.peer_id:
            return [self.peer_id]
        if target_peer_id not in self.peer_graph:
            return None
        
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
             
    def remove_peer(self, other_peer_id):
        """
        Removes disconnected peers from Router
        """

        # Remove from peer graph
        if other_peer_id in self.peer_graph:
            del self.peer_graph[other_peer_id]
        
        # Remove from routing graph
        # Using keys_to_remove list to prevent editing the dictionary while iterating over it
        keys_to_remove = []
        for destination, hop in self.routing_graph.items():
            if destination == other_peer_id or hop == other_peer_id:
                keys_to_remove.append(destination)
        for key in keys_to_remove:
            del self.routing_graph[key]

        # Remove from other peers' connection
        for other_peer, connection in self.peer_graph.items():
            if other_peer_id in connection:
                connection.remove(other_peer_id)

class cli_interface:
    def __init__(self, peer):
        self.peer = peer
        self.running = True

    def print_help(self):
        """
        Displays the help text 
        """
        help_text = """
            Available Commands:
            connect (host) (port) - Connect to another peer
            send (peer_id) (message) - Send message to peer
            list - Show known peers and status
            status - Display system statistics
            help - Show command help
            quit - Graceful shutdown
        """
        print(help_text)

    def cmd_connect(self, args):
        """
        Handle connect command
        """
        if len(args) != 2:
            print("Usage: connect (host) (port)")
            return
        
        host = args[0]
        try:
            port = int(args[1])
        except ValueError:
            print("Error: Port must be a number")
            return
            
        success = self.peer.connect_to_peer(host, port)
        if success:
            print(f"Connection initiated to {host} {port}")
        else:
            print(f"Failed to connect to {host} {port}")

    def cmd_send(self, args):
        """
        Handle send message command
        """
        if len(args) < 2:
            print("Usage: send (peer_id) (message)")
            return
        
        target_peer_id = args[0]
        message_content = " ".join(args[1:])
        
        if target_peer_id not in self.peer.known_peers and target_peer_id not in self.peer.connections:
            print(f"Unknown peer: {target_peer_id}")
            return
        
        message = Message(
            peer_id=self.peer.peer_id,
            target_user_id=target_peer_id,
            message_type="MESSAGE",
            data={"content": message_content},
            time_stamp=time.time()
        )
        
        success = self.peer.send_message(message)
        if success:
            print(f"Message sent to {target_peer_id}")
        else:
            print(f"Failed to send message to {target_peer_id}")

    def cmd_list(self, args):
        """
        Handle list peers command
        """
        print(f"___Peer List for {self.peer.peer_id}___")
        print(f"Listening on: {self.peer.host}:{self.peer.port}")
        
        print(f"\nConnected Peers ({len(self.peer.connections)}):")
        if self.peer.connections:
            for peer_id, connection in self.peer.connections.items():
                status = "Connected" if connection.is_handshake_complete else "Connecting"
                print(f"  {peer_id} - {connection.address} ({status})")
        else:
            print("None")
        
        print(f"\nKnown Peers ({len(self.peer.known_peers)}):")
        if self.peer.known_peers:
            for peer_id, info in self.peer.known_peers.items():
                connected = "Yes" if peer_id in self.peer.connections else "No"
                print(f"  {peer_id} - {info['host']}:{info['port']} (Connected: {connected})")
        else:
            print("None")

    def cmd_status(self, args):
        """
        Handle status command
        """
        print(f"\n___System Status___")
        print(f"Peer ID: {self.peer.peer_id}")
        print(f"Listening: {self.peer.host}:{self.peer.port}")
        print(f"Status: {'Running' if self.peer.is_socket_running else 'Stopped'}")
        print(f"Connected Peers: {len(self.peer.connections)}")
        print(f"Known Peers: {len(self.peer.known_peers)}")
        print(f"Routing Entries: {len(self.peer.router.routing_graph)}")
        print(f"Seen Messages: {len(self.peer.seen_messages)}")
        
        # Shows routing table
        if self.peer.router.routing_graph:
            print(f"\nRouting Table:")
            for target, next_hop in self.peer.router.routing_graph.items():
                print(f"  To {target} via {next_hop}")
        else:
            print(f"\nRouting Table: Empty")

    def cmd_quit(self, args):
        """
        Handle quit command
        """
        print("Shutting down...")
        self.running = False
        self.peer.close_current_peer()

    def cmd_help(self, args):
        """
        Handle help command
        """
        self.print_help()

    def parse_command(self, user_input):
        """
        Parse and execute user command
        """
        user_input = user_input.strip()
        
        if not user_input:
            return
        
        # Split input into command and arguments
        parts = user_input.split()
        command = parts[0].lower()
        args = parts[1:]
        
        # Commands dictionary
        commands = {
            'connect': self.cmd_connect,
            'send': self.cmd_send,
            'list': self.cmd_list,
            'status': self.cmd_status,
            'help': self.cmd_help,
            'quit': self.cmd_quit,
            # Adding additional command to quit
            'exit': self.cmd_quit,
        }
        
        if command in commands:
            commands[command](args)
        else:
            print(f"Unknown command: '{command}'. Type 'help' for available commands.")

    def run(self):
        """
        Main CLI loop
        """
        print(f"___P2P Network CLI___")
        print(f"Peer ID: {self.peer.peer_id}")
        print(f"Listening on: {self.peer.host}:{self.peer.port}")
        print("Type 'help' for available commands.")
        
        while self.running:
            try:
                user_input = input(f"\n[{self.peer.peer_id}]> ")
                if user_input:
                    self.parse_command(user_input)
            except KeyboardInterrupt:
                print("\nReceived Ctrl+C, shutting down...")
                self.cmd_quit([])
                break

def main():
    if len(sys.argv) != 3:
        print("Usage: python main.py (host) (port)")
        sys.exit(1)
    
    try:
        host = sys.argv[1]
        port = int(sys.argv[2])
    except ValueError:
        print("Error: Port must be a number")
        sys.exit(1)
    
    peer = Peer(host, port)
    peer.start_server()
    
    cli = cli_interface(peer)
    cli.run()

if __name__ == "__main__":
    main()
