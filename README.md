# Alfred

A personal AI agent I talk to through Telegram, by text, voice or photo. Alfred manages my calendar, inbox and bills, runs an overnight market and news pipeline that grades its own prediction accuracy, tracks my health against my own baselines, and looks for patterns across all of it. It raises one only when it clears a strict bar enforced in code.

Built solo in Python. Speech runs locally; Claude handles reasoning and tool selection.

<img width="643" height="983" alt="Alfred in Telegram" src="https://github.com/user-attachments/assets/d4e12a46-b42b-48fd-9b5a-8d07df31405f" />

---

## What it does

| Area | Capabilities |
|---|---|
| **Conversation** | Claude tool calling with short-term history (SQLite) and long-term semantic memory (ChromaDB). Only durable facts I state are remembered: a Claude judge filters each message and fails closed, and Alfred's own replies are never stored as memory. |
| **Voice** | Telegram voice notes → Whisper (local STT) → Alfred → Kokoro (local TTS, British male voice) → voice reply |
| **Calendar** | Read, add, edit and delete events; find free time (daylight-saving aware) |
| **Email** | Summarise unread mail, search with Gmail syntax, draft, send |
| **Markets** | Watchlist and portfolio tracking, 12 technical signal types, daily price alerts, Claude-written brief |
| **Self-grading** | Every signal is logged as a hypothesis and graded automatically once its timeframe passes. Accuracy per signal type is reported honestly, including when it's poor. |
| **News intelligence** | RSS (Yahoo, Google News, Fed, RBNZ) → dedupe → Claude classifies events and reasons through direct, second- and third-order effects → hypotheses logged and graded |
| **Self-calibration** | Confidence per signal type moves up or down with Alfred's own track record (after 20+ graded signals) |
| **Health** | Sleep, energy, mood and more, logged from plain language; every value compared to my own baseline (z-scores), never to population averages |
| **Intelligence layer** | Daily 11-step inference across health, activity rhythm, calendar load, learning, money and my own words. Observations are tiered 1–5; a code-enforced gate (5+ data points, 2+ domains, 7-day cooldown, quiet hours, busy-calendar check) decides what's worth saying. Alfred keeps score from my ratings and raises its own bar when it's wrong. |
| **Reviews** | Weekly, monthly and quarterly life reviews, each compared to the previous one |
| **Socrates mode** | "Think through this with me" switches Alfred from answering to questioning, with memory of past thinking sessions |
| **Vision coaching** | Photo of the fridge → meal ideas pitched to my cooking history; mid-cooking photos → technique feedback; progress logged |
| **Bills & banking** | Recurring bills with 3-day reminders; Akahu (NZ open banking, read-only): spending by category, subscription detection, unusual-spend alerts |
| **Food ordering** | Saved "usual" orders; Playwright builds the DoorDash cart; checkout needs a tap to confirm |
| **Morning brief** | 7am: weather, today's calendar, unread mail, overnight market + news brief, gentle check-in — as text and voice |

## Architecture

```
Phone (Telegram) ──text / voice / photo──▶ bot.py ──(only my chat ID gets through)
                                     │
            voice? ──▶ Whisper (local) ──▶ text      photo? ──▶ image block (vision)
                                     │
   ChromaDB memories + recent SQLite history + preferences (+ Socrates mode if active)
                                     │
                                     ▼
                  Claude API (tool-calling loop, cached tool list)
                                     │
                    tool_registry.py — 46 tools, one dispatch table
  ┌─────────┬───────┬──────────┬─────────┴──┬────────┬─────────┬──────────┬──────────┐
Calendar  Gmail  Web/weather  Finance/news  Health  Bills/   Learning   Food      Self-
                                                    Akahu    Socrates  ordering  knowledge
                                     │
            gated tools (send email, delete event, checkout) ──▶ ✅ / ❌ buttons
                                     │
                    reply text ──▶ Kokoro TTS (local) ──▶ voice reply

APScheduler (NZ time)
  05:00 Tue–Sat  market pipeline: grade → scan → news analysis → calibrate → log → Claude brief
  07:00 daily    morning brief (text + voice) + gentle check-in
  09:00 daily    bill reminders, subscription renewals, unusual spending
  10:30 Tue–Sat  watchlist move alerts (after US close)
  18:00 daily    inference engine → at most one observation, only if it clears the gate
  20:30 daily    optional evening check-in (only if nothing logged)
  Sun 19:00 · 1st 09:30 · quarterly   weekly / monthly / quarterly reviews
```

## Safety design

- **Single-user lock.** Telegram handlers are filtered to one chat ID, so anyone else who finds the bot gets no response.
- **Confirmation gate in code, not in the prompt.** Irreversible tools (send email, delete event, place order) are never executed directly. They're parked and executed only when I tap Confirm. The same holds if Claude misreads a request, or if an email or web page tries to inject instructions.
- **Spend limits.** Food checkout is dry-run by default, has a hard NZD cap, and aborts if the cart total changed since I confirmed.
- **No `eval`.** The calculator walks the Python AST and allows only arithmetic and a short list of maths functions.
- **Audit log.** Every scheduled job, gated action and failure is timestamped in `task_history`.
- **Kill switch.** `/stop` shuts down the scheduler and the bot.
- **Honest by construction.** Observations must clear a code-enforced bar, the prompt forbids claiming history that isn't in the data, and Alfred never diagnoses. Serious wellbeing signals bypass quiet hours and include NZ support lines (1737, Lifeline).
- **Banking is read-only.** Akahu is used for reading only; no payments.
- **Secrets** live only in `.env` and OAuth token files, which are never committed. The DoorDash login is a browser session I create by hand; Alfred never sees the password.

