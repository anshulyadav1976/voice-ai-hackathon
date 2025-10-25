-- EchoDiary D1 Database Schema
-- Run with: wrangler d1 execute echodiary_db --file=./schema.sql

-- Users table
CREATE TABLE IF NOT EXISTS users (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    phone_number TEXT UNIQUE NOT NULL,
    name TEXT,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    updated_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    preferred_mode TEXT DEFAULT 'reassure',
    baseline_mood REAL DEFAULT 5.0
);

CREATE INDEX idx_users_phone ON users(phone_number);

-- Calls table
CREATE TABLE IF NOT EXISTS calls (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER NOT NULL,
    call_sid TEXT UNIQUE NOT NULL,
    from_number TEXT NOT NULL,
    start_time DATETIME DEFAULT CURRENT_TIMESTAMP,
    end_time DATETIME,
    duration_seconds INTEGER,
    mode TEXT DEFAULT 'reassure',
    mood_score REAL,
    sentiment TEXT,
    audio_url TEXT,
    audio_duration INTEGER,
    summary TEXT,
    tags TEXT,  -- JSON array as TEXT
    FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
);

CREATE INDEX idx_calls_user ON calls(user_id);
CREATE INDEX idx_calls_sid ON calls(call_sid);
CREATE INDEX idx_calls_time ON calls(start_time DESC);

-- Transcripts table
CREATE TABLE IF NOT EXISTS transcripts (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    call_id INTEGER NOT NULL,
    timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
    speaker TEXT NOT NULL,  -- 'user' or 'agent'
    text TEXT NOT NULL,
    confidence REAL,
    emotion TEXT,
    FOREIGN KEY (call_id) REFERENCES calls(id) ON DELETE CASCADE
);

CREATE INDEX idx_transcripts_call ON transcripts(call_id);
CREATE INDEX idx_transcripts_time ON transcripts(timestamp);

-- Entities table (Knowledge Graph nodes)
CREATE TABLE IF NOT EXISTS entities (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER NOT NULL,
    name TEXT NOT NULL,
    entity_type TEXT NOT NULL,  -- Person, Place, Org, Topic, Emotion
    first_mentioned DATETIME DEFAULT CURRENT_TIMESTAMP,
    last_mentioned DATETIME DEFAULT CURRENT_TIMESTAMP,
    mention_count INTEGER DEFAULT 1,
    properties TEXT,  -- JSON as TEXT
    FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
);

CREATE INDEX idx_entities_user ON entities(user_id);
CREATE INDEX idx_entities_type ON entities(entity_type);
CREATE UNIQUE INDEX idx_entities_user_name_type ON entities(user_id, name, entity_type);

-- Relations table (Knowledge Graph edges)
CREATE TABLE IF NOT EXISTS relations (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    call_id INTEGER NOT NULL,
    entity1_id INTEGER NOT NULL,
    entity2_id INTEGER NOT NULL,
    relation_type TEXT NOT NULL,  -- met_with, argued_with, worked_on, felt, went_to
    timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
    context TEXT,
    FOREIGN KEY (call_id) REFERENCES calls(id) ON DELETE CASCADE,
    FOREIGN KEY (entity1_id) REFERENCES entities(id) ON DELETE CASCADE,
    FOREIGN KEY (entity2_id) REFERENCES entities(id) ON DELETE CASCADE
);

CREATE INDEX idx_relations_call ON relations(call_id);
CREATE INDEX idx_relations_entity1 ON relations(entity1_id);
CREATE INDEX idx_relations_entity2 ON relations(entity2_id);

-- Check-ins table
CREATE TABLE IF NOT EXISTS checkins (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER NOT NULL,
    call_id INTEGER,
    scheduled_time DATETIME NOT NULL,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    status TEXT DEFAULT 'pending',  -- pending, completed, failed, cancelled
    completed_at DATETIME,
    reason TEXT,
    message TEXT,
    delivery_method TEXT DEFAULT 'sms',  -- sms or call
    twilio_sid TEXT,
    success INTEGER DEFAULT 0,
    FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE,
    FOREIGN KEY (call_id) REFERENCES calls(id) ON DELETE SET NULL
);

CREATE INDEX idx_checkins_user ON checkins(user_id);
CREATE INDEX idx_checkins_status ON checkins(status);
CREATE INDEX idx_checkins_scheduled ON checkins(scheduled_time);

-- Insert default test user (optional)
-- INSERT INTO users (phone_number, name, preferred_mode) 
-- VALUES ('+1234567890', 'Test User', 'reassure');

