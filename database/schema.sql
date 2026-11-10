-- SQLite schema for lead-explorer-os database
-- Table to store filtered lead records from lead parser

CREATE TABLE IF NOT EXISTS leads (
    id TEXT PRIMARY KEY,
    name TEXT NOT NULL,
    email TEXT NOT NULL,
    phone TEXT NOT NULL,
    industry TEXT NOT NULL,
    region TEXT NOT NULL,
    source TEXT NOT NULL,
    created_at TEXT NOT NULL,
    intent_score REAL NOT NULL,
    interest_level TEXT NOT NULL,
    processed_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(id, source)
);

-- Index for faster lookups on interest level
CREATE INDEX IF NOT EXISTS idx_interest_level ON leads (interest_level);

-- Index for faster lookups on intent score
CREATE INDEX IF NOT EXISTS idx_intent_score ON leads (intent_score);

-- Index for faster lookups on region
CREATE INDEX IF NOT EXISTS idx_region ON leads (region);

-- View for hot leads (high intent score)
CREATE VIEW IF NOT EXISTS hot_leads AS
SELECT * FROM leads WHERE intent_score >= 0.85;

-- View for warm leads (medium intent score)
CREATE VIEW IF NOT EXISTS warm_leads AS
SELECT * FROM leads WHERE intent_score >= 0.65 AND intent_score < 0.85;

-- View for cold leads (low intent score)
CREATE VIEW IF NOT EXISTS cold_leads AS
SELECT * FROM leads WHERE intent_score < 0.65;
