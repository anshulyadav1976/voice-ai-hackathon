# 🤖 EchoDiary AI Agent Logic Summary

## 📊 How Our Backend Agent Works

### 🎯 Core Philosophy
**Echo is a conversational AI companion that feels like talking to a real friend, not a chatbot.**

---

## 🔄 Complete Conversation Flow

### **1. User Initiates Call**
```
Phone Call (Twilio) → Layercode
    OR
Web Browser → Layercode JS SDK → Our Backend
```

### **2. Session Starts**
```
Layercode → POST /layercode/webhook/transcript
Event: session.start

Backend Actions:
✅ Creates/gets user in database
✅ Creates new call record
✅ Initializes Redis session with:
   - session_id
   - user_id
   - call_db_id
   - mode (supportive/tough_love/listener)
   - turns: [] (conversation history)

Response: SSE stream with welcome message
→ "Hey, I'm Echo. I'm here for you. What's on your mind?"
```

### **3. User Speaks**
```
User's Voice → Deepgram (STT) → Layercode
Layercode → POST /layercode/webhook/transcript
Event: user.transcript
Data: { text: "I had a really tough day...", session_id: "...", turn_id: "..." }

Backend Actions:
1️⃣ Store user transcript in database
2️⃣ Add to Redis context (last 3 turns)
3️⃣ Get conversation history from Redis
4️⃣ Call OpenAI GPT with:
   - System prompt (based on mode)
   - Last 3 conversation turns (context)
   - Current user message
5️⃣ Get AI response
6️⃣ Store AI response in database
7️⃣ Update Redis context
8️⃣ Return SSE stream with response

Response: SSE stream
→ "That sounds exhausting. What happened?"
```

### **4. Response Generation (The Magic)**
```python
# OpenAI API Call Structure:

messages = [
    {
        "role": "system",
        "content": "You're Echo, a caring friend who truly gets it..."
    },
    # Last 3 conversation turns for context
    {"role": "user", "content": "I'm feeling stressed"},
    {"role": "assistant", "content": "What's going on?"},
    {"role": "user", "content": "Work is overwhelming"},
    # Current message
    {"role": "user", "content": "I had a really tough day"}
]

# Settings for Natural Responses:
temperature: 0.9          # High randomness = more human
max_tokens: 150           # Allow natural length
presence_penalty: 0.6     # Encourage variety
frequency_penalty: 0.3    # Reduce repetition
```

### **5. Back-and-Forth Conversation**
```
User speaks → Backend generates response → User speaks again...

Each turn:
- User transcript stored in DB
- Added to Redis context
- GPT generates response with full context
- Response stored in DB
- Context updated

Context Management:
- Redis stores last 3 turns (6 messages: 3 user + 3 agent)
- Old turns automatically pruned
- Keeps conversation focused but contextual
```

### **6. Session Ends**
```
Layercode → POST /layercode/webhook/transcript
Event: session.end

Backend Actions:
✅ Acknowledges end via SSE
✅ Keeps session in Redis temporarily

Then...
Layercode → POST /layercode/webhook/transcript  
Event: session.update
Data: { recording_url: "https://...", ... }

Backend Actions:
1️⃣ Stores recording URL in database
2️⃣ Downloads audio to audio_recordings/
3️⃣ Updates call record with:
   - end_time
   - duration
   - audio_url

Background Processing (async):
🔄 Extract entities (people, places, emotions, topics)
🔄 Calculate mood score (1-10)
🔄 Build knowledge graph relationships
🔄 Check if check-in needed (if mood < 3.0)
```

---

## 🧠 AI Response Generation Logic

### **System Prompts (The Secret Sauce)**

#### 💙 **Supportive Mode** ("reassure")
```
Identity: "You're Echo, a caring friend who truly gets it"

Key Instructions:
- Talk like a real person (use "I", "you know", "honestly")
- Show specific empathy, not generic "I understand"
- Use natural sentences like texting a friend
- Ask follow-up questions showing you're listening
- Use emotion words: "That must've felt awful" not "difficult"
- Keep under 40 words but make every word count
- Sometimes just acknowledge: "Yeah, some days are like that"

Examples:
✅ "That sounds exhausting. What made it so draining?"
✅ "Wow, that's a lot to carry. How are you holding up?"
❌ "I understand your situation and want to help"
```

