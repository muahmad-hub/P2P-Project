from message import Message


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