from collections import deque


class Router:
    def __init__(self, peer_id):
        # Dictionary of the which peer to route to depending on the target peer
        self.routing_graph = {}
        # Adjacency matrix of all the connected peer of each peer
        self.peer_graph = {}
        self.peer_id = peer_id

    def BFS_path_finding(self, target_peer_id):
        """
        Breadth-first search used to find the shortest path (with the smallest hops)

        PSEUDOCODE:
            var start node
            add start node to frontier


            while frontier is not empty
                pop node and path from frontier (BFS is FIFO)
                if node was already explored then skip loop
                is the node the target node, if yes then return else keep going
                find neighbours
                append neirbours to the frontier along with the updated path
        """

        # Handling edge cases
        if target_peer_id == self.peer_id:
            return [self.peer_id]
        if target_peer_id not in self.peer_graph:
            return None
        
        frontier = deque()
        explored_nodes = set()

        start_node = self.peer_id
        frontier.append((start_node, [start_node]))

        while frontier:
            current_node, current_path = frontier.popleft()
            if current_node in explored_nodes:
                continue
            explored_nodes.add(current_node)
            if current_node == target_peer_id:
                return current_path
            neighbors = self.peer_graph.get(current_node, set())
            for neighbor in neighbors:
                if neighbor not in explored_nodes:
                    frontier.append((neighbor, current_path + [neighbor]))
        return None
    
    def get_next_hop(self, current_node, path, update_path=False):
        try:
            index = path.index(current_node)
            if index + 1 >= len(path):
                return None
            next_node = path[index + 1]

            if update_path:
                new_path = path[:index] + path[index+1:]
                return next_node, new_path

            return next_node
        except:
            return None

    def update_routing_graph(self, known_peers):
        """
        Precomputes the routing procedure using BFS

        PSEUDOCODE:
            function
                loop over all known peers
                    if peer is itself then skip loop
                    run the bfs
                    get the next hop from start node
                    update the table as this 'to get to': 'send to'

        """
        self.routing_graph = {}
        for target_peer in known_peers:
            if target_peer == self.peer_id:
                continue
            path = self.BFS_path_finding(target_peer)
            if path:
                next_hop = self.get_next_hop(self.peer_id, path)
                if next_hop:
                    self.routing_graph[target_peer] = next_hop

    def update_peer_graph(self, other_peer_id):
        if self.peer_id not in self.peer_graph:
            self.peer_graph[self.peer_id] = set()
        if other_peer_id not in self.peer_graph:
            self.peer_graph[other_peer_id] = set()

        self.peer_graph[self.peer_id].add(other_peer_id)
        self.peer_graph[other_peer_id].add(self.peer_id)
             
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