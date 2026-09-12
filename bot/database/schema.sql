-- =============================================================================
-- Horizon Devs Database Schema (PostgreSQL / Supabase)
-- 
-- Run this script in the Supabase SQL Editor:
-- https://app.supabase.com/project/_/sql
-- =============================================================================

-- Enable UUID extension if needed in future
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";

-- -----------------------------------------------------------------------------
-- 1. REPUTATION / KARMA SYSTEM
-- -----------------------------------------------------------------------------
-- Stores aggregated points for users per Discord guild.
-- Discord snowflakes (user_id, guild_id) must be stored as BIGINT.
CREATE TABLE IF NOT EXISTS reputation (
    user_id BIGINT NOT NULL,
    guild_id BIGINT NOT NULL,
    points INTEGER NOT NULL DEFAULT 0,
    last_thanked_at TIMESTAMPTZ,
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    PRIMARY KEY (user_id, guild_id)
);

-- Index for fast leaderboard queries
CREATE INDEX IF NOT EXISTS idx_reputation_leaderboard 
    ON reputation (guild_id, points DESC);

-- Audit log of individual thank/karma awards
CREATE TABLE IF NOT EXISTS reputation_logs (
    id BIGSERIAL PRIMARY KEY,
    from_user_id BIGINT NOT NULL,
    to_user_id BIGINT NOT NULL,
    guild_id BIGINT NOT NULL,
    reason TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_reputation_logs_user 
    ON reputation_logs (guild_id, to_user_id, created_at DESC);

-- -----------------------------------------------------------------------------
-- 2. PROJECT SHOWCASE SYSTEM
-- -----------------------------------------------------------------------------
-- Stores projects submitted by members for community feedback and discovery.
CREATE TABLE IF NOT EXISTS showcases (
    id BIGSERIAL PRIMARY KEY,
    message_id BIGINT UNIQUE,
    channel_id BIGINT,
    author_id BIGINT NOT NULL,
    guild_id BIGINT NOT NULL,
    title VARCHAR(255) NOT NULL,
    description TEXT NOT NULL,
    tech_stack VARCHAR(255) NOT NULL,
    github_url TEXT,
    demo_url TEXT,
    upvotes INTEGER NOT NULL DEFAULT 0,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_showcases_guild_author 
    ON showcases (guild_id, author_id);

CREATE INDEX IF NOT EXISTS idx_showcases_guild_created 
    ON showcases (guild_id, created_at DESC);

-- Tracks member upvotes to enforce one vote per user per showcase
CREATE TABLE IF NOT EXISTS showcase_votes (
    showcase_id BIGINT NOT NULL REFERENCES showcases(id) ON DELETE CASCADE,
    user_id BIGINT NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    PRIMARY KEY (showcase_id, user_id)
);

-- -----------------------------------------------------------------------------
-- 3. HELPFUL VIEWS
-- -----------------------------------------------------------------------------
-- View for top dev contributors per server
CREATE OR REPLACE VIEW top_developers AS
SELECT 
    guild_id,
    user_id,
    points,
    last_thanked_at
FROM reputation
ORDER BY points DESC;

-- -----------------------------------------------------------------------------
-- 4. ROW LEVEL SECURITY (RLS) POLICIES
-- -----------------------------------------------------------------------------
-- Enables RLS on all tables to satisfy Supabase security standards.
-- Backend bot processes using the 'service_role' key bypass RLS automatically.
-- For requests using the 'anon' key, policies below grant access.
ALTER TABLE reputation ENABLE ROW LEVEL SECURITY;
ALTER TABLE reputation_logs ENABLE ROW LEVEL SECURITY;
ALTER TABLE showcases ENABLE ROW LEVEL SECURITY;
ALTER TABLE showcase_votes ENABLE ROW LEVEL SECURITY;

DO $$ 
BEGIN
    -- Reputation policies
    IF NOT EXISTS (SELECT 1 FROM pg_policies WHERE policyname = 'Public read reputation') THEN
        CREATE POLICY "Public read reputation" ON reputation FOR SELECT USING (true);
    END IF;
    IF NOT EXISTS (SELECT 1 FROM pg_policies WHERE policyname = 'Full access reputation') THEN
        CREATE POLICY "Full access reputation" ON reputation FOR ALL USING (true);
    END IF;

    -- Reputation logs policies
    IF NOT EXISTS (SELECT 1 FROM pg_policies WHERE policyname = 'Public read reputation_logs') THEN
        CREATE POLICY "Public read reputation_logs" ON reputation_logs FOR SELECT USING (true);
    END IF;
    IF NOT EXISTS (SELECT 1 FROM pg_policies WHERE policyname = 'Full access reputation_logs') THEN
        CREATE POLICY "Full access reputation_logs" ON reputation_logs FOR ALL USING (true);
    END IF;

    -- Showcases policies
    IF NOT EXISTS (SELECT 1 FROM pg_policies WHERE policyname = 'Public read showcases') THEN
        CREATE POLICY "Public read showcases" ON showcases FOR SELECT USING (true);
    END IF;
    IF NOT EXISTS (SELECT 1 FROM pg_policies WHERE policyname = 'Full access showcases') THEN
        CREATE POLICY "Full access showcases" ON showcases FOR ALL USING (true);
    END IF;

    -- Showcase votes policies
    IF NOT EXISTS (SELECT 1 FROM pg_policies WHERE policyname = 'Public read showcase_votes') THEN
        CREATE POLICY "Public read showcase_votes" ON showcase_votes FOR SELECT USING (true);
    END IF;
    IF NOT EXISTS (SELECT 1 FROM pg_policies WHERE policyname = 'Full access showcase_votes') THEN
        CREATE POLICY "Full access showcase_votes" ON showcase_votes FOR ALL USING (true);
    END IF;
END $$;
