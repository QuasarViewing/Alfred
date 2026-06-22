# Alfred

> Personal AI assistant and life-management platform built in Python.

Alfred combines memory, email, calendar management, voice interaction, financial tools, and automation into a single conversational interface.

Built as both a long-term personal project and a software engineering learning platform.

---

## Features

### Memory & Context
- Persistent memory using ChromaDB and SQLite
- Context retrieval across conversations
- Structured conversation storage
- Long-term memory experiments

### Communication
- Gmail integration
- Email retrieval and summarisation
- Action item extraction
- Inbox overview generation

### Scheduling
- Google Calendar integration
- Natural language calendar queries
- Event retrieval and schedule awareness

### Voice
- Whisper speech-to-text
- Kokoro text-to-speech
- End-to-end voice interactions

### Daily Briefing
- Weather overview
- Calendar summary
- Email highlights
- Daily information aggregation

### Financial Tools
- Portfolio tracking
- Watchlists
- Position performance tracking
- RSI calculations
- Moving averages
- Market data retrieval through Yahoo Finance

### Tool Framework
- Modular tool architecture
- Dynamic tool execution
- Extensible integration system

---

# Screenshots


<img width="643" height="983" alt="image" src="https://github.com/user-attachments/assets/d4e12a46-b42b-48fd-9b5a-8d07df31405f" />


---

# Architecture

```text
User
 │
 ▼
Telegram
 │
 ▼
Message Handler
 │
 ▼
Claude
 │
 ▼
Tool Router
 ├── Memory
 ├── Gmail
 ├── Calendar
 ├── Finance
 ├── Morning Brief
 └── Voice Services
 │
 ▼
Response
```

# Tech Stack

## Backend

- Python
- FastAPI
- SQLite
- ChromaDB

## AI & Voice

- Claude API
- Whisper
- Kokoro TTS

## Integrations

- Gmail API
- Google Calendar API
- Telegram Bot API
- Yahoo Finance API

## Development

- Git
- Virtual Environments
- Structured Logging
- Environment Configuration
- Error Handling

---

# Learning Objectives

Alfred was used as a practical software engineering learning project.

Topics explored while building the system include:

- FastAPI
- OAuth
- Google APIs
- Logging
- Error Handling
- Database Design
- Context Managers
- Function Composition
- API Integrations
- Tool Orchestration

Each new concept was documented with notes, examples, and exercises during development.

---

# Why I Built Alfred

Most productivity tools focus on a single domain.

Alfred explores what happens when memory, communication, scheduling, voice interaction, and personal data are combined into a single assistant capable of maintaining long-term context.

The project began as a software engineering learning exercise and evolved into an ongoing exploration of AI-assisted personal organisation.

---

# Current Status

Personal project.

Used as a platform for experimentation, learning, and exploration of long-term AI systems.

---

# Future Areas of Exploration

- Improved memory retrieval
- Behavioural pattern analysis
- Additional automation workflows
- Enhanced voice interaction
- Expanded financial tooling
- Personal knowledge management
