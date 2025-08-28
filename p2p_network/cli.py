import time
from message import Message

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
            queue - shows queued messages
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
        
        if target_peer_id not in self.peer.known_peers:
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
            print(f"Message queued for {target_peer_id} (will retry when peer comes online)")

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

    def cmd_queued_messages(self, args):
        pending = self.peer.message_store.get_all_pending_messages()
        
        print("\n___Queued Messages___")
        if not pending:
            print("No pending messages.")
            return

        print(f"{len(pending)} message(s) in queue:")
        for message in pending:
            target = message.target_user_id
            content = message.data.get('content', 'N/A')
            print(f"- To: {target}")
            print(f"  Content: {content}")
            print(f"  Message ID: {message.message_id}")

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
            'queue': self.cmd_queued_messages,
        }
        
        if command in commands:
            commands[command](args)
        else:
            print(f"Unknown command: '{command}'. Type 'help' for available commands.")

    def show_prompt(self):
        """Show the command prompt"""
        print(f"\n[{self.peer.peer_id}]> ", end="", flush=True)

    def run(self):
        """
        Main CLI loop
        """
        print(f"___P2P Network CLI___")
        print(f"Peer ID: {self.peer.peer_id}")
        print(f"Listening on: {self.peer.host}:{self.peer.port}")
        print("Type 'help' for available commands.")
        
        # Show initial prompt
        self.show_prompt()
        
        while self.running:
            try:
                user_input = input()
                if user_input.strip():
                    self.parse_command(user_input)
                if self.running:
                    self.show_prompt()
            except KeyboardInterrupt:
                print("\nReceived Ctrl+C, shutting down...")
                self.cmd_quit([])
                break

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
        
        if target_peer_id not in self.peer.known_peers:
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
            print(f"Message queued for {target_peer_id} (will retry when peer comes online)")

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

    def cmd_queued_messages(self, args):
        pending = self.peer.message_store.get_all_pending_messages()

        print("\n___Queued Messages___")
        if not pending:
            print("No pending messages.")
            return

        print(f"{len(pending)} message(s) in queue:")
        for message in pending:
            target = message.target_user_id
            content = message.data.get('content')
            retry = getattr(message, 'retry_count', 0)
            created = getattr(message, 'created_at', 'Unknown')
            
            print(f"- To: {target}")
            print(f"  Content: {content}...")
            print(f"  Retry: {retry}, Queued: {created}")

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
            'queue': self.cmd_queued_messages,
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
        
        self.show_prompt()
        
        while self.running:
            try:
                user_input = input()
                if user_input.strip():
                    self.parse_command(user_input)
                if self.running:
                    self.show_prompt()
            except KeyboardInterrupt:
                print("\nReceived Ctrl+C, shutting down...")
                self.cmd_quit([])
                break

    def show_prompt(self):
        """Show the command prompt"""
        print(f"\n[{self.peer.peer_id}]> ", end="", flush=True)