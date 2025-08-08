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

