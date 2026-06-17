# Minimal Scaling Architecture Improvements

This plan outlines how to address the 5 architectural improvements minimally, to ensure you can easily read and understand the changes. 

## Proposed Changes

### 1. Database Connection Leak
**Problem**: Keeping a database connection open for the entire lifetime of a WebSocket quickly exhausts the database connection pool.
**Fix**: 
- Remove the `db: db_session` dependency from `websocket_endpoint`.
- Use `async with SessionLocal() as db:` for authentication at connection time.
- Open short-lived sessions inside the event loop whenever a database action (like `MessageCreate`) is triggered.

#### [MODIFY] app/ws/sockets.py
- Import `SessionLocal` from `app.database`.
- Instantiate `SessionLocal()` using an async context manager during initial connection (to verify the token) and for processing incoming events that require DB interaction.

---

### 2. Startup Race Conditions & N+1 Queries
**Problem**: Multiple workers trigger `sync_all` at startup, causing DB contention. `sync_all` performs N+1 queries.
**Fix**:
- Add a distributed lock in `main.py` using Redis `SET NX` so only one worker process triggers the sync.
- Update `sync_all` to execute a single bulk query to fetch all participants, grouping them in memory rather than querying the DB in a loop.

#### [MODIFY] app/main.py
- Wrap the `sync_all` call with a Redis lock: `await r.set("startup_sync_lock", "1", nx=True, ex=60)`.

#### [MODIFY] app/services/conversation_cache.py
- Update `sync_all` to fetch all `ConversationParticipants` via a single SQL query and populate Redis to fix the N+1 query issue.

---

### 3. Redis Memory Leak: Stale Presence Watchers
**Problem**: Users who disconnect abruptly leave behind their user IDs in other users' `presence_watchers` Redis sets, causing memory leaks.
**Fix**:
- Track `watched_users` as a Python `set` locally on the `Connection` dataclass.
- Clean up these watchers in Redis when the connection drops in `manager.disconnect`.

#### [MODIFY] app/ws/manager.py
- Add `watched_users: set[int] = field(default_factory=set)` to the `Connection` dataclass.
- Inside `disconnect()`, iterate over `disconnected.watched_users` and execute `await PresenceCache.unwatch(user_id, target_user_id)`.

#### [MODIFY] app/ws/sockets.py
- When `event == "conversation.joined"`, add `other_user_id` to the connection's local `watched_users` set.

---

### 4. Missing Redis Pipelining
**Problem**: Executing multiple consecutive `await r.sadd(...)` calls incurs network delays.
**Fix**: 
- Batch Redis operations in `ConversationCache.sync_conversation` and `sync_all` using `async with r.pipeline() as pipe:`.

#### [MODIFY] app/services/conversation_cache.py
- Apply `pipe.sadd()` and `pipe.delete()` in cache syncing methods, followed by a single `await pipe.execute()`.

---

### 5. Outbox/Queue for Slow Clients (Backpressure) 🟠🟠🟠 (Pending) Above 4 has been done
**Problem**: Sending JSON to a slow client blocks the execution loop for other clients.
**Fix**:
- Add an `asyncio.Queue` and a background worker task for each WebSocket connection. `send_to_user` will drop messages into the queue instantly without blocking, and the worker will send them over the socket.

#### [MODIFY] app/ws/manager.py
- Add `send_queue: asyncio.Queue` and `send_task: asyncio.Task` to the `Connection` object.
- In `connect()`, spawn an `asyncio.create_task` that runs a `while True:` loop, reading from the `send_queue` and writing to `conn.ws`.
- In `send_to_user()`, use `conn.send_queue.put_nowait(payload)` instead of `await conn.ws.send_json(payload)`.
- In `disconnect()`, call `send_task.cancel()`.

## Verification Plan
1. Check that the server boots up without N+1 query delays.
2. Connect websockets and verify database connections are returned to the pool (not held indefinitely).
3. Send a message to verify the Outbox `asyncio.Queue` properly receives and forwards messages.
4. Abruptly disconnect a client and observe Redis to confirm watcher presence sets are cleaned up.
