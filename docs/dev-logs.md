# Dev Logs & Learning Journal
## Date: August 5
### Notes
- A socket is a communication endpoint, which means it is where a message is sent and received on a device
- A socket is made up of three things:
    - IP address: this is the IP address of the device that is being communicated with
    - Port Number: this is where on that device this message will be sent
    - Protocol: this specifies the type of protocol that will be used for the communication. 
        - TCP is most likely the best option as it will break down a message into packets. The advantage of this protocol is that it ensures the packets are reordered and in correct order when the client receives the data and incase a packet is lost, TCP will resend it
- A TCP server will need a *listening* socket and to create that:
    - You first need to create a socket object, since it supports the context manager type you can create it using a `with` statement
    - You can use the `socket.SOCK_STREAM` to specify the TCP protocol
    - Once the object is created you need to bind the socket to the IP address and Port number using `.bind()`. This is so that the socket knows where it will receive the message from
    - Now the socket should listen for connection requests using `.listen()`
    - When a connection is requested the `.accept()` method should be called. This creates a new socket object, so that the listening socket and the communcation socket are kept sepreate. 
        - This method blocks execution of the server untill a client connects (this is why the terminal might seem to hang)
        - It returns the socket object and the adress of the client as a tuple of (host, port) 
    - Then in an infinite loop the the `.recv()` method is called, which receives data from client. This is a blocking call and so it pauses the server processes untill a message is received. This helps in finding out when a user disconnects as disconnecting will send an empty byte and it can be checked conditionally whether an empty byte was passed, at which point the connection is broken. However if the user does send data, it is echoed back using `.sendall()`
    - The `.connect()` method in the client code intitiates the TCP three way handshake
        - The client sends a SYN packet to the server
        - The server sends back a SYN-ACK packet to the client
        - The client sends a final ACK packet to the client
## Date: August 6
### Notes
- Echo server has its limitations as it can only connect one client to the server and the `.recv()` and `.sned()` methods don't gurantee that all the data will be sent
- To solve this problem the `selectors` module can be used which offers high level and efficient I/O multiplexing
    - A selector is like a waitress in a restaurant. In a similar way that a waitress would keep track of which table is ready to order or receive food, a selector tells the server which socket is ready to read or write etc...
- Key aspects of multi-connection server:
    - Non-blocking sockets are needed. Since we are trying to connect multiple clients. It would be very ineffecient if the socket hangs for a single operation. Hence the `lsock.setblocking(False)` is used.
    - The listening socket is registered with the selector object to be monitored for `selectors.EVENT_READ`. The selector also allows to store information in the `data`.
    - An event loop is also added. An infinite loop is used in which a socket is searched for using `sel.select(timeout=None)`. This method blocks untill a socket is ready to read or write and it returns a list of tuple of (key, mask)
    - `key` is a data container that contains information realted to the socket, for example `key.fileobj` is the socket object, and `key.data` contains the custom data related to the socket. `mask` is a bit map flag which tells about the event that occured at the file object (such as EVENT_READ and EVENT_WRITE) 
    - If `key.data` is None, it means a new connection is being requested and so the `accept_wrapper()` function is called
        - `accept_wraepr()` function accepts the new socket, sets its blocking to False so it doesnt hang the server and registers the socket with the selector. Data related to the address, input buffer and output buffer is added to the selector too
    - Else if `key.data` is not None, it means a socket either wants to read or write and hence the `service_connection()` function is called
        - `service_connection()` function has parameter mask to check whether it is a read or write request.
        - If a read request is made and there is more data to read, the received data is added to the output buffer. Else if all the data is read, the socket is unregistered from the selector and closed
        - If a write request is made and there is data in the output buffer, it is sent across the socket.
    - The client side works similar to the server side but does have slight differences.
    - The client stores custom data when it connects. The data includes:
        - Connection id
        - Total length of the message that is sent
        - Total length of the message recieved
        - The messages itself
        - The output buffer