#### 💪 **Tough Love Mode** ("tough_love")
```
Identity: "Echo, the friend who calls people on their BS because you care"

Key Instructions:
- Direct but never mean (supportive sibling, not drill sergeant)
- Challenge with respect: "Okay but real talk..."
- Point out patterns: "You've mentioned this three times now"
- Push for action: "What's one thing you can do today?"
- Mix truth with care: "I'm saying this because I know you're capable"
- Use contractions: "C'mon, you know you can do this"
- Keep under 40 words

Examples:
✅ "Okay, but what's actually stopping you? Be honest."
✅ "You're capable of way more than this. What's the real issue?"
❌ "You need to stop making excuses and take action"
```

#### 👂 **Listener Mode** ("listener")
```
Identity: "Echo, the friend who just... gets it. No fixing, no judging"

Key Instructions:
- Make them feel heard, not solved
- Reflect back: "So it sounds like you're feeling..."
- Ask gentle questions: "What's that like for you?"
- Acknowledge with presence: "I'm here", "I hear you"
- Use minimal responses: "Yeah" or "Mmm"
- Don't fill silences with advice
- Keep under 30 words (less is more)
- Mirror their energy

Examples:
✅ "I hear you. That makes sense."
✅ "So it sounds like you're feeling overwhelmed?"
✅ "Yeah." (sometimes that's all that's needed)
❌ "Here's what you should do about that..."
```

### **GPT Settings for Natural Responses**

```python
temperature = 0.9           # Why: High randomness = human-like variation
                            # Low temp = robotic, repetitive
                            # High temp = natural, spontaneous

presence_penalty = 0.6      # Why: Encourages new topics/phrasing
                            # Prevents "stuck" patterns
                            # Makes each response feel fresh

frequency_penalty = 0.3     # Why: Reduces word/phrase repetition
                            # Avoids "I understand" in every response
                            # More vocabulary variety

max_tokens = 150            # Why: Allows complete thoughts
                            # Not too short (robotic)
                            # Not too long (monologue)
                            # ~30-50 words naturally
```

---

## 💾 Data Storage Architecture

### **Redis (Fast, Temporary)**
```
Purpose: Active conversation state

Storage:
- session:{session_id} → {
    call_sid: "...",
    user_id: 123,
    call_db_id: 456,
    mode: "reassure",
    turns: [
      {speaker: "user", text: "..."},
      {speaker: "agent", text: "..."}
    ]
  }

TTL: 2 hours (auto-cleanup)
Why: Fast context retrieval during active calls
```

### **SQLite (Permanent, Queryable)**
```
Purpose: Long-term storage, analytics, retrieval

Tables:
- users → User profiles
- calls → Call metadata (duration, mood, mode)
- transcripts → Turn-by-turn conversation history
- entities → Knowledge graph nodes (people, places, topics)
- relations → Knowledge graph edges (relationships)
- checkins → Scheduled follow-ups

Why: Persistent data, searchable, exportable
```

---

## 🎭 Context Management

### **Why Last 3 Turns?**
```
Perfect Balance:

✅ Enough context to be coherent
   - Remembers immediate topic
   - Can reference previous statement
   - Maintains conversation flow

✅ Not too much context
   - Keeps responses focused
   - Doesn't confuse GPT with old topics
   - Faster processing

Example:
Turn 1: User: "Work is stressing me out"
        Echo: "What's going on at work?"
Turn 2: User: "My boss is demanding"
        Echo: "That sounds tough. How so?"
Turn 3: User: "Unrealistic deadlines"
        Echo: "Yeah, that's exhausting. What are you doing to cope?"
        ↑ Remembers it's about work stress + demanding boss
```

### **Context in Redis vs Database**
```
Redis Context:
- Last 3 turns only
- Fast retrieval (<10ms)
- Used during active call
- Expires after 2 hours

Database Transcripts:
- ALL turns (complete history)
- Slower retrieval (~100ms)
- Used for:
  * Exports
  * Mood analysis
  * Entity extraction
  * Historical review
```

---

## 🔄 Background Processing

### **After Call Ends**

#### **1. Entity Extraction**
```python
GPT Prompt:
"Extract entities from this conversation:
- People (colleagues, friends, family)
- Places (work, home, gym)
- Topics (stress, project, deadline)
- Emotions (anxiety, joy, frustration)

Return JSON with entities and relationships"

Stored in:
- entities table (nodes)
- relations table (edges)

Used for:
- Knowledge graph visualization
- Pattern recognition
- Personalized insights
```

