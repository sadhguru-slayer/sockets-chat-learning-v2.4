# Application Architecture & Scaling Plan

> **Note:** The application has successfully completed all 3 phases of horizontal scaling as described below. It now comfortably supports multiple WebSocket servers behind a load balancer using Redis for message routing and isolated business logic.

---

# Architecture Overview

After reviewing the initial architecture, the application was ~90% of the way to a horizontally scalable WebSocket system. The biggest missing piece was that the websocket server was doing too many responsibilities inside the socket connection itself.

Instead of adding lots of infrastructure, the application was scaled efficiently through **3 phases**.

---

# Previous Architecture & Problems

## Initial Architecture

```text
                Client
                   │
            FastAPI WebSocket
                   │
        ┌──────────┴───────────┐
        │                      │
   Database writes         Redis Pub/Sub
        │                      │
        └──────────────► redis_listener()
                               │
                        manager.send_to_user()
```

The system used Redis Pub/Sub, which is exactly what multiple socket servers need. However, the logic placement was the bottleneck.

## Problems Identified

### 1. Socket endpoint was huge
The websocket endpoint performed:
* authentication
* membership validation
* database writes
* editing messages
* deleting messages
* typing events
* presence
* redis publishing

All inside one file. That becomes difficult to scale because every websocket server was doing business logic.

### 2. Redis listener queried the database
Every published message caused:
```text
Redis -> redis_listener() -> Query DB -> find members -> publish user events
```
For every message, which wouldn't scale to large groups.

### 3. Two Redis hops
Current flow doubled Redis traffic:
```text
Socket -> Publish conversation -> redis_listener -> lookup members -> publish user1, user2, etc.
```

### 4. Business logic mixed with transport
The websocket layer shouldn't know message storage details.

---

# Completed Scaling Architecture

## Phase 1 (Biggest Win) - Introduce Services
*(Status: Completed)*

**Goal:** Extract business logic into service classes (highest impact, minimal infrastructure changes).

Instead of handling DB writes and validation inside the websocket, it routes to a `ChatService`.
```text
event -> service -> done
```

The websocket server became a dumb router. Logic was split into:
* `services/chat_service.py`
* `services/message_service.py`
* `services/presence_service.py`
* `services/conversation_service.py`

## Phase 2 (Make Redis the Router)
*(Status: Completed)*

**Goal:** Use Redis as the routing layer by maintaining conversation membership in Redis, eliminating per-message database lookups.

Publish directly to conversation channels (e.g., `conversation:15`). Every websocket server subscribes to `conversation:*`.
Conversation subscriptions are maintained in Redis, avoiding DB lookups on every message.

## Phase 3 (Multiple Socket Servers)
*(Status: Completed)*

**Goal:** Scale horizontally by running multiple FastAPI WebSocket instances behind a load balancer, with each instance only managing its local connections while Redis fans out events.

The final architecture achieved:
```text
             Load Balancer
            /      |      \
           /       |       \
      Socket1  Socket2  Socket3
           │       │       │
           └───────┼───────┘
                   │
                 Redis
                   │
             PostgreSQL
```

Each server keeps only local websocket connections.
Message flow:
```text
User1 -> Redis -> All servers receive -> Each server sends only to local users
```
This scales almost linearly.

---

# Core Components

## ConnectionManager
The connection manager maps local active users to their websocket connections (`local_connections`).

## Presence
Presence implementation is highly scalable using a Redis Set for `online_users` and `presence_watchers:user_id` pattern.

## Redis Listener
The listener is isolated in its own module:
* `subscriber.py`: Only listens to Redis events.
* `handlers.py`: Dispatches events.
* `manager.send_to_user()`: The only websocket interaction point.

---

# Final Architecture Diagram

```text
                Client
                  │
                  ▼
           WebSocket Server
                  │
          Event Dispatcher
                  │
        ┌─────────┴─────────┐
        │                   │
 ChatService         PresenceService
        │                   │
        └─────────┬─────────┘
                  │
             PostgreSQL
                  │
                  ▼
               Redis
                  │
      ┌───────────┼───────────┐
      │           │           │
 Socket #1   Socket #2   Socket #3
      │           │           │
 Local users  Local users  Local users
```

This approach minimized refactoring while establishing an architecture that comfortably supports tens of thousands of concurrent WebSocket connections across multiple instances.
