CREATE TABLE IF NOT EXISTS sessions (
  id TEXT PRIMARY KEY NOT NULL,
  state TEXT NOT NULL CHECK(length(state) <= 1048576),
  version INTEGER NOT NULL DEFAULT 0,
  expires INTEGER NOT NULL
);
CREATE INDEX IF NOT EXISTS sessions_expiry ON sessions(expires);
CREATE TABLE IF NOT EXISTS fx_cache (
  id INTEGER PRIMARY KEY CHECK(id = 1),
  snapshot TEXT NOT NULL,
  fetched INTEGER NOT NULL
);
CREATE TABLE IF NOT EXISTS rate_buckets (
  id TEXT PRIMARY KEY NOT NULL,
  count INTEGER NOT NULL,
  expires INTEGER NOT NULL
);
CREATE INDEX IF NOT EXISTS rate_expiry ON rate_buckets(expires);
