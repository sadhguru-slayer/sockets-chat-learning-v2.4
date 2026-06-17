# Scalable FastAPI WebSocket Chat Application

## Overview
This is a scalable real-time chat application built with FastAPI and WebSockets. It uses Redis for Pub/Sub and horizontal scalability, and PostgreSQL (or SQLite locally) for persistence. The application has been fully scaled through three phases of architecture evolution.

## Setup and Installation

1. **Clone the repository:**
   ```bash
   mkdir chat_app # You can choose the name of your liking
   git clone <repository-url>
   cd chat_app
   ```

2. **Set up a virtual environment:**
   ```bash
   python -m venv venv
   # Windows
   .\venv\Scripts\activate
   # Linux/macOS
   source venv/bin/activate
   ```

3. **Install dependencies:**
   ```bash
   pip install -r requirements.txt
   ```

4. **Environment Variables:**
   Configure your environment variables in a `.env` file (e.g., Redis URL, Database URL).

5. **Run the application:**
   You can run the application locally using Uvicorn or run the Dockerized version:
   ```bash
   # Local run
   uvicorn app.main:app --host 0.0.0.0 --port 8000
   
   # Or using Docker Compose
   docker-compose up --build
   ```

## Architecture

For a detailed understanding of the architecture, horizontal scaling implementation, and the completed three-phase scaling strategy, please visit [Architecture.md](Architecture.md).
