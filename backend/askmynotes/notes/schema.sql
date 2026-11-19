-- The record of which note files are in the notes database, kept in app.db.
-- Every statement is safe to run on every start.

CREATE TABLE IF NOT EXISTS note_files (
    -- "<module short name>/<path inside the module's folder>", e.g. "AFA/Lecture 1.pptx"
    file_id     TEXT PRIMARY KEY,
    module      TEXT NOT NULL,
    file_name   TEXT NOT NULL,
    -- A fingerprint of the file's contents: if it changes, so did the file.
    sha256      TEXT NOT NULL,
    status      TEXT NOT NULL CHECK (status IN ('indexed', 'unreadable')),
    -- For an unreadable file: why it couldn't be read.
    reason      TEXT,
    chunk_count INTEGER NOT NULL DEFAULT 0,
    synced_at   TEXT NOT NULL
);
