# Automated Voice-to-Text Customer Communication System 🎙️📚

A lightweight, high-performance customer voice automation system designed to transcribe customer speech audio into text and search local databases—**without requiring heavy generative AI models**.

Ideal for school projects, library locators, campus helpdesks, and bus status lookup systems!

---

## 🌟 Key Features

1. **Dual Operating Modes**:
   - **Zero-Cost Browser Demo (School Presentation)**: Built-in native Web Speech API integration (`webkitSpeechRecognition` & Speech Synthesis) allowing live voice search directly in the browser without Twilio credits or ngrok.
   - **Real Phone Telephony Integration (Twilio)**: Handles live phone calls and SMS via Twilio webhooks using TwiML `<Gather input="speech">` and Speech-to-Text (STT).
2. **AI-Free Fast Database Search**:
   - SQLite database (`school_library.db`) with keyword matching (`LIKE` clauses) for accurate, deterministic results with zero AI hallucinations or delays.
3. **Interactive Web Dashboard**:
   - Modern dark glassmorphism interface.
   - Live microphone voice input with speech visualization.
   - Interactive Twilio Webhook & TwiML XML Simulator.
   - Real-time catalog inventory editor & call logs viewer.

---

## 📐 System Architecture

```
                                  +------------------------------------+
                                  |     Caller (Phone / SMS)           |
                                  +------------------+-----------------+
                                                     |
                                                     v
                                  +------------------+-----------------+
                                  |        Twilio Voice / SMS          |
                                  +------------------+-----------------+
                                                     | (Webhook POST)
                                                     v
+------------------+   Web Speech  +-----------------+-----------------+
|  Web Browser UI  |<------------->|           Flask Backend           |
| (Interactive Demo|   API (JS)    |  - /voice (TwiML Gather)          |
|  & Dashboard)    |               |  - /handle-speech (STT Search)    |
+------------------+               |  - /api/search (REST Endpoint)    |
                                   +-----------------+-----------------+
                                                     |
                                                     v
                                   +-----------------+-----------------+
                                   |    SQLite DB (school_library.db)  |
                                   |  - books & shelf locations        |
                                   |  - voice call & query logs        |
                                   +-----------------------------------+
```

---

## 🚀 Quick Start Guide

### 1. Prerequisites
- Python 3.8 or higher installed on your system.

### 2. Install Dependencies
```bash
pip install -r requirements.txt
```
*(Note: `flask` and `twilio` are the main dependencies).*

### 3. Launch the Server
```bash
python app.py
```

### 4. Open the Web Application
Navigate to `http://127.0.0.1:5000` in Google Chrome or Microsoft Edge.

---

## 🎙️ How to Test & Demonstrate

### Option A: Free Browser Voice Search (Recommended for Classrooms)
1. Open `http://127.0.0.1:5000` in Google Chrome or Edge.
2. Click the **Microphone Button** on the **Live Voice Demo** tab.
3. Speak clearly into your microphone: *"Physics"* or *"Computer Science"*.
4. Watch the browser transcribe your speech in real-time, query the SQLite database, display the shelf location, and speak back the result!

### Option B: Real Phone Calls via Twilio & ngrok
To trigger automated calls from real phone numbers:

1. **Start ngrok tunnel**:
   ```bash
   ngrok http 5000
   ```
   Copy your forwarding HTTPS URL (e.g. `https://your-subdomain.ngrok-free.app`).

2. **Configure Twilio Phone Number**:
   - Go to [Twilio Console](https://console.twilio.com/) → **Active Numbers**.
   - Under **Voice & Fax**, set **A CALL COMES IN** to `Webhook` `HTTP POST`.
   - Set the URL to: `https://your-subdomain.ngrok-free.app/voice`
   - Under **Messaging**, set **A MESSAGE COMES IN** to: `https://your-subdomain.ngrok-free.app/sms`

3. **Make a Call**:
   - Dial your Twilio Phone Number from your phone.
   - Listen to the greeting prompt, speak the name of a book (e.g. *"Calculus"*), and the system will automatically transcribe your voice and respond with the shelf location over the phone!

---

## 📁 Project Structure

```
CSE472/
├── app.py                 # Flask backend, SQLite DB logic, & Twilio webhooks
├── requirements.txt       # Python dependencies (Flask, Twilio, dotenv)
├── .env.example           # Environment template for Twilio keys
├── school_library.db      # SQLite database (auto-generated on first run)
├── templates/
│   └── index.html         # Glassmorphism HTML dashboard & voice UI
├── static/
│   ├── style.css          # Modern dark CSS styling & animations
│   └── app.js             # Web Speech API & AJAX frontend logic
└── README.md              # Documentation & setup guide
```

---

## 💡 Key School Project Talking Points

When presenting this project to your teachers or evaluators, highlight these key engineering decisions:
- **No Generative AI Overhead**: Eliminates API costs, latency, and model hallucinations by pairing standard Speech-to-Text (STT) with structured database queries.
- **Deterministic Accuracy**: Guarantees that inventory locations, availability status, and student info are 100% accurate.
- **Multi-Channel Accessibility**: Works via web browser speech, phone voice calls, and SMS text messages.
