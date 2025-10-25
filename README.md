# 🎙️ EchoDiary

**An AI-powered voice diary and emotional companion that listens, remembers, and cares.**

> 🏆 **Winner - First Place** at [Layercode Voice AI Hackathon at Cloudflare 2025]

EchoDiary is a voice-first journaling application that lets you share your thoughts and feelings through natural phone conversations. It uses advanced AI to understand your emotions, build a knowledge graph of your life, and provide empathetic responses in real-time.

## ⚡ Powered by Layercode - NO CODE Voice Pipeline

The entire voice infrastructure is orchestrated **with minimal latency** using [Layercode](https://layercode.com)'s NO CODE platform. Layercode handles Twilio, Deepgram, and Rime integration automatically - **no complex setup required**. 

**Our custom backend connects with just a single webhook endpoint.** That's it. No SDK installation, no complex API integrations, no voice infrastructure management. Just pure business logic.

---

## ✨ Features

### 🗣️ **Natural Voice Conversations**
- Call EchoDiary like a friend - no app installation required
- Real-time speech-to-text and text-to-speech
- Natural, empathetic AI responses powered by OpenAI GPT

### 🧠 **Knowledge Graph**
- Automatically extracts entities (people, places, topics, emotions) from your conversations
- Builds relationships between entities over time
- Visual knowledge graph to see connections in your life

### 📊 **Mood Tracking**
- AI-powered mood analysis (1-10 scale) from your voice
- Track emotional patterns over time
- Historical mood graphs and statistics

### 💬 **Multiple Conversation Modes**
- **Reassure Mode**: Warm, supportive responses for difficult times
- **Tough Love Mode**: Direct, motivational feedback when you need a push
- **Listener Mode**: Gentle acknowledgment, lets you talk it out

### 📞 **Smart Check-ins**
- Automatic follow-up when mood drops below threshold
- Scheduled check-ins via SMS or voice call
- Personalized messages based on your history

### 📱 **Web Dashboard**
- View all your call history
- Interactive knowledge graph visualization
- Mood statistics and trends
- Individual call transcripts

---

## 🏗️ Architecture

```mermaid
flowchart TB
    Phone[📱 Phone User]
    Web[💻 Web User]
    
    subgraph Layercode["🔊 Layercode NO CODE Platform"]
        Twilio[📞 Twilio Voice]
        SDK[🌐 JS SDK<br/>Web Audio]
        Deepgram[🎤 Deepgram STT]
        Rime[🔊 Rime AI TTS<br/>Emotion-Aware]
    end
    
    subgraph Backend["🖥️ EchoDiary Backend - FastAPI"]
        Auth[🔐 /api/authorize<br/>Session Auth]
        Webhook[📡 /layercode/webhook<br/>SSE Handler]
        
        subgraph Intelligence["🧠 AI Response Engine"]
            Context[📚 Context Manager<br/>Last 3 Turns]
            GPT[🤖 OpenAI GPT<br/>temp=0.9<br/>Echo Personality]
            Prompts[💬 Mode Prompts<br/>Supportive/Tough/Listener]
        end
        
        Redis[⚡ Redis<br/>Active Sessions<br/>Conversation Context]
        
        subgraph Processing["⚙️ Background Processing"]
            Entity[🧩 Entity Extraction<br/>People/Places/Emotions]
            Mood[😊 Mood Analysis<br/>1-10 Score]
            Audio[🎵 Audio Download<br/>Local Storage]
            CheckIn[⏰ Smart Check-ins<br/>If mood < 3]
        end
        
        DB[(💾 SQLite<br/>Permanent Storage)]
    end
    
    subgraph Frontend["🌐 Web Dashboard"]
        Talk[🎙️ Talk Now<br/>Live Calling]
        Home[🏠 Call History]
        CallPage[📄 Call Details<br/>Export Options]
        Graph[🕸️ Knowledge Graph]
        Stats[📊 Mood Stats]
    end
    
    %% User Entry Points
    Phone -->|Dials In| Twilio
    Web -->|Opens /talk.html| SDK
    
    %% Voice Pipeline
    Twilio -->|Audio Stream| Deepgram
    SDK -->|Web Audio| Deepgram
    Deepgram -->|user.transcript| Webhook
    
    %% Authorization Flow
    SDK -->|Request Auth| Auth
    Auth -->|Call Layercode API| Layercode
    Auth -->|Return session_key| SDK
    
    %% Response Generation Flow
    Webhook -->|1. Get Context| Redis
    Redis -->|Last 3 Turns| Context
    Context -->|2. Build Messages| GPT
    Prompts -->|System Prompt| GPT
    GPT -->|3. Generate Response| Webhook
    Webhook -->|4. Store Turn| Redis
    Webhook -->|5. Store Transcript| DB
    
    %% TTS & Delivery
    Webhook -->|SSE Stream<br/>+ Emotion| Rime
    Rime -->|Natural Voice| Twilio
    Rime -->|Natural Voice| SDK
    Twilio -->|Audio| Phone
    SDK -->|Audio| Web
    
    %% Background Processing
    Webhook -->|On Call End| Audio
    Audio -->|Download & Save| DB
    Webhook -->|Full Transcript| Entity
    Webhook -->|Full Transcript| Mood
    Entity -->|Knowledge Graph| DB
    Mood -->|Score & Sentiment| DB
    Mood -->|If Low Mood| CheckIn
    CheckIn -->|Schedule SMS| Twilio
    
    %% Frontend Interactions
    Web -->|Browse| Home
    Home -->|View Details| CallPage
    CallPage -->|Export| DB
    Home -->|Visualize| Graph
    Home -->|View Trends| Stats
    
    %% Data Flow
    DB -->|Read| Frontend
    
    style Layercode fill:#667eea,stroke:#764ba2,color:#fff
    style Intelligence fill:#f093fb,stroke:#f5576c,color:#fff
    style Processing fill:#4facfe,stroke:#00f2fe,color:#fff
    style GPT fill:#fa709a,stroke:#fee140,color:#fff
```

### Technology Stack

**Voice Pipeline (Orchestrated by Layercode - NO CODE):**
- **Layercode Platform** - Zero-code voice orchestration with minimal latency
- **Twilio** - Phone call infrastructure (auto-configured by Layercode)
- **Deepgram** - Speech-to-text transcription (auto-configured by Layercode)
- **Rime AI** - Expressive text-to-speech (auto-configured by Layercode)

**Backend (Your Custom Logic):**
- **FastAPI** - High-performance web framework
- **OpenAI GPT** - Conversational AI and entity extraction
- **Redis (Upstash)** - Session state & conversation context during calls
- **SQLAlchemy** - Database ORM
- **SQLite** - Persistent data storage
- **APScheduler** - Background task scheduling
- **Server-Sent Events (SSE)** - Real-time response streaming to Layercode

**Frontend:**
- Vanilla HTML/CSS/JavaScript
- D3.js for knowledge graph visualization

> **Note:** Redis stores active call sessions and conversation context (last 3 turns) for fast retrieval during conversations. SSE streams responses back to Layercode in real-time. SQLite stores all permanent data (users, calls, transcripts, knowledge graph).

---

## 🚀 How It Works

### 1️⃣ **You Call In**
When you dial EchoDiary's number, **Layercode's NO CODE platform** orchestrates everything:
- Twilio receives your call (auto-configured by Layercode)
- Deepgram transcribes your speech in real-time (auto-configured by Layercode)
- Transcript is sent to EchoDiary backend via **a single webhook** - that's all you need!

### 2️⃣ **AI Responds** (Your Custom Backend)
EchoDiary backend processes your message:
1. Retrieves your conversation history from Redis (last 3 turns for context)
2. Generates empathetic response using OpenAI GPT
3. Streams response back to Layercode via SSE (Server-Sent Events)
4. **Layercode handles the rest** - Rime TTS conversion, audio streaming, call management
5. You hear the response instantly - all with minimal latency!

### 3️⃣ **Background Magic**
After the call ends, EchoDiary:
- Extracts entities (people, places, emotions, topics) using GPT
- Builds relationships in your knowledge graph
- Calculates your mood score (1-10 scale)
- Schedules check-in if mood is concerning

### 4️⃣ **Review & Reflect**
Visit the web dashboard to:
- See your call history with transcripts
- Explore your interactive knowledge graph
- Track mood trends over time
- Review what you talked about

---

## 🔌 Why Layercode?

**Building voice AI used to be complex.** You'd need to:
- Set up Twilio webhooks
- Configure Deepgram streaming
- Implement audio buffering
- Handle TTS synthesis
- Manage WebSocket connections
- Deal with audio format conversions

**With Layercode, it's just a webhook.** ✨

```python
@router.post("/layercode/webhook/transcript")
async def handle_transcript_webhook(request: Request):
    data = await request.json()
    # Your business logic here
    response = generate_ai_response(data['text'])
    # Stream back to Layercode
    return StreamingResponse(...)
```

That's it. Layercode handles **all the voice infrastructure** with NO CODE configuration and minimal latency.

---

## 📋 Prerequisites

- Python 3.10+
- Redis instance (we recommend [Upstash](https://upstash.com/) free tier)
- OpenAI API key
- Layercode account with:
  - Twilio phone number
  - Deepgram API key
  - Rime AI API key

---

## ⚙️ Installation

### 1. Clone the Repository
```bash
git clone https://github.com/yourusername/echodiary.git
cd echodiary
```

### 2. Create Virtual Environment
```bash
python -m venv venv

# Windows
venv\Scripts\activate

# Mac/Linux
source venv/bin/activate
```

### 3. Install Dependencies
```bash
pip install -r requirements.txt
```

### 4. Configure Environment Variables
Create a `.env` file in the root directory:

```env
# Application
APP_NAME=EchoDiary
DEBUG=false
HOST=0.0.0.0
PORT=8000

# Database
DATABASE_URL=sqlite+aiosqlite:///./echodiary.db

# Redis (Upstash)
UPSTASH_REDIS_URL=your_upstash_redis_url
UPSTASH_REDIS_TOKEN=your_upstash_redis_token

# OpenAI (Required)
OPENAI_API_KEY=your_openai_api_key

# Layercode (Optional - for direct integration)
LAYERCODE_API_KEY=your_layercode_api_key
```

See `env_example.txt` for full configuration options.

### 5. Initialize Database
```bash
python -m app.database
```

### 6. Run the Application
```bash
uvicorn app.main:app --reload
```

The app will be available at `http://localhost:8000`

---

## 🔧 Layercode Configuration (NO CODE Required!)

### Connect Your Backend with ONE Webhook

The beauty of Layercode is its simplicity. **No code changes needed on their side** - just configure your webhook in their dashboard:

1. **In Layercode Dashboard**: Set your webhook URL
   ```
   https://your-domain.com/layercode/webhook/transcript
   ```

2. **That's literally it.** Layercode sends you these events automatically:
   - `session.start` - Call begins
   - `message` - User speaks (transcript arrives in real-time)
   - `session.end` - Call ends

3. **Your Response**: Stream back via SSE (Server-Sent Events)
   ```json
   data: {"type": "response.tts", "content": "AI response here", "turn_id": "..."}
   data: {"type": "response.end", "turn_id": "..."}
   ```

**Layercode handles everything else**: Twilio routing, Deepgram transcription, Rime TTS, audio streaming, call management - all with **minimal latency** and **zero voice infrastructure code**.

---

## 📱 Usage

### Making a Call
1. Dial your Layercode phone number
2. Wait for the welcome message
3. Start talking! EchoDiary will respond naturally
4. Hang up when you're done

### Web Dashboard
Navigate to:
- **Home** (`/`) - View all calls
- **Call Details** (`/call.html?id=X`) - See transcript and details
- **Knowledge Graph** (`/graph.html`) - Visualize your entities
- **Statistics** (`/stats.html`) - View mood trends

---

## 🗂️ Project Structure

```
echodiary/
├── app/
│   ├── main.py                 # FastAPI application entry point
│   ├── config.py              # Configuration management
│   ├── database.py            # Database setup
│   ├── models.py              # SQLAlchemy models
│   ├── schemas.py             # Pydantic schemas
│   ├── redis_client.py        # Redis session management
│   ├── tasks.py               # Background processing tasks
│   ├── routes/
│   │   ├── api.py            # REST API endpoints
│   │   ├── cron.py           # Scheduled tasks
│   │   └── layercode.py      # Layercode webhook handlers
│   └── services/
│       ├── openai_service.py  # OpenAI integration
│       └── layercode_service.py # Layercode integration
├── static/
│   └── css/
│       └── style.css          # Styling
├── templates/
│   ├── index.html            # Home page
│   ├── call.html             # Call details page
│   ├── graph.html            # Knowledge graph visualization
│   └── stats.html            # Statistics page
├── audio_recordings/         # Stored audio files
├── requirements.txt          # Python dependencies
├── .env                      # Environment variables (create this)
└── README.md                 # You are here!
```

---

## 🔌 API Endpoints

### Layercode Webhooks
- `POST /layercode/webhook/transcript` - Main webhook for all events
- `POST /layercode/webhook/call-start` - Call start handler
- `POST /layercode/webhook/call-end` - Call end handler

### Web API
- `GET /api/calls` - List all calls
- `GET /api/calls/{id}` - Get call details
- `GET /api/calls/{id}/transcript` - Get call transcript
- `GET /api/entities` - Get knowledge graph data
- `GET /api/stats` - Get mood statistics

### Health Checks
- `GET /health` - Application health
- `GET /layercode/health` - Webhook health

---

## 📊 Database Schema

### Core Tables
- **users** - User profiles and preferences
- **calls** - Call records with metadata
- **transcripts** - Turn-by-turn conversation history
- **entities** - Knowledge graph entities
- **relations** - Entity relationships
- **checkins** - Scheduled follow-up reminders

See `app/models.py` for detailed schema.

---

## 🤝 Contributing

We'd love your contributions! Here's how:

1. Fork the repository
2. Create a feature branch (`git checkout -b feature/amazing-feature`)
3. Commit your changes (`git commit -m 'Add amazing feature'`)
4. Push to the branch (`git push origin feature/amazing-feature`)
5. Open a Pull Request

---

## 🐛 Known Issues

- Knowledge graph visualization could use performance optimization for 100+ entities
- Check-in scheduler needs more robust error handling
- Audio file storage could benefit from cloud storage integration

---

## 🗺️ Roadmap

- [ ] Multi-language support
- [ ] WhatsApp integration
- [ ] Advanced sentiment analysis
- [ ] Voice emotion detection
- [ ] Export diary entries
- [ ] Mobile app
- [ ] Group therapy sessions
- [ ] Integration with mental health resources

---

## 📄 License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.

---

## 🙏 Acknowledgments

- **Layercode** for building the most developer-friendly NO CODE voice platform - you made voice AI accessible with just a webhook! 🎙️
- **OpenAI** for GPT's incredible conversational abilities
- **Hackathon Organizers** for the opportunity and support
- **Our users** for trusting us with their stories

---

## 💬 Contact

Have questions? Want to chat about the project?

- **Email**: your-email@example.com
- **GitHub**: [@yourusername](https://github.com/yourusername)
- **Twitter**: [@yourhandle](https://twitter.com/yourhandle)

---

<div align="center">
  <b>Built with ❤️ for the Voice AI Hackathon 2025</b>
  <br>
  <sub>If EchoDiary helped you, consider giving it a ⭐️</sub>
</div>
