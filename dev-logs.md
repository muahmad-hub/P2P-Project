# Dev Logs
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
