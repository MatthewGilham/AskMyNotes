-- What the app has spent on OpenAI. Every statement is safe to run on every start.

-- One row per model call (or per batch of embeddings). There is deliberately no
-- foreign key to chats: deleting a chat must not delete the money it cost.
CREATE TABLE IF NOT EXISTS api_usage (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    chat_id       TEXT,  -- NULL for a notes update, which belongs to no chat
    kind          TEXT NOT NULL
                  CHECK (kind IN ('reply', 'title', 'summary', 'search', 'notes_update',
                                'web_search', 'python')),
    model         TEXT NOT NULL,
    input_tokens  INTEGER NOT NULL,  -- includes the cached ones
    cached_tokens INTEGER NOT NULL,
    output_tokens INTEGER NOT NULL,
    cost          REAL NOT NULL,     -- US dollars, worked out when the call was made
    estimated     INTEGER NOT NULL DEFAULT 0,
    created_at    TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS api_usage_by_chat ON api_usage(chat_id);

-- When recording began (a single row), so chats from before can say that their
-- earlier costs weren't recorded.
CREATE TABLE IF NOT EXISTS usage_tracking (
    id         INTEGER PRIMARY KEY CHECK (id = 1),
    started_at TEXT NOT NULL
);
