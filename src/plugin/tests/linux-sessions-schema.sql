CREATE TABLE IF NOT EXISTS sessions (
    id TEXT PRIMARY KEY,
    cwd TEXT NOT NULL,
    user_id TEXT NOT NULL,
    title TEXT,
    custom_title TEXT,
    status TEXT NOT NULL DEFAULT 'Pending',
    created_at INTEGER NOT NULL,
    updated_at INTEGER NOT NULL,
    last_activity_at INTEGER,
    deleted_at INTEGER,
    is_playground INTEGER NOT NULL DEFAULT 0,
    source_mode TEXT,
    is_background_automation INTEGER,
    mode TEXT,
    model TEXT,
    expert_id TEXT,
    expert_locale TEXT,
    expert_runtime_identity TEXT,
    expert_marketplace TEXT,
    permission_mode TEXT,
    use_sandbox_cli INTEGER,
    project_id TEXT
);
ALTER TABLE sessions ADD COLUMN plugin_context_json TEXT;
ALTER TABLE sessions ADD COLUMN addon_selection TEXT;
ALTER TABLE sessions ADD COLUMN session_settings TEXT;
ALTER TABLE sessions ADD COLUMN last_user_prompt_expert_selection TEXT;
ALTER TABLE sessions ADD COLUMN context_window INTEGER;
ALTER TABLE sessions ADD COLUMN buddy_snapshot_id TEXT;
ALTER TABLE sessions ADD COLUMN buddy_binding_json TEXT;
ALTER TABLE sessions ADD COLUMN thought_level TEXT;
ALTER TABLE sessions ADD COLUMN transport TEXT NOT NULL DEFAULT 'local';
ALTER TABLE sessions ADD COLUMN conversation_origin TEXT;
ALTER TABLE sessions ADD COLUMN visibility TEXT;
ALTER TABLE sessions ADD COLUMN group_id TEXT;
ALTER TABLE sessions ADD COLUMN group_title TEXT;
ALTER TABLE sessions ADD COLUMN agent_dirty INTEGER;
ALTER TABLE sessions ADD COLUMN agent_dirty_at INTEGER;
ALTER TABLE sessions ADD COLUMN agent_last_synced INTEGER;
ALTER TABLE sessions ADD COLUMN verified_at INTEGER;
ALTER TABLE sessions ADD COLUMN unread INTEGER NOT NULL DEFAULT 0;
