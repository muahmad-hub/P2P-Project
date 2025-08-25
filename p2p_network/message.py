import json
import uuid
import time


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