PRAGMA journal_mode=WAL;
PRAGMA foreign_keys=ON;
CREATE TABLE IF NOT EXISTS settings (id INTEGER PRIMARY KEY CHECK(id=1), data TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS products (
 id TEXT PRIMARY KEY, name TEXT NOT NULL, url TEXT NOT NULL, source TEXT NOT NULL,
 facts TEXT NOT NULL, economics TEXT NOT NULL, created_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS experiments (
 id TEXT PRIMARY KEY, product_id TEXT NOT NULL REFERENCES products(id), name TEXT NOT NULL,
 platform TEXT NOT NULL, angle TEXT NOT NULL, audience TEXT NOT NULL, hook TEXT NOT NULL,
 landing_page TEXT NOT NULL, hypothesis TEXT NOT NULL, success_metric TEXT NOT NULL,
 creative TEXT NOT NULL, status TEXT NOT NULL DEFAULT 'draft', created_at TEXT NOT NULL, started_at TEXT
);
CREATE TABLE IF NOT EXISTS events (
 id TEXT PRIMARY KEY, name TEXT NOT NULL, creative_id TEXT REFERENCES experiments(id),
 session_id TEXT NOT NULL, occurred_at TEXT NOT NULL, attribution TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS orders (
 id TEXT PRIMARY KEY, source TEXT NOT NULL, creative_id TEXT REFERENCES experiments(id),
 revenue REAL NOT NULL, contribution REAL NOT NULL, economics_snapshot TEXT NOT NULL,
 occurred_at TEXT NOT NULL, imported_at TEXT NOT NULL, session_id TEXT
);
CREATE TABLE IF NOT EXISTS ad_metrics (
 creative_id TEXT NOT NULL REFERENCES experiments(id), day TEXT NOT NULL,
 spend REAL NOT NULL, impressions INTEGER NOT NULL, clicks INTEGER NOT NULL, source TEXT NOT NULL,
 PRIMARY KEY(creative_id,day)
);
CREATE TABLE IF NOT EXISTS actions (
 id TEXT PRIMARY KEY, title TEXT NOT NULL, kind TEXT NOT NULL, risk TEXT NOT NULL,
 target TEXT NOT NULL, current_value TEXT NOT NULL, proposed_value TEXT NOT NULL,
 reason TEXT NOT NULL, expected_impact TEXT NOT NULL, confidence TEXT NOT NULL,
 status TEXT NOT NULL DEFAULT 'pending', approved_by TEXT, created_at TEXT NOT NULL, updated_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS audit (
 id INTEGER PRIMARY KEY AUTOINCREMENT, action_id TEXT, actor TEXT NOT NULL, operation TEXT NOT NULL,
 before_value TEXT NOT NULL, after_value TEXT NOT NULL, occurred_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS learnings (
 id TEXT PRIMARY KEY, creative_id TEXT NOT NULL REFERENCES experiments(id),
 evidence TEXT NOT NULL, finding TEXT NOT NULL, next_experiment TEXT NOT NULL, created_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS leads (
 id TEXT PRIMARY KEY, email TEXT NOT NULL UNIQUE, source TEXT NOT NULL, relevance TEXT NOT NULL,
 consent_text TEXT NOT NULL, consent_version TEXT NOT NULL, consent_at TEXT NOT NULL,
 status TEXT NOT NULL DEFAULT 'pending_confirmation', token_hash TEXT NOT NULL, confirmed_at TEXT
);