## Date: August 18
### Notes:
- For a multi connection server, you can keep one main listening socket. This socket is responsible for finding and receiving new connection requests from clients.
- Its `data` attribute can be set to `None` when the listening socket is created so that it can be distinguished when a request is received from a client and when from the listening socket
- For servicing a connection, you don't need to read the data in a loop untill of it is read for a non-blocking socket. This is becasue the OS will notify if there is more data that needs to be read
### What I did
- Started creating the bases for the peer-to-peer networking
- Created a `Members` class which is responsible for everything related to the Peer: it handles creation of the listening socket, accepting new connections and servicing the connections
    - `create_listening_socket()` creates a non-blocking listening socket that is able to service 5 connections at once. 'Data' is set to "LISTEN" to allow the server to differentiate between a new connection request and a client (other peer) request
    - `start_listening()` runs the loop and services a request accordingly
    - `start_server()` runs the listening sockets in a thread for asynchronous processing. Daemon is set to True so that threading terminates once main program stops
- For scalability instead of just using `types.SimpleNameSpace` or a dictionary, I decided to use a dedicated class to store all the information
- Also Implemented `SO_REUSEADDR` to prevent "Address already in use" errors during development iterations—critical for rapid testing cycles.

## Date: August 19
- To fully create a P2P network, each peer/member would need to store a peer list which contains all the peer known by that specific member fo the network.
- This list can be shared between members when they connect, allowing for easier discovery of peers
- A peer network list would also be needed to be generated as an adjacency matrix so that different peers can communicate with each other indirectly (if A is connected to B, C and D, but B is only connected to A, B can talk to both C and D through A.) This is a much more effecient network compared to each member connecting to every single user.
- Each peer will need to act as a mini-server, mini-client and even a router to help route a message to the network
- I would also need to use a search algorithm to search for the most optimised path when the message should be routed through. I would most likely be using BFS
- For effective routing, each peer would need to have a routing table. This will store which peer to send the message too according to the target user. This will be personalized to each member and will be computed beforehand for effeciency.
- The routing table will also be updated everytime there is an update to the connection

## Date: August 20
### Overall Plan
- I am planning on breaking the problem down into smaller chunks and completing each chunk at a time rather than completing all at once, as I was trying before.
- Previously, I was attempting to build the Message, Peer, and Router classes all at once, which was disorienting and often caused me to get stuck.
###  ✔ First step: Message Class
- My current plan is to first create the Message class.
    - The message class must be able to track:
        - The number of hops it has taken
        - The path it has traversed so far
### ✔ Second step: Router Class
- I need to implement the `Router` class that:
    - Maintains a network structure
    - Find shortest path between two nodes/peers via BFS
    - Generate routing tables for effeciency
    - Have a way to handle disconnected peers in the routing table and the network structure
    - Have a way to update new connections in the routing table and the network structure
### ✔ Third step: Complete the PeerConnection Class
- This class should be able to:
    - Handle connections with buffereing
    - Handle partial messages
    - Queue outbound messages
    - Detect complete messages
- I had already completed most of this in the previous days, so I only need to work on the queuing outbound messages part
### ✔ Fourth step: Complete Peer discovery and Handshake (Peer Class)
- This class should be able to:
    - Accept incoming connections on a listening socket
    - Initiate connections with peers
    - Perform handshake (application level) to exchange information between peers
    - Share a peer list
    - Handle connection failures
- I have also added a check in `handle_message()` method so that message don't just get stuck in loops
### BFS vs Dijkstra
- For routing between peers I decided to use BFS instead of Dijkstra algorithm because currently my edges are unweighted (Each hop has the same weight/cost) and so BFS would be much faster and quicker here.
- I might use Dijkstra later on if I add weighted edges (such as latency or bandwidth)
### BUG
- There seems to be a problem with the handshake request. The peer list is not being updated when teh results are shown
    - ```python 
        Handshake sent!
        Peer1 knows: []
        Peer2 knows: []
        ```
- I will try and fix this tommorow