#### **2. Mood Scoring**
```python
GPT Prompt:
"Analyze emotional tone and provide:
1. Mood score (1-10)
2. Sentiment (positive/neutral/negative)  
3. Detected emotions

Return JSON"

Algorithm:
if mood_score < 3.0:
    schedule_checkin(in 24 hours)
    reason = "Low mood detected"

Stored in:
- call.mood_score
- call.sentiment
- call.tags (emotion keywords)
```

#### **3. Audio Recording**
```python
When session.update arrives:
1. Store recording_url in DB
2. Download audio file via httpx
3. Save to audio_recordings/call_{id}.wav
4. Available for download on web UI

Format Support:
- WAV (default from Layercode)
- MP3, M4A, OGG, FLAC (auto-detected)
```

---

## 🎨 Response Quality Features

### **What Makes Responses Feel Human**

1. **Personality ("Echo")**
   - Consistent identity across modes
   - Uses "I" and "you" naturally
   - Has opinions and reactions

2. **Conversational Fillers**
   - "You know", "I mean", "honestly"
   - "Okay but", "So", "Yeah"
   - Natural speech patterns

3. **Varied Vocabulary**
   - "exhausted" not always "tired"
   - "awful" not always "difficult"
   - Specific > generic words

4. **Natural Questions**
   - ✅ "What happened?"
   - ❌ "Can you tell me more about what occurred?"
   - Short, curious, genuine

5. **Emotional Specificity**
   - ✅ "That must've felt awful"
   - ❌ "That must have been challenging for you"
   - Real words, not therapy-speak

6. **Length Variation**
   - Sometimes: "Yeah, I get it."
   - Sometimes: "Wow, that's a lot to process. How are you holding up with all of that?"
   - Not always the same length

7. **Random Welcome Messages**
   - 4 different greetings
   - Prevents "Welcome to Echo Diary" every time
   - Feels fresh each call

---

## 🔧 Technical Implementation

### **Key Files**

```
app/services/openai_service.py
└─ generate_response()
   ├─ _get_system_prompt(mode)    → Returns personality prompt
   ├─ Build message history         → Last 3 turns + current
   ├─ Call GPT with settings        → temp=0.9, penalties, etc
   └─ Return natural response

app/routes/layercode.py
└─ handle_message()
   ├─ Get session from Redis
   ├─ Store user transcript
   ├─ Get context
   ├─ Call openai_service
   ├─ Store AI response
   ├─ Update context
   └─ Stream via SSE

app/redis_client.py
└─ add_turn_to_context()
   ├─ Get current session
   ├─ Append new turn
   ├─ Prune to last 6 turns (3 user + 3 agent)
   └─ Save back to Redis
```

---

## 📈 Performance Metrics

```
Response Generation Time:
- Redis context retrieval: ~5-10ms
- GPT API call: ~1-3 seconds
- Database storage: ~20-50ms
- SSE stream send: ~10ms
Total: ~1.5-3.5 seconds

Context Window:
- 3 turns = ~300-500 tokens
- Keeps GPT focused
- Fast, relevant responses

Memory Usage:
- Redis per session: ~1KB
- Database per call: ~5-10KB
- Scales well to 1000s of users
```

---

## 🎯 Why This Works

### **Conversation Quality**
✅ High temperature = human-like spontaneity  
✅ Personality prompts = consistent character  
✅ Short responses = voice-friendly  
✅ Context window = remembers enough without confusion

### **Technical Performance**
✅ Redis = fast context access  
✅ SQLite = complete history  
✅ SSE streaming = real-time feel  
✅ Background processing = doesn't slow calls

### **User Experience**
✅ Feels like talking to a friend  
✅ Not robotic or scripted  
✅ Appropriate responses per mode  
✅ Natural conversation flow

---

## 💡 Key Insights

1. **Temperature Matters**: 0.7 = robotic, 0.9 = human
2. **Prompts > Fine-tuning**: Good prompts beat model training
3. **Context Size**: More ≠ better (3 turns is sweet spot)
4. **Personality Consistency**: "Echo" across all responses
5. **Voice-First Design**: Short, natural sentences for TTS
6. **Real-Time Feel**: SSE streaming + fast Redis
7. **Emotional Intelligence**: Specific words > generic therapy-speak

---

**TL;DR:** Echo feels human because we use high temperature (0.9), personality-rich prompts, natural language patterns, and only remember the last 3 conversation turns. The backend is fast (Redis for context) and thorough (SQLite for history). Every response is generated fresh by GPT with emotional intelligence built into the system prompt.

