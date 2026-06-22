# Alfred

Alfred is a personal AI assistant built to manage information across multiple areas of daily life through a single conversational interface.

Unlike a traditional chatbot, Alfred combines memory, email, calendar management, voice interaction and personal productivity tools into a unified assistant designed for long-term use.

## Features

- Persistent memory using ChromaDB and SQLite
- Gmail integration (read, search and summarise emails)
- Google Calendar integration (read and create events)
- Voice input using Whisper
- Voice output using Kokoro TTS
- Daily morning brief generation
- Portfolio tracking and watchlists
- Technical market analysis (RSI, moving averages)
- Tool-based orchestration framework
- Telegram chat interface

## Architecture

```text
Telegram
    │
    ▼
FastAPI Backend
    │
 ┌──┴─────────────┐
 ▼                ▼
Claude         Memory Layer
                (ChromaDB +
                 SQLite)

    │
    ▼

Tool Router

├─ Gmail
├─ Calendar
├─ Portfolio
├─ Morning Brief
├─ Voice Services
└─ Future Tools
```

## Screenshots

<img width="580" height="967" alt="image" src="https://github.com/user-attachments/assets/be028587-76df-4a4b-afbc-3fd0c69de88d" />


## Technical Stack

### Backend

- Python
- FastAPI
- SQLite
- ChromaDB

### AI & Voice

- Claude API
- Whisper
- Kokoro TTS

### Integrations

- Gmail API
- Google Calendar API
- Telegram Bot API

## Why I Built It

Alfred started as an experiment in long-term AI memory and personal productivity.

The long-term goal is to explore whether an AI assistant can build a more consistent model of behaviour, habits and preferences over time by combining memory, communication, scheduling and personal data into a single system.

## Future Work

- Enhanced behavioural profiling
- Better memory retrieval and ranking
- Additional productivity integrations
- Improved voice conversations
- Deployment and multi-device access