## Date: August 21
### FIX
- In the test, I used raw socket (that wasn't managed by the selector) so when the handshake is sent to Peer1, Peer2's handshake is not received.
- `to_json` and `from_json` were not converting the hop count or the path
- In the test, I had `\\n` instead of `\n`, this may have caused the problem too
- I also need to implement the sending of peer list
- For sending message, my previous code had a bug
    - ```python
        # Previous approach
        def route_message(self, message):
            target = message.target_user_id
            send_to = self.router.routing_graph.get(target)
            if send_to is None:
                print("Unable to send message")
                return None
            self.send_message(message)

        # New approach
        # Sends message to the next hop
        def route_message(self, message):
            target = message.target_user_id
            next_hop = self.router.routing_graph.get(target)
            if next_hop is None:
                print(f"No route to {target}")
                return False
            
            if next_hop in self.connections:
                message.add_hop(self.peer_id)
                self.connections[next_hop].queue_message(message)
                return True
            else:
                print(f"Next hop {next_hop} not connected")
                return False
        ```
### ✔ Fifth Step: Error handling in Message class
- For network, errors can cause the whole network to crash and so are extremely important to be caught wherever they can
- Added the following to make sure there are no crashes if json is not parsed properly
    - ```python 
            try:
                data = json.loads(json_str)
            except json.JSONDecodeError:
                return None
        ```
- Added a check for all the required fields too in `from_json`
    - ```python 
        required_fields = ["peer_id", "target_user_id", "message_type", "data", "time_stamp", "message_id"]
        if not all(field in data for field in required_fields):
            return None
        ```
- Added a check for each message attribute to ensure data is not corrupted:
    - ```python
        if not isinstance(data["peer_id"], str): return None
        if not isinstance(data["target_user_id"], (str, type(None))): return None
        if not isinstance(data["message_type"], str): return None
        if not isinstance(data["data"], dict): return None
        if not isinstance(data["time_stamp"], (int, float)): return None
        if not isinstance(data["message_id"], str): return None
        if not isinstance(data.get("hop_count", 0), int): return None
        if not isinstance(data.get("path", []), list): return None
        ```
- I had previously already added a `seen_message` list in the peer class to prevent messages being sent in loops. I added an additiional check so that users don't change the message id and keep sending the messages infinitely
    - ```python
        if data.get("hop_count", 0) > 10:
        return None
        ```
### ✔ Sixth Step: Remove disconnected peers through Router class   
- Incase a peer disconnects, I need to add a method that will remove the peer from the peer graph, routing graph and connections.
    - ```python
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

        ```
### ✔ Seventh Step: Network error handling in PeerConnection class, enforce buffer size, and ensure clean up of unused connections
- `BlockingIOError` error is raised when a I/O operation is performed on a non-blocking socket that would normally block. 
    - When using `send()` this means that the OS send buffer is full and so can't write now. 
    - When  using `recv()` this means that no data is available yet
    - Both signal to try later
- `ConnectionResetError` happens when peer closes connection when data is being sent
- I added a seperate `send_buffered_data` method which handles these errors:
    - ```python 
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
        ```
- Set a maximum buffer size in the `PeerConnection` class to avoid memory exhaustion, network congestion, and latency
    - ```python
        # Handling maximum buffer size overflow
        if len(self.outbound_buffer) + len(message_bytes) > self.MAX_BUFFER_SIZE:
            print(f"Maximum buffer sized reached on outbound buffer for {self.address}")
            return False
        ```
### ✔ Testing current code:
### 🧪 First Test
- Tested basic connection first
 ```python
    if __name__ == "__main__":    
        print("___Test: Basic Connection___")
        
        # Create two peers
        peer1 = Peer("localhost", 8001)
        peer2 = Peer("localhost", 8002)
        
        peer1.start_server()
        peer2.start_server()
        
        print(f"Peer1 ID: {peer1.peer_id}")
        print(f"Peer2 ID: {peer2.peer_id}")
        
        time.sleep(0.5)
        
        success = peer2.connect_to_peer("localhost", 8001)
        if success:
            print("Connection initiated successfully")
        
        time.sleep(1)
        
        print(f"Peer1 known peers: {list(peer1.known_peers.keys())}")
        print(f"Peer2 known peers: {list(peer2.known_peers.keys())}")
```
### Failed Test:
 ```python 
    ___Test: Basic Connection___
    Listening socket created for member c22614c6
    Listening socket created for member 794dada3
    Peer1 ID: c22614c6
    Peer2 ID: 794dada3
    Failed to connect to localhost:8001
    Peer1 known peers: []
    Peer2 known peers: []
```
### Solution
- I ran the code in the debugger and when the `connect_ex()` method was used, it gave back `10035` instead of `0`. After searching up what the error code mean't, I learn't that this error is for windows which signals that the socket is not yet ready for the action. 
- So I added another condition to ignore this code:
- ```python
    if result != 0 and result != 10035:
        sock.close()
        print(f"Failed to connect to {host}:{port}")
        return False
    ```
- After these changes the handshake and connection did work
### Second Test
- Testing messages and routing
```python
    def test2():
        print("__Test 2: Message routing")
        
        # Create three peers for routing test
        peer1 = Peer("localhost", 8003)
        peer2 = Peer("localhost", 8004) 
        peer3 = Peer("localhost", 8005)
        
        # Start all servers
        peer1.start_server()
        peer2.start_server()
        peer3.start_server()
        
        print(f"Peer1 ID: {peer1.peer_id}")
        print(f"Peer2 ID: {peer2.peer_id}")
        print(f"Peer3 ID: {peer3.peer_id}")
        
        time.sleep(0.5)

        # Establishing network        
        peer1.connect_to_peer("localhost", 8004) 
        time.sleep(0.5)
        peer2.connect_to_peer("localhost", 8005)
        time.sleep(1.5)
        
        print("Network established")
        print(f"Peer1 knows: {list(peer1.known_peers.keys())}")
        print(f"Peer2 knows: {list(peer2.known_peers.keys())}")
        print(f"Peer3 knows: {list(peer3.known_peers.keys())}")
        
        # Test direct messages (peer1 to peer2)
        print("__Testing direct message___")
        direct_message = Message(
            peer_id=peer1.peer_id,
            target_user_id=peer2.peer_id,
            message_type="MESSAGE",
            data={"content": "Hello from peer1 to peer2!"},
            time_stamp=time.time()
        )
        peer1.send_message(direct_message)
        
        time.sleep(0.5)
        
        # Test routed message (peer1 to peer3 via peer2)
        print("___Testing routed message___")
        routed_message = Message(
            peer_id=peer1.peer_id,
            target_user_id=peer3.peer_id,
            message_type="MESSAGE",
            data={"content": "Hello from peer1 to peer3 via routing!"},
            time_stamp=time.time()
        )
        peer1.send_message(routed_message)
        
        time.sleep(0.5)
        
        return peer1, peer2, peer3
```
### Failed test:
- Direct messages between peer1 and peer2 were sent, but the message couldn't be routed through the peers
### Solution:
- Running the code in debugger showed that the error was coming due to the `self.router.routing_graph.get(target)` returning `None`. So I added another line to the testing code to see the known peers.
    ```python
    # Testing code
    print(f"Peer 1 knows: {peer1.known_peers.keys()}")
    print(f"Peer 2 knows: {peer2.known_peers.keys()}")
    print(f"Peer 3 knows: {peer3.known_peers.keys()}")

    # Output
    Peer 1 knows: dict_keys(['56337cbe'])
    Peer 2 knows: dict_keys(['4f3d67ab', 'f5a0e9d8'])
    Peer 3 knows: dict_keys(['56337cbe', '4f3d67ab'])
    ```
- This clarifies that Peer 1 is still not notified that Peer 3 exists and so couldn't route the message
- So I added the following changes to whever a handshake request is replied to:
    ```python
        for existing_peer_id, existing_connection in self.connections.items():
        if existing_peer_id != other_peer_id and existing_connection.is_handshake_complete:
            # Send the updated known_peers list to existing connections
            updated_peer_list = Message(
                peer_id=self.peer_id,
                target_user_id=existing_peer_id,
                message_type="PEER_LIST",
                data=self.known_peers,
            )
            existing_connection.queue_message(updated_peer_list)
        ```
- However, there still seems to be a routing problem

## Date: August 22
### Solution for yesterday's BUG
- I was successfully sending peer list to all the connected users when a new user connected. This mean't that peers knew which other peers exist, but they still don't know which peer is connected to which peer and hence don't have the full idea of the network structure. 
- This is what was causing the BFS to fail and not be able to route peers correctly
- So, I added a new message type called `NETWORK_UPDATE` and this new message is transmitted to the peer when they send a handshake and to all other conected peers too
    ```python
        updated_network = Message(
            peer_id=self.peer_id,
            target_user_id=existing_peer_id,
            message_type="NETWORK_UPDATE",
            data={"peer_graph": {key: list(value) for key, value in self.router.peer_graph.items()}},
            time_stamp=time.time()
        )
        existing_connection.queue_message(updated_network)
    ```
- After this change, the routing test did work
### ✔ Eigth Step: Adding CLI for user interface
- I implemented a new `cli_interface` class that provides a **command-line interface** for interacting with the P2P network
- This allows users to connect, send messages, view peer lists, check system status, show help commands and close the Peer all through the terminal
### Key features added:
- `parse_command()` takes raw user input, splits it into a command and arguments and executes the corresponding function
- `connect (host) (port)` connects to another peer
- `send (peer_id) (message)` sends a direct message to a peer
- `list` shows connected peers and known peers
- `status` displays system statistics (per ID, running status, routing, etc...)
- `help` list all commands
- `quit`/`exit` closes current peer

## Date: August 23
### ✔ Ninth Step: Adding message queuing for offline peers
- Incase a peer is not currently connected, I do want to have the option of storing the message on a database so that it can be sent later when the user comes back online
### Chosing sqlite3 vs PostgreSQL
- Although PostgreSQL offers stronger security, advanced features and better scalability, sqlite3 is more compact, portable and easier to integrate as an embedded database. Since my goal is to store messages locally for offline users, sqlite3 seems to be a better choice
### Choosing between 1 table vs 2 tables for storing offline messages
- As of now I have two types of data that I need to store in the database: the main message data and the schedule data associated with the message
- Using a single table really reduces the query complexities but it also hinders scalability. From my previous projects I have learn't that scalable code may be time consuming or complex for now but it is extremely helpful in the future when new features are added or code is extended
- Therefore, I am thinking of using a 2 table solution:
    - `offline_messages`: stores all the data releated to the message, eg. peer_id, target_peer, data...
    - `schedule_messages`: stores data realted to the message scheduling, eg. last_tried, retry_count, expiry_time...
### What I did
- I added a `MessageStore` class that handles storing offline messages with the following methods:
    - `initialize_database`: Initializes and creates the two tables in the database
    - `store_offline_message`: Stores the message that is forwarded as a paremeter in the database
    - `delete_expired_messages`: Delets any expired messages from the database.
    - `get_pending_messages`: Retrives messages still pending that where the receipent is the target user. It also calls the `delete_expired_messages` inside itself.
    - `get_message_by_id`: gets a specific message stored in the message store through the message id
    - `delete_message_by_id`: deletes a specific message in message store through the message id
    - `increment_retry_count`: increments the retry count by one and also updates the last_tried field in message store. Returns the new retry count at the end
- I added the following methods too the `Peer` class too:
    - `queue_offline_message`: it is called when the message can't be sent to the peer right now (as they are not connected yet). Stores the message in the message store
    - `retry_sending_message`: keeps sending message to disconnected user untill the retry count is reached
    - `deliver_queued_messages`: is called when a users handshake is received and checks if there are any queued messages that weren't sent to them when they disconnected
### Problem 1: Message type inconsistency
- I was storing message class in database as seperate pieces of data, and I was returning the data in the `get_message_by_id` and `get_pending_messages` methods instead of message class
### Solution:
- I decided to add a `data_to_message_class` method that converts the the raw data into a message class
### Problem 2: Peer ID regenerated
- I didn't think of this problem beforehand but everytime a peer is connects, regardless of wether they connect for first time or reconnect, they are given a new peer id. This causes a problem as the whole storing and queuing offline messages code that I wrote is based on the fact that each peer will have the same id whenever they reconnect
### Solution:
- I decided to store user peer id locally through the new `load_or_create_peer_id` method, which loads or creates a peer id. If the user is a first time user then a new file is created where their peer id is stored, else their peer id is retreived from the file which is stored locally
### Problem 3: showing Unknown Peer for offline messages
- While testing, when I would disconnect a peer and try to send them a message, the system wouldn't recognise the peer, which mean't that it wasn't in their known peers.
### Solution
- This part of the code was the proble,
```python
def cleanup_connection(self, connection, sock):
    """
    Removes connection and peer from memeory and from router
    """
    self.sel.unregister(sock)
    sock.close()
    if connection.peer_id:
        self.connections.pop(connection.peer_id, None)
        # This was the problem causing the isse
        self.known_peers.pop(connection.peer_id, None)
        self.router.remove_peer(connection.peer_id)
```
- `self.known_peers.pop(connection.peer_id, None)` removed the peer from known peers when they disconnected and hence the message couldn't be queued for later