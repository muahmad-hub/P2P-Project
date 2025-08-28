import selectors
import socket
import uuid
import threading
import time
import os
from router import Router
from connection import PeerConnection
from message import Message
from message_store import MessageStore

class Peer:
    def __init__(self, host, port):
        self.host = host
        self.port = port
        self.peer_id = self.load_or_create_peer_id()
        self.sel = selectors.DefaultSelector()
        self.is_socket_running = False
        # Listening socket
        self.lsock = None
        self.router = Router(self.peer_id)
        self.known_peers = {}
        self.connections = {}
        self.seen_messages = set()
        # Setting message_store for storing offline messages and retry scheduler
        self.message_store = MessageStore(self.peer_id)
        self.retry_scheduler = {}

    def load_or_create_peer_id(self):
        """
        If first time user, then a new id is created for them and stored locally
        If not first time user, then the peer id is retreived
        """
        peer_id_file = f"ids/peer_{self.host}_{self.port}.id"
        if os.path.exists(peer_id_file):
            with open(peer_id_file, 'r') as f:
                return f.read().strip()
        else:
            new_id = uuid.uuid4().hex[:8]
            with open(peer_id_file, 'w') as f:
                f.write(new_id)
            return new_id

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
        except Exception as e:
            print(f"ERROR: {e}")

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
        Handles a peers incoming handshake

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
        print(f"[{self.peer_id}]> ", end="", flush=True)

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

        # Deliver any message that was queued for this peer
        self.deliver_queued_messages(other_peer_id)

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
            print(f"\nMessage from {message.peer_id}: {message.data.get('content', '')}")
            print(f"[{self.peer_id}]> ", end="", flush=True)
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
            print(f"[{self.peer_id}]> ", end="", flush=True)
            self.router.update_routing_graph(self.known_peers)

            for existing_peer_id, existing_connection in self.connections.items():
                if existing_connection.is_handshake_complete:
                    updated_peer_list = Message(
                        peer_id=self.peer_id,
                        target_user_id=existing_peer_id,
                        message_type="PEER_LIST",
                        data=self.known_peers,
                        time_stamp=time.time()
                    )
                    existing_connection.queue_message(updated_peer_list)

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
                    network_updated = True

                if neighbor not in self.router.peer_graph[peer_id]:
                    self.router.peer_graph[peer_id].add(neighbor)
                    network_updated = True
                if peer_id not in self.router.peer_graph[neighbor]:
                    self.router.peer_graph[neighbor].add(peer_id)
                    network_updated = True
        
        if network_updated:
            print("Network updated")
            print(f"[{self.peer_id}]> ", end="", flush=True)
            self.router.update_routing_graph(self.known_peers)
            
            # Sends update to all connected users
            for existing_peer_id, existing_connection in self.connections.items():
                if existing_peer_id != message.peer_id and existing_connection.is_handshake_complete:
                    updated_network = Message(
                        peer_id=self.peer_id,
                        target_user_id=existing_peer_id,
                        message_type="NETWORK_UPDATE",
                        data={"peer_graph": {key: list(value) for key, value in self.router.peer_graph.items()}},
                        time_stamp=time.time()
                    )
                    existing_connection.queue_message(updated_network)

    def route_message(self, message):
        target = message.target_user_id

        # Gets the next hop on the path
        next_hop = self.router.routing_graph.get(target)
        
        if next_hop is None:
            print(f"No route to {target}, queing for later")
            self.queue_offline_message(message)
            return False
        
        if next_hop in self.connections:
            message.add_hop(self.peer_id)
            self.connections[next_hop].queue_message(message) 
            print(f"Forwarded message for {target} via {next_hop}")
            return True
        else:
            print(f"Next hop {next_hop} not connected, queing for later")
            self.queue_offline_message(message)
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

    def queue_offline_message(self, message):
        """
        Queues offline message and stores in the message store 

        PSEUDOCODE:
            store message in database
            start a thread to retry sending message (through retry function)
            store the thread in the retry dictinary 
        """
        self.message_store.store_offline_message(message)

        # timer = threading.Timer(1.0, self.retry_sending_message, [message.message_id])
        # timer.start()
        # self.retry_scheduler[message.message_id] = timer

    # def retry_sending_message(self, message_id):
    #     """
    #     PSEUDOCODE:
    #         set a delay and retry_count limit
    #         get stored message through message id
    #         call route_message function
    #         if success then print success message
    #         else increment retry_count 
    #         if retry_count limit is reached then stop sending messages for now
    #         else retry sending the message
    #     """
    #     delay = 2.0
    #     retry_count_limit = 10

    #     message = self.message_store.get_message_by_id(message_id)
        
    #     if not message:
    #         print(f"Message {message_id} not found for retry")
    #         return
        
    #     target = message.target_user_id
    #     next_hop = self.router.routing_graph.get(target)
        
    #     success = False
    #     if next_hop and next_hop in self.connections:
    #         message.add_hop(self.peer_id)
    #         self.connections[next_hop].queue_message(message)
    #         print(f"Successfully sent queued message to {target} via {next_hop}")
    #         success = True
    #     elif target in self.connections:
    #         message.add_hop(self.peer_id)
    #         self.connections[target].queue_message(message)
    #         print(f"Successfully sent queued message directly to {target}")
    #         success = True
        
    #     if success:
    #         self.message_store.delete_message_by_id(message_id)
    #         if message_id in self.retry_scheduler:
    #             self.retry_scheduler.pop(message_id, None)
    #     else:
    #         retry_count = self.message_store.increment_retry_count(message_id)
    #         print(f"Retry attempt {retry_count} failed for message to {target}")

    #         if retry_count >= retry_count_limit:
    #             print(f"Retry limit reached for message to {target}, stopping retries")
    #             self.message_store.delete_message_by_id(message_id)
    #             if message_id in self.retry_scheduler:
    #                 self.retry_scheduler.pop(message_id, None)
    #         else:
    #             timer = threading.Timer(delay, self.retry_sending_message, [message_id])
    #             timer.start()
    #             self.retry_scheduler[message_id] = timer

    def deliver_queued_messages(self, target_peer):
        messages = self.message_store.get_pending_messages(target_peer)

        if messages:
            for i, message in enumerate(messages):
                self.send_message(message)
                print(f"Sent {i+1} queued message")

            print("Sent all previously queued messages")

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
        Removes connection and peer from memory and from router
        """
        self.sel.unregister(sock)
        sock.close()
        if connection.peer_id:
            # Remove from connections and router
            disconnected_peer = connection.peer_id
            self.connections.pop(disconnected_peer, None)
            self.router.remove_peer(disconnected_peer)
            
            # update routing graph
            self.router.update_routing_graph(self.known_peers)
            
            # share changes with all connected peers
            for existing_peer_id, existing_connection in self.connections.items():
                if existing_connection.is_handshake_complete:
                    network_update_message = Message(
                        peer_id=self.peer_id,
                        target_user_id=existing_peer_id,
                        message_type="NETWORK_UPDATE",
                        data={"peer_graph": {key: list(value) for key, value in self.router.peer_graph.items()}},
                        time_stamp=time.time()
                    )
                    existing_connection.queue_message(network_update_message)
            
        print(f"\nCleaned up connection {connection.address}")
   
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
