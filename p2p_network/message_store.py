import sqlite3
import json
import time
import os
from message import Message


class MessageStore:
    """
    Stores offline messages to send to users who aren't currently connected to the network

    PSEUDOCODE:
        Class MessageStore

            creates a message database for a peer
            Needs a message table to store relevant message data
            Add a schedule table, connect it as a one to one field to the message table
            Schedule table should store:
                - Last tried timestamp
                - Number of times it was tried to send
                - Expiry timestamp (so that the message isn't being sent forever)

            Function inititialize database:
                create the two necessary tables

            Function store_offline_message(message):
                store the message in the database
                add expiry timestamp of 7 days from now

            Function get_pending_messages(target user):
                delete any messages whose expirty date has exceeded
                search the database where intended user is the target user
    """
    def __init__(self, peer_id):
        self.peer_id = peer_id
        # Each peer has their own database
        self.database_path = f"database/{self.peer_id}_messages.db"

        os.makedirs("database", exist_ok=True)

        self.initialize_database()

    def initialize_database(self):
        connection = sqlite3.connect(self.database_path)
        cursor = connection.cursor()

        cursor.execute("""
        CREATE TABLE IF NOT EXISTS offline_messages (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            peer_id TEXT NOT NULL,
            target_user_id TEXT NOT NULL,
            message_type TEXT NOT NULL,
            data TEXT NOT NULL,
            time_stamp DATETIME,
            message_id TEXT NOT NULL,
            hop_count INTEGER,
            path TEXT
            )
        """)

        cursor.execute("""
        CREATE TABLE IF NOT EXISTS schedule_messages (
            message_id TEXT PRIMARY KEY,
            last_tried DATETIME,
            retry_count INTEGER DEFAULT 0,
            expiry_time DATETIME, 
            FOREIGN KEY(message_id) REFERENCES offline_messages(message_id) ON DELETE CASCADE
            )
        """)

        connection.commit()
        connection.close()

    def store_offline_message(self, message):
        connection = sqlite3.connect(self.database_path)
        cursor = connection.cursor()

        # Expiry time is set to 7 days from when message was stored in database
        expiry_time = time.time() + 604800

        cursor.execute("""
        INSERT INTO offline_messages
        (peer_id, target_user_id, message_type, data, time_stamp, message_id, hop_count, path) 
        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            message.peer_id,
            message.target_user_id,
            message.message_type,
            json.dumps(message.data),
            message.time_stamp,
            message.message_id,
            message.hop_count,
            json.dumps(message.path)
        ))

        cursor.execute("""
        INSERT INTO schedule_messages
        (message_id, last_tried, retry_count, expiry_time)
        VALUES (?, ?, ?, ?)
        """, (
            message.message_id,
            None,
            0,
            expiry_time
        ))

        connection.commit()
        connection.close()

    def get_pending_messages(self, target_peer):
        connection = sqlite3.connect(self.database_path)
        cursor = connection.cursor()

        self.delete_expired_messages()

        # Query to retrieve all messages where the target is the target_peer and message hasn't expired yet
        cursor.execute("""
        SELECT o.id, o.peer_id, o.target_user_id, o.message_type, o.data, 
            o.time_stamp, o.message_id, o.hop_count, o.path,
            s.last_tried, s.retry_count, s.expiry_time
        FROM offline_messages o
        JOIN schedule_messages s ON o.message_id = s.message_id
        WHERE o.target_user_id = ? AND s.expiry_time > ?
        """, (target_peer, time.time()))

        result_raw = cursor.fetchall()
        connection.close()

        messages = []
        for result in result_raw:
            messages.append(self.data_to_message_class(result))

        return messages

    def get_all_pending_messages(self):
        connection = sqlite3.connect()
        cursor = connection.cursor()

        cursor.execute("""
        SELECT o.id, o.peer_id, o.target_user_id, o.message_type, o.data, 
            o.time_stamp, o.message_id, o.hop_count, o.path,
            s.last_tried, s.retry_count, s.expiry_time
        FROM offline_messages o
        JOIN schedule_messages s ON o.message_id = s.message_id
        WHERE s.expiry_time > ?
        """, (time.time()))

        result_raw = cursor.fetchall()
        connection.close()

        messages = []
        for result in result_raw:
            messages.append(self.data_to_message_class(result))

        return messages

    def get_message_by_id(self, message_id):
        connection = sqlite3.connect(self.database_path)
        cursor = connection.cursor()

        self.delete_expired_messages()

        # Query to retrieve all messages where the target is the target_peer and message hasn't expired yet
        cursor.execute("""
        SELECT o.id, o.peer_id, o.target_user_id, o.message_type, o.data, 
            o.time_stamp, o.message_id, o.hop_count, o.path,
            s.last_tried, s.retry_count, s.expiry_time
        FROM offline_messages o
        JOIN schedule_messages s ON o.message_id = s.message_id
        WHERE o.message_id = ? AND s.expiry_time > ?
        """, (message_id, time.time()))

        result_raw = cursor.fetchone()
        connection.close()
        
        if result_raw:
            result = self.data_to_message_class(result_raw)
            return result   
        return None     

    def delete_expired_messages(self):
        """
        Deletes all the expired messages in the database
        """
        connection = sqlite3.connect(self.database_path)
        cursor = connection.cursor()

        cursor.execute("""
        DELETE FROM offline_messages
        WHERE message_id IN (
            SELECT message_id FROM schedule_messages WHERE expiry_time <= ?
        )
        """, (time.time(),))

        connection.commit()
        connection.close()
        
    def delete_message_by_id(self, message_id):
        connection = sqlite3.connect(self.database_path)
        cursor = connection.cursor()

        cursor.execute("""
        DELETE FROM offline_messages 
        WHERE message_id = ?
        """, (message_id,))

        connection.commit()
        connection.close()

    def increment_retry_count(self, message_id):
        connection = sqlite3.connect(self.database_path)
        cursor = connection.cursor()
        
        # Updates both retry_count and last_tried timestamp
        cursor.execute("""
        UPDATE schedule_messages 
        SET retry_count = retry_count + 1, 
            last_tried = ?
        WHERE message_id = ?
        """, (time.time(), message_id))

        # Gets the new retry count value
        cursor.execute("""
        SELECT retry_count 
        FROM schedule_messages 
        WHERE message_id = ?
        """, (message_id,))
        
        result = cursor.fetchone()
        retry_count = result[0] if result else 0

        connection.commit()
        connection.close()

        return retry_count
            
    def data_to_message_class(self, message_data):
        """
        Converts the raw message data from the database into a message class
        """
        if message_data:
            message = Message(
                peer_id=message_data[1],
                target_user_id=message_data[2],
                message_type=message_data[3],
                data=json.loads(message_data[4]),
                time_stamp=message_data[5]
            )
            message.message_id = message_data[6]
            message.hop_count = message_data[7]
            message.path = json.loads(message_data[8])

            return message
        
        return None