"""Database schema definitions and initialization scripts for OfflineMind."""

SCHEMA_SQL = """
-- Core Knowledge Facts Table
CREATE TABLE IF NOT EXISTS facts (
    id TEXT PRIMARY KEY,
    entity TEXT NOT NULL,
    attribute TEXT NOT NULL,
    value TEXT NOT NULL,
    category TEXT DEFAULT 'general',
    confidence REAL DEFAULT 1.0,
    source TEXT NOT NULL,
    source_priority INTEGER DEFAULT 50,
    version INTEGER DEFAULT 1,
    status TEXT DEFAULT 'ACTIVE',
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    content_hash TEXT,
    CONSTRAINT chk_confidence CHECK (confidence >= 0.0 AND confidence <= 1.0),
    CONSTRAINT chk_status CHECK (status IN ('ACTIVE', 'ARCHIVED', 'NEEDS_REVIEW'))
);

CREATE INDEX IF NOT EXISTS idx_facts_entity_attr ON facts(entity, attribute);
CREATE INDEX IF NOT EXISTS idx_facts_status ON facts(status);
CREATE INDEX IF NOT EXISTS idx_facts_category ON facts(category);

-- Fact Version History Table (Immutable Audit Log)
CREATE TABLE IF NOT EXISTS fact_history (
    history_id INTEGER PRIMARY KEY AUTOINCREMENT,
    fact_id TEXT NOT NULL,
    entity TEXT NOT NULL,
    attribute TEXT NOT NULL,
    old_value TEXT,
    new_value TEXT NOT NULL,
    source TEXT NOT NULL,
    version INTEGER NOT NULL,
    change_reason TEXT,
    timestamp TEXT NOT NULL,
    FOREIGN KEY (fact_id) REFERENCES facts(id) ON DELETE CASCADE
);

CREATE INDEX IF NOT EXISTS idx_history_fact_id ON fact_history(fact_id);
CREATE INDEX IF NOT EXISTS idx_history_entity_attr ON fact_history(entity, attribute);
CREATE INDEX IF NOT EXISTS idx_history_timestamp ON fact_history(timestamp);

-- Conflict & Review Queue Table
CREATE TABLE IF NOT EXISTS review_queue (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    fact_id TEXT,
    entity TEXT NOT NULL,
    attribute TEXT NOT NULL,
    current_value TEXT,
    incoming_value TEXT NOT NULL,
    current_source TEXT,
    incoming_source TEXT NOT NULL,
    current_confidence REAL,
    incoming_confidence REAL,
    conflict_reason TEXT NOT NULL,
    status TEXT DEFAULT 'PENDING',
    created_at TEXT NOT NULL,
    resolved_at TEXT,
    resolution_notes TEXT,
    CONSTRAINT chk_review_status CHECK (status IN ('PENDING', 'RESOLVED_ACCEPTED', 'RESOLVED_REJECTED'))
);

CREATE INDEX IF NOT EXISTS idx_review_queue_status ON review_queue(status);

-- Sync Logs Table
CREATE TABLE IF NOT EXISTS sync_logs (
    sync_id TEXT PRIMARY KEY,
    start_time TEXT NOT NULL,
    end_time TEXT,
    status TEXT NOT NULL,
    facts_checked INTEGER DEFAULT 0,
    facts_updated INTEGER DEFAULT 0,
    facts_added INTEGER DEFAULT 0,
    conflicts_detected INTEGER DEFAULT 0,
    error_message TEXT,
    source_url TEXT,
    CONSTRAINT chk_sync_status CHECK (status IN ('IN_PROGRESS', 'SUCCESS', 'FAILED', 'PARTIAL'))
);

CREATE INDEX IF NOT EXISTS idx_sync_logs_start ON sync_logs(start_time);

-- Trusted Sources Configuration Table
CREATE TABLE IF NOT EXISTS trusted_sources (
    id TEXT PRIMARY KEY,
    name TEXT NOT NULL,
    url TEXT NOT NULL UNIQUE,
    source_type TEXT DEFAULT 'JSON',
    priority INTEGER DEFAULT 50,
    last_synced_at TEXT,
    is_active INTEGER DEFAULT 1,
    CONSTRAINT chk_priority CHECK (priority >= 1 AND priority <= 100)
);

-- Full-Text Search (FTS5) Table for Knowledge Retrieval
CREATE VIRTUAL TABLE IF NOT EXISTS facts_fts USING fts5(
    entity,
    attribute,
    value,
    category,
    content='facts',
    content_rowid='rowid'
);

-- Triggers to synchronize facts_fts with facts table
CREATE TRIGGER IF NOT EXISTS facts_ai AFTER INSERT ON facts BEGIN
  INSERT INTO facts_fts(rowid, entity, attribute, value, category) 
  VALUES (new.rowid, new.entity, new.attribute, new.value, new.category);
END;

CREATE TRIGGER IF NOT EXISTS facts_ad AFTER DELETE ON facts BEGIN
  INSERT INTO facts_fts(facts_fts, rowid, entity, attribute, value, category) 
  VALUES ('delete', old.rowid, old.entity, old.attribute, old.value, old.category);
END;

CREATE TRIGGER IF NOT EXISTS facts_au AFTER UPDATE ON facts BEGIN
  INSERT INTO facts_fts(facts_fts, rowid, entity, attribute, value, category) 
  VALUES ('delete', old.rowid, old.entity, old.attribute, old.value, old.category);
  INSERT INTO facts_fts(rowid, entity, attribute, value, category) 
  VALUES (new.rowid, new.entity, new.attribute, new.value, new.category);
END;
"""
