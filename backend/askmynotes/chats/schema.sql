-- Chat storage. Every statement is safe to run on every start.

CREATE TABLE IF NOT EXISTS chats (
    id           TEXT PRIMARY KEY,
    title        TEXT NOT NULL,
    pinned       INTEGER NOT NULL DEFAULT 0,
    created_at   TEXT NOT NULL,
    last_used_at TEXT NOT NULL,
    -- For long chats: a summary of the older messages, and the id of the
    -- last message it covers. Only what the model is sent changes; the
    -- messages themselves are all kept.
    summary          TEXT,
    summarised_up_to INTEGER NOT NULL DEFAULT 0
);

CREATE TABLE IF NOT EXISTS messages (
    id         INTEGER PRIMARY KEY AUTOINCREMENT,
    chat_id    TEXT NOT NULL REFERENCES chats(id) ON DELETE CASCADE,
    role       TEXT NOT NULL CHECK (role IN ('user', 'assistant')),
    content    TEXT NOT NULL,
    status     TEXT NOT NULL DEFAULT 'complete'
               CHECK (status IN ('complete', 'stopped', 'error')),
    error      TEXT,
    sources    TEXT,  -- JSON list of the slides and pages a notes answer used
    web_sources TEXT,  -- JSON list of the web pages a web answer cited or searched
    web_searches TEXT,  -- JSON list of what the web searches asked for
    tool_runs   TEXT,  -- JSON list of the calculations and Python runs an answer was worked out with
    created_at TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS messages_by_chat ON messages(chat_id, id);

CREATE TABLE IF NOT EXISTS message_images (
    id         INTEGER PRIMARY KEY AUTOINCREMENT,
    message_id INTEGER NOT NULL REFERENCES messages(id) ON DELETE CASCADE,
    path       TEXT NOT NULL
);

-- A document (Word, Excel, PowerPoint or PDF) attached to a message. The
-- original file is kept under data/uploads/; `text` is what the model reads.
CREATE TABLE IF NOT EXISTS message_documents (
    id         INTEGER PRIMARY KEY AUTOINCREMENT,
    message_id INTEGER NOT NULL REFERENCES messages(id) ON DELETE CASCADE,
    name       TEXT NOT NULL,
    path       TEXT NOT NULL,
    kind       TEXT NOT NULL,
    count      INTEGER,
    text       TEXT NOT NULL
);

-- A file that Python made for an answer. The file is kept under
-- data/uploads/<chat id>/generated/ and is deleted with its message.
CREATE TABLE IF NOT EXISTS message_files (
    id         INTEGER PRIMARY KEY AUTOINCREMENT,
    message_id INTEGER NOT NULL REFERENCES messages(id) ON DELETE CASCADE,
    name       TEXT NOT NULL,
    path       TEXT NOT NULL,
    size       INTEGER NOT NULL,
    media_type TEXT NOT NULL
);

-- Full-text search over chat titles and message text. A title has no
-- message_id; a message row has one. Triggers keep it in step with the
-- tables above, so no other code has to remember to update it.
CREATE VIRTUAL TABLE IF NOT EXISTS chat_search USING fts5(
    chat_id UNINDEXED,
    message_id UNINDEXED,
    text
);

CREATE TRIGGER IF NOT EXISTS chat_search_chat_added AFTER INSERT ON chats
BEGIN
    INSERT INTO chat_search(chat_id, message_id, text)
    VALUES (new.id, NULL, new.title);
END;

CREATE TRIGGER IF NOT EXISTS chat_search_chat_renamed
AFTER UPDATE OF title ON chats
BEGIN
    UPDATE chat_search SET text = new.title
    WHERE chat_id = new.id AND message_id IS NULL;
END;

CREATE TRIGGER IF NOT EXISTS chat_search_chat_deleted AFTER DELETE ON chats
BEGIN
    DELETE FROM chat_search WHERE chat_id = old.id;
END;

CREATE TRIGGER IF NOT EXISTS chat_search_message_added AFTER INSERT ON messages
BEGIN
    INSERT INTO chat_search(chat_id, message_id, text)
    VALUES (new.chat_id, new.id, new.content);
END;

CREATE TRIGGER IF NOT EXISTS chat_search_message_edited
AFTER UPDATE OF content ON messages
BEGIN
    UPDATE chat_search SET text = new.content WHERE message_id = new.id;
END;

CREATE TRIGGER IF NOT EXISTS chat_search_message_deleted
AFTER DELETE ON messages
BEGIN
    DELETE FROM chat_search WHERE message_id = old.id;
END;
