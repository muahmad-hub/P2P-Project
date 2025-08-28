# P2P Network - Distributed Messaging System

## Table of Contents
- [Motivation & Purpose](#motivation--purpose)
- [Demo](#demo)
- [Quick Overview](#quick-overview)
- [Key Features](#key-features)
- [Challenges](#challenges-faced)
- [What I learned](#what-i-learned)
## Motivation & Purpose
In 2005, a devastating earthquake struck northern Pakistan, my country of origin, killing over 80,000 people and leaving millions homeless. Rescue operations were slowed by the lack of reliable communication. Relief workers struggled to coordinate, and resources didn’t always reach where they were needed in time.

That memory stayed with me. It made me wonder: what if people in disaster-prone areas could still connect even if central infrastructure failed?

This project is a small step toward that idea. It is nowhere near disaster-ready—it’s a simple proof-of-concept—but it gave me hands-on experience with distributed systems, fault tolerance, and resilience. More importantly, it showed me how even small-scale technical experiments can connect to real-world humanitarian challenges.
## Demo
> **Demo:** https://youtu.be/VmvUyCWIB3w
## Quick Overview
This is a peer-to-peer (P2P) distributed messaging system that allows nodes to communicate directly without relying on a central server.
- **Network Type**: Partial mesh topology with automatic peer discovery and dynamic routing
- **Core Tech**: Python sockets, SQLite for offline message storage, BFS routing algorithm, async I/O with selectors
- **Message Delivery**: Stores messages in queues and sends them with retry mechanisms for reliable delivery
- **Interface**: Command-line interface (CLI) for user interaction
>For more details: [Dev logs & Learning Journal](docs/dev-logs.md)
## Key Features:
### Core Networking
- **Direct P2P Communication**: Each peer acts as a client, server, and router at the same time.
- **Automatic Peer Discovery**: Peers share peer lists to expand network knowledge.
- **Multi-hop Routing**: Messages can be routed through multiple peers using BFS to find the shortest available path.
- **Connection Management**: Efficient handling of multiple connections using non-blocking I/O.
### Messaging system
- **Reliable Delivery**: Messages are first queued before being sent in chunks.
- **Offline Message Queue**: If a peer disconnects, outgoing messages are stored in SQLite until they reconnect.
- **Automatic Retry**: Retries every 30 seconds; deferred if delivery fails multiple times.
- **Loop Prevention**: Uses hop limits and “seen message” tracking to stop infinite forwarding or message getting stuck in loops.
### Network Resilience
- **Dynamic Routing**: Routing graphs automatically adapt for each peer as other peers join or leave.
- **Network Awareness**: Each peer maintains an updated adjacency list of the network.
### User Interface
- **CLI Interface:** Interactive command line interface for operations
## Challenges Faced
- **Managing Complexity**
    - At first, I underestimated how many moving parts were happening at once. I switched to a step-by-step method: pseudocode for tricky parts, modular testing, and class-by-class development.
- **Routing & BFS Bugs**
    - My first routing implementation didn’t forward messages correctly. I rebuilt the routing graph logic and debugged message system step by step until multi-hop worked consistently.
- **Persistent Peer Identity**
    - Originally, peers got new IDs every time they reconnected, which broke offline delivery. I fixed this by assigning each peer a stored ID or generating one on first-time setup.
- **Testing a Distributed System**
    - Debugging across multiple nodes was far harder than debugging a single program. I built test scenarios and ran them repeatedly to fix bugs and verify stability.
## What I Learned
- **Distributed systems are messy in practice**: handling half-messages, retries, and failures required more thought than I expected.
- **Resilience requires deliberate design**: I learned that features I thought were “nice extras” (like offline queuing and persistent IDs) were actually essential. Without them, the system lost messages or mis-identified peers, making it unreliable.
- **Debugging skills:** I learned to design specific tests, isolate components through modular testing, and trace failures step by step to identify and fix bugs.