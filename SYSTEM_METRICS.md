# System Metrics: Sockets Chat Learning v2.4

This document summarizes the architectural characteristics, scalability expectations, computational complexity, estimated resource usage, and design trade-offs of the **Sockets Chat Learning v2.4** project.

> [!NOTE]
> All performance numbers and capacity estimates are architectural estimates based on the current implementation and common FastAPI + Redis + PostgreSQL deployments. Actual throughput depends on hardware, operating system tuning, network bandwidth, Redis configuration, PostgreSQL configuration, and deployment topology.

---

## Technology Stack

### Backend
* **FastAPI** (Python 3, AsyncIO)
* **SQLAlchemy** (Async)
* **PostgreSQL**

### Real-Time Communication
* **WebSockets**
* **Redis Pub/Sub**

### Caching
* **Redis**
  * Conversation Membership Cache
  * User Conversation Cache
  * Presence Cache

---

## Architecture Highlights

* **Stateless FastAPI WebSocket servers** to allow independent scaling.
* **Redis Pub/Sub** acting as a distributed message bus across nodes.
* **PostgreSQL** utilized as the absolute source of truth for persistent data.
* **Local in-memory connection routing** to optimize packet dispatching.
* **Redis-backed caches** dedicated to tracking conversation membership and user presence.
* **Multi-device connection support** allowing seamless multi-session synchronization per user.
* **Horizontal scaling ready** design from inception.

---

## Scalability & Capacity

The current architecture natively supports horizontal WebSocket scaling via multiple socket server instances, distributed message routing, local connection management, and globally synced Redis caches.

### Estimated Capacity (Per Socket Server)

| Metric | Estimated Capacity |
| :--- | :--- |
| **Concurrent WebSocket Connections** | 20,000 – 40,000 |
| **Active Conversations** | 500,000+ |
| **Redis Operations** | 100K+ ops/sec |
| **Messages** | Limited primarily by PostgreSQL storage capacity |

### Multi-Server Deployment Scaling

| Socket Servers | Estimated Concurrent Connections |
| :---: | :--- |
| **1** | 20K – 40K |
| **3** | 60K – 120K |
| **5** | 100K – 200K |
| **10** | 200K – 400K |

*Scaling is linearly achieved by adding additional WebSocket server nodes behind a load balancer.*

---

## Routing & Performance Characteristics

### Database and Cache Overhead
* **Database queries required during message routing:** `0`
* **Conversation membership lookup:** Redis O(1)
* **Local routing:** In-Memory O(1)
* **Redis publishes per message:** `1`
* **Database writes per message:** `1 INSERT`

### Operation Latencies
*The following approximate operation latencies are observed on a local development environment (not official benchmarks):*

| Operation | Estimated Time |
| :--- | :--- |
| WebSocket Authentication | 3–5 ms |
| Redis Publish | < 1 ms |
| Redis Set Lookup | < 1 ms |
| Local Conversation Routing | < 1 ms |
| PostgreSQL Message Insert | 4–10 ms |
| Presence Update | < 2 ms |
| **End-to-End Message Delivery** | **10–30 ms** |

---

## Memory Estimates

### Redis Caches

* **Conversation Membership Cache**
  * *Basis:* 100,000 conversations, average of 5 members per conversation.
  * *Approximate Memory:* **30–40 MB**
* **Presence Cache**
  * *Basis:* 100,000 online users.
  * *Approximate Memory:* **6–10 MB**
* **User Conversation Cache**
  * *Basis:* 100,000 users, average of 20 conversations per user.
  * *Approximate Memory:* **120–150 MB**
* **Total Redis Cache Allocation**
  * *Approximate Total:* **150–220 MB**

### Connection Manager (App Server Memory)
* *Basis:* 20,000 active WebSocket connections on a single server instance.
* *Approximate Memory:* **120–200 MB**

---

## Computational Complexity

| Operation | Complexity | Description / Variables |
| :--- | :---: | :--- |
| **Connect WebSocket** | O(1) | Initial handshake and context registration |
| **Disconnect WebSocket** | O(k) | Where k is the number of conversations and watched users associated with the connection |
| **Authenticate Connection** | O(1) | Token verification and user context parsing |
| **Join Conversation** | O(1) | Cache append operations |
| **Leave Conversation** | O(1) | Cache eviction operations |
| **Get Conversation Members** | O(1) | Direct Redis lookup |
| **Get User Conversations** | O(1) | Direct Redis lookup |
| **Presence Lookup** | O(1) | Fast key-value status check |
| **Local Conversation Lookup**| O(1) | Memory dictionary verification |
| **Local Message Routing** | O(local connected members) | Limited strictly to active local connections |
| **Redis Publish** | O(1) | Pub/Sub message dispatching |
| **PostgreSQL Message Insert**| O(1) | Appending message payload to historical logs |

---

## Design Trade-offs

### 1. Redis Memory vs. Database Queries
Additional Redis memory is intentionally consumed to store real-time states and relationships, entirely eliminating database read queries from the active message delivery path.
* **Result:** Blazing fast routing, heavily reduced database load, and robust horizontal scalability.

### 2. Local Routing vs. Redis Fan-out
Instead of forcing Redis to publish messages individually to every single connected client device, each WebSocket server node listens to a broad channel and performs sub-routing exclusively for users physically connected to *that specific server node*.
* **Result:** Drastically reduced Redis traffic, minimal network overhead, and clean horizontal scaling.

### 3. PostgreSQL as the Source of Truth
Redis is treated strictly as an ephemeral caching, presence, and transient routing engine. Persistent data records (including messages and conversation schemas) reside safely in PostgreSQL.
* **Result:** Guaranteed reliable long-term persistence, easily recoverable Redis caches, and highly simplified cache rebuilding strategies.

### 4. In-Memory Connection Manager
Each individual WebSocket server node handles and tracks only its own active client sockets locally.
* **Result:** Zero distributed locking overhead, lightning-fast local lookups, constant-time internal routing, and predictable linear scaling.

---

## Roadmap & Features

### Implemented
* [x] JWT Authentication
* [x] Async FastAPI Foundations
* [x] Redis Pub/Sub Distributed Messaging
* [x] PostgreSQL Persistence Layers
* [x] Full-Duplex WebSocket Communication
* [x] Conversation Membership Cache
* [x] User Conversation Cache
* [x] Presence Tracking & Fluid Typing Indicators
* [x] Multi-device Sessions Synchronization
* [x] Local In-Memory Fast Routing
* [x] Horizontal Scaling Ready Architecture
* [x] Automatic Connection Cleanup & Redis Cache Synchronization

### Planned
* [ ] Heartbeat Mechanics (Ping/Pong) & Auto Reconnection
* [ ] Message Delivery Acknowledgements & Read Receipts
* [ ] Prometheus Integration & Comprehensive Metrics Collection
* [ ] Distributed Tracing & High-Availability Health Checks
* [ ] API & WebSocket Rate Limiting
* [ ] Rigorous Automated Load Testing
* [ ] Native Redis Cluster Support

---

## Architectural Goals

The primary objective of this project is to explore and implement a **production-grade WebSocket architecture** rather than simply build user-facing chat features. 

Key architectural learning focal areas include:
1. Distributed WebSocket Systems
2. Redis-Based Routing Layouts
3. Cache-Aside and Real-Time Write Strategies
4. Linear Horizontal Scaling Mechanics
5. High-Throughput Presence Systems
6. Edge-Case Connection Lifecycle Management
7. Reconciling Local vs. Distributed State
8. High-Performance Real-Time System Design