## Stack

Python 3.13 · Claude API (tool use) · python-telegram-bot · SQLite · ChromaDB · Whisper · Kokoro (ONNX) · Google Calendar & Gmail APIs (OAuth2) · Claude vision · yfinance · pandas · pandas-ta · feedparser · Akahu API · Playwright · APScheduler · pytest · Docker

## Project layout

All the code lives in `alfred/`:

```
bot.py              Telegram handlers, Claude tool loop, scheduler, commands
tool_registry.py    Every tool: schema + function + needs-confirmation flag
confirmations.py    Pending-action store behind the ✅/❌ buttons
config.py           All settings and paths (env-overridable)
llm.py              Shared Claude client
database.py         SQLite schema and helpers
memory.py           ChromaDB semantic memory
memory_gate.py      Decides what's worth remembering (user facts only, fails closed)
tools.py            Web search, weather, safe calculator, preferences
calendar_tool.py    Google Calendar
gmail_tool.py       Gmail
google_auth.py      OAuth2 flow and token refresh
finance_tool.py     Quotes, portfolio, watchlist, move alerts
market_signals.py   Indicators and the signal scanner (pure functions)
hypothesis.py       Logging, grading and accuracy reporting
market_pipeline.py  The 5am job that ties the finance module together
news_pipeline.py    RSS news → Claude event analysis → graded hypotheses
morning_brief.py    7am brief (text + voice)
health.py           Health logging and personal baselines (z-scores)
intelligence.py     Inference engine, surfacing gate, self-scoring, reviews
socrates.py         Socrates thinking mode + session memory
learning.py         Cooking / learning history for vision coaching
bills.py            Recurring bills, drift-free due dates, reminders
akahu_tool.py       NZ open banking: spending, subscriptions, unusual spend
food_order.py       Usual orders + Playwright cart / checkout
voice_handler.py    Whisper speech-to-text
tts_handler.py      Kokoro text-to-speech
tests/              pytest suite — 84 tests
```

## Setup

> **Not included in this repo:** the Kokoro voice model files (`kokoro-v1_0.onnx`, `voices-v1_0.bin`, ~350 MB, download them separately) and all secrets (`.env`, `credentials.json`, `token.json`). Copy `.env.example` to `.env` and fill in your own keys.

### 1. Accounts and keys
1. Telegram: create a bot with **@BotFather** to get the token, and find your chat ID with **@userinfobot**.
2. Anthropic: create an API key at console.anthropic.com.
3. Google Cloud: create a project, enable the **Calendar** and **Gmail** APIs, configure the OAuth consent screen, create a **Desktop app** OAuth client and download it as `credentials.json`.
4. Kokoro: download `kokoro-v1_0.onnx` and `voices-v1_0.bin` into the `alfred/` folder.

All the commands below are run from inside the `alfred/` folder.

### 2. Run locally (Windows)
```powershell
cd alfred
py -3.13 -m venv venv
.\venv\Scripts\activate
pip install -r requirements.txt
playwright install chromium          # only needed for food ordering
copy .env.example .env               # then fill it in
py auth_test.py                      # one-time Google login → creates token.json
py bot.py
```
ffmpeg must be on your PATH for Whisper.

### 3. Run in Docker
```bash
cd alfred
mkdir data
# move runtime data into the mounted folder
mv alfred.db chroma_db token.json credentials.json data/
docker compose up -d --build
docker compose logs -f
```
Complete the Google OAuth login once on the host (step 2) before running in Docker. A container can't open a browser.

### 4. Optional: food ordering
```bash
py food_order.py login                  # log in to DoorDash by hand once
py food_order.py test "friday burger"   # watch it build the cart
```
Then tell Alfred: *"save my usual Friday order: Bastard burger and kumara fries from Burger Fuel"*.
Checkout stays in dry-run until you set `ALFRED_ORDER_DRY_RUN=false`.

### 5. Optional: banking
Create a free Akahu personal app (my.akahu.nz → connect banks; developers.akahu.nz → tokens) and add `AKAHU_APP_TOKEN` and `AKAHU_USER_TOKEN` to `.env`.

## Tests
```bash
cd alfred
py -m pytest tests -q
```
84 tests cover:
- the signal scanner on synthetic price series, and hypothesis grading (including out-of-order rows)
- the memory gate failing closed on errors and malformed answers
- SQLite WAL mode and concurrent writes from two threads
- tool errors never leaking raw exception messages
- confidence calibration and news deduplication
- free-slot finding across NZ daylight saving
- the calculator's injection resistance and the confirmation gate
- health baselines and bill date maths (31st → 28 Feb → 31 Mar)
- subscription and unusual-spend detection
- every branch of the intelligence surfacing gate, and the Socrates session lifecycle

They run against a temp database, so no network or API calls.

## Commands

| Command | What it does |
|---|---|
| `/brief` | Morning brief now |
| `/market` | Run the market + news pipeline now |
| `/review` | Weekly life review now |
| `/stop` | Kill switch |

Also: send a photo for vision coaching, and say *"think through this with me"* for Socrates mode.

## Why I Built Alfred
I built Alfred because starting things bills, admin, ordering food, anything that needs structure to begin has always cost me more effort than it should. Alfred takes the friction out of that: it handles the admin I'd otherwise put off, and quietly keeps track of things so I don't have to hold them all in my head.

I'm also drawn to behavioural psychology, and I'm curious what Alfred becomes over time a tool that reflects my own patterns back to me and helps me understand how I actually function.

## What Alfred won't do
Alfred doesn't recommend trades, doesn't claim certainty about prices, and doesn't hide a poor track record. The market brief describes what the indicators show, alongside how often each signal type has actually been right.
