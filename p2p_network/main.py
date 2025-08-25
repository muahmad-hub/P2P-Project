import sys
import os
from peer import Peer
from cli import cli_interface


def main():
    # Create directories if they don't exist
    os.makedirs("ids", exist_ok=True)
    
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