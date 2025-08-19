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