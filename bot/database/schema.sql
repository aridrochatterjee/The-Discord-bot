-- =============================================================================
-- Horizon Devs Database Schema
-- PostgreSQL / Supabase
-- =============================================================================
--
-- Main systems:
--
--   1. Reputation / Dev Karma
--   2. Project Showcases
--   3. Developer Challenges
--   4. Dev Karma Bounties
--
-- Discord snowflake IDs are stored as BIGINT.
--
-- This file is the canonical database schema for Horizon Devs.
-- =============================================================================


-- =============================================================================
-- 0. EXTENSIONS
-- =============================================================================

CREATE EXTENSION IF NOT EXISTS "uuid-ossp";


-- =============================================================================
-- 1. REPUTATION / DEV KARMA
-- =============================================================================

-- -----------------------------------------------------------------------------
-- Current aggregated Karma balance for each user in each guild.
-- -----------------------------------------------------------------------------

CREATE TABLE IF NOT EXISTS reputation (
    user_id BIGINT NOT NULL,
    guild_id BIGINT NOT NULL,

    points INTEGER NOT NULL DEFAULT 0
        CHECK (points >= 0),

    last_thanked_at TIMESTAMPTZ,

    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),

    PRIMARY KEY (user_id, guild_id)
);


-- -----------------------------------------------------------------------------
-- Reputation leaderboard index.
-- -----------------------------------------------------------------------------

CREATE INDEX IF NOT EXISTS idx_reputation_leaderboard
ON reputation (
    guild_id,
    points DESC,
    updated_at DESC
);


-- -----------------------------------------------------------------------------
-- Reputation audit log.
--
-- log_type:
--
--   THANK  = normal /thank action
--   REMOVE = admin removed Karma
--   RESET  = server Karma reset
--
-- amount stores how many Karma points were affected.
-- -----------------------------------------------------------------------------

CREATE TABLE IF NOT EXISTS reputation_logs (
    id BIGSERIAL PRIMARY KEY,

    from_user_id BIGINT NOT NULL,
    to_user_id BIGINT NOT NULL,

    guild_id BIGINT NOT NULL,

    amount INTEGER NOT NULL DEFAULT 1
        CHECK (amount > 0),

    log_type TEXT NOT NULL DEFAULT 'THANK'
        CHECK (
            log_type IN (
                'THANK',
                'REMOVE',
                'RESET'
            )
        ),

    reason TEXT,

    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);


-- -----------------------------------------------------------------------------
-- Reputation history lookup.
-- -----------------------------------------------------------------------------

CREATE INDEX IF NOT EXISTS idx_reputation_logs_user
ON reputation_logs (
    guild_id,
    to_user_id,
    created_at DESC
);


-- -----------------------------------------------------------------------------
-- /thank cooldown lookup.
--
-- Only THANK records participate in the cooldown.
-- -----------------------------------------------------------------------------

CREATE INDEX IF NOT EXISTS idx_reputation_logs_cooldown
ON reputation_logs (
    guild_id,
    from_user_id,
    to_user_id,
    created_at DESC
)
WHERE log_type = 'THANK';


-- -----------------------------------------------------------------------------
-- Administrative/action history lookup.
-- -----------------------------------------------------------------------------

CREATE INDEX IF NOT EXISTS idx_reputation_logs_type
ON reputation_logs (
    guild_id,
    log_type,
    created_at DESC
);


-- =============================================================================
-- 2. PROJECT SHOWCASE SYSTEM
-- =============================================================================

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

    upvotes INTEGER NOT NULL DEFAULT 0
        CHECK (upvotes >= 0),

    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),

    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);


-- -----------------------------------------------------------------------------
-- Showcase author lookup.
-- -----------------------------------------------------------------------------

CREATE INDEX IF NOT EXISTS idx_showcases_guild_author
ON showcases (
    guild_id,
    author_id
);


-- -----------------------------------------------------------------------------
-- Showcase creation/date lookup.
-- -----------------------------------------------------------------------------

CREATE INDEX IF NOT EXISTS idx_showcases_guild_created
ON showcases (
    guild_id,
    created_at DESC
);


-- -----------------------------------------------------------------------------
-- One vote per user per showcase.
-- -----------------------------------------------------------------------------

CREATE TABLE IF NOT EXISTS showcase_votes (
    showcase_id BIGINT NOT NULL
        REFERENCES showcases(id)
        ON DELETE CASCADE,

    user_id BIGINT NOT NULL,

    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),

    PRIMARY KEY (
        showcase_id,
        user_id
    )
);


-- -----------------------------------------------------------------------------
-- Showcase vote lookup.
-- -----------------------------------------------------------------------------

CREATE INDEX IF NOT EXISTS idx_showcase_votes_user
ON showcase_votes (
    user_id,
    created_at DESC
);


-- =============================================================================
-- 3. DEVELOPER CHALLENGES
-- =============================================================================

CREATE TABLE IF NOT EXISTS challenges (
    id BIGSERIAL PRIMARY KEY,

    guild_id BIGINT NOT NULL,

    channel_id BIGINT NOT NULL,

    message_id BIGINT UNIQUE,

    thread_id BIGINT,

    author_id BIGINT NOT NULL,

    day_number INTEGER
        CHECK (
            day_number IS NULL
            OR day_number > 0
        ),

    title TEXT NOT NULL,

    description TEXT NOT NULL,

    rules TEXT,

    easy_points INTEGER NOT NULL DEFAULT 5
        CHECK (easy_points >= 0),

    medium_points INTEGER NOT NULL DEFAULT 10
        CHECK (medium_points >= 0),

    hard_points INTEGER NOT NULL DEFAULT 15
        CHECK (hard_points >= 0),

    deadline TIMESTAMPTZ,

    is_active BOOLEAN NOT NULL DEFAULT TRUE,

    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);


-- -----------------------------------------------------------------------------
-- Active challenge lookup.
-- -----------------------------------------------------------------------------

CREATE INDEX IF NOT EXISTS idx_challenges_active
ON challenges (
    guild_id,
    is_active,
    created_at DESC
);


-- -----------------------------------------------------------------------------
-- Challenge submissions.
-- -----------------------------------------------------------------------------

CREATE TABLE IF NOT EXISTS challenge_submissions (
    id BIGSERIAL PRIMARY KEY,

    challenge_id BIGINT NOT NULL
        REFERENCES challenges(id)
        ON DELETE CASCADE,

    guild_id BIGINT NOT NULL,

    user_id BIGINT NOT NULL,

    github_url TEXT NOT NULL,

    demo_url TEXT,

    difficulty_tier TEXT NOT NULL DEFAULT 'Easy'
        CHECK (
            difficulty_tier IN (
                'Easy',
                'Medium',
                'Hard'
            )
        ),

    notes TEXT,

    awarded_points INTEGER NOT NULL DEFAULT 0
        CHECK (awarded_points >= 0),

    status TEXT NOT NULL DEFAULT 'SUBMITTED'
        CHECK (
            status IN (
                'SUBMITTED',
                'APPROVED',
                'REJECTED',
                'CANCELLED'
            )
        ),

    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),

    UNIQUE (
        challenge_id,
        user_id
    )
);


-- -----------------------------------------------------------------------------
-- Challenge submission lookup by user.
-- -----------------------------------------------------------------------------

CREATE INDEX IF NOT EXISTS idx_challenge_submissions_user
ON challenge_submissions (
    guild_id,
    user_id,
    created_at DESC
);


-- -----------------------------------------------------------------------------
-- Challenge submission lookup by challenge.
-- -----------------------------------------------------------------------------

CREATE INDEX IF NOT EXISTS idx_challenge_submissions_challenge
ON challenge_submissions (
    challenge_id,
    created_at DESC
);


-- -----------------------------------------------------------------------------
-- Challenge status lookup.
-- -----------------------------------------------------------------------------

CREATE INDEX IF NOT EXISTS idx_challenge_submissions_status
ON challenge_submissions (
    guild_id,
    status,
    created_at DESC
);


-- =============================================================================
-- 4. DEV KARMA BOUNTY SYSTEM
-- =============================================================================

CREATE TABLE IF NOT EXISTS bounties (
    id BIGSERIAL PRIMARY KEY,

    guild_id BIGINT NOT NULL,

    channel_id BIGINT NOT NULL,

    message_id BIGINT UNIQUE,

    thread_id BIGINT,

    creator_id BIGINT NOT NULL,

    title TEXT NOT NULL,

    description TEXT NOT NULL,

    reward_karma INTEGER NOT NULL
        CHECK (reward_karma > 0),

    status TEXT NOT NULL DEFAULT 'OPEN'
        CHECK (
            status IN (
                'OPEN',
                'CLAIMED',
                'COMPLETED',
                'CANCELLED'
            )
        ),

    solver_id BIGINT,

    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),

    resolved_at TIMESTAMPTZ
);


-- -----------------------------------------------------------------------------
-- Bounty status lookup.
-- -----------------------------------------------------------------------------

CREATE INDEX IF NOT EXISTS idx_bounties_guild_status
ON bounties (
    guild_id,
    status,
    created_at DESC
);


-- -----------------------------------------------------------------------------
-- Bounty creator lookup.
-- -----------------------------------------------------------------------------

CREATE INDEX IF NOT EXISTS idx_bounties_creator
ON bounties (
    guild_id,
    creator_id,
    created_at DESC
);


-- -----------------------------------------------------------------------------
-- Bounty solver lookup.
-- -----------------------------------------------------------------------------

CREATE INDEX IF NOT EXISTS idx_bounties_solver
ON bounties (
    guild_id,
    solver_id,
    created_at DESC
);


-- =============================================================================
-- 5. TOP DEVELOPERS VIEW
-- =============================================================================

CREATE OR REPLACE VIEW top_developers AS
SELECT
    guild_id,
    user_id,
    points,
    last_thanked_at,
    updated_at
FROM reputation
WHERE points > 0
ORDER BY
    guild_id,
    points DESC,
    updated_at ASC;


-- =============================================================================
-- 6. SHOWCASE UPDATED_AT TRIGGER
-- =============================================================================

-- -----------------------------------------------------------------------------
-- Automatically updates showcases.updated_at whenever a showcase changes.
-- -----------------------------------------------------------------------------

CREATE OR REPLACE FUNCTION update_showcase_updated_at()
RETURNS TRIGGER
LANGUAGE plpgsql
AS $$
BEGIN
    NEW.updated_at = NOW();

    RETURN NEW;
END;
$$;


DROP TRIGGER IF EXISTS trg_showcases_updated_at
ON showcases;


CREATE TRIGGER trg_showcases_updated_at
BEFORE UPDATE ON showcases
FOR EACH ROW
EXECUTE FUNCTION update_showcase_updated_at();


-- =============================================================================
-- 7. REPUTATION UPDATED_AT TRIGGER
-- =============================================================================

-- -----------------------------------------------------------------------------
-- Automatically updates reputation.updated_at whenever Karma changes.
-- -----------------------------------------------------------------------------

CREATE OR REPLACE FUNCTION update_reputation_updated_at()
RETURNS TRIGGER
LANGUAGE plpgsql
AS $$
BEGIN
    NEW.updated_at = NOW();

    RETURN NEW;
END;
$$;


DROP TRIGGER IF EXISTS trg_reputation_updated_at
ON reputation;


CREATE TRIGGER trg_reputation_updated_at
BEFORE UPDATE ON reputation
FOR EACH ROW
EXECUTE FUNCTION update_reputation_updated_at();


-- =============================================================================
-- 8. ROW LEVEL SECURITY
-- =============================================================================

ALTER TABLE reputation ENABLE ROW LEVEL SECURITY;

ALTER TABLE reputation_logs ENABLE ROW LEVEL SECURITY;

ALTER TABLE showcases ENABLE ROW LEVEL SECURITY;

ALTER TABLE showcase_votes ENABLE ROW LEVEL SECURITY;

ALTER TABLE challenges ENABLE ROW LEVEL SECURITY;

ALTER TABLE challenge_submissions ENABLE ROW LEVEL SECURITY;

ALTER TABLE bounties ENABLE ROW LEVEL SECURITY;


-- =============================================================================
-- 9. RLS POLICIES
-- =============================================================================

-- -----------------------------------------------------------------------------
-- REPUTATION
-- -----------------------------------------------------------------------------

DROP POLICY IF EXISTS "Public read reputation"
ON reputation;


CREATE POLICY "Public read reputation"
ON reputation
FOR SELECT
USING (true);


DROP POLICY IF EXISTS "Service role full access reputation"
ON reputation;


CREATE POLICY "Service role full access reputation"
ON reputation
FOR ALL
TO service_role
USING (true)
WITH CHECK (true);


-- -----------------------------------------------------------------------------
-- REPUTATION LOGS
-- -----------------------------------------------------------------------------

DROP POLICY IF EXISTS "Public read reputation logs"
ON reputation_logs;


CREATE POLICY "Public read reputation logs"
ON reputation_logs
FOR SELECT
USING (true);


DROP POLICY IF EXISTS "Service role full access reputation logs"
ON reputation_logs;


CREATE POLICY "Service role full access reputation logs"
ON reputation_logs
FOR ALL
TO service_role
USING (true)
WITH CHECK (true);


-- -----------------------------------------------------------------------------
-- SHOWCASES
-- -----------------------------------------------------------------------------

DROP POLICY IF EXISTS "Public read showcases"
ON showcases;


CREATE POLICY "Public read showcases"
ON showcases
FOR SELECT
USING (true);


DROP POLICY IF EXISTS "Service role full access showcases"
ON showcases;


CREATE POLICY "Service role full access showcases"
ON showcases
FOR ALL
TO service_role
USING (true)
WITH CHECK (true);


-- -----------------------------------------------------------------------------
-- SHOWCASE VOTES
-- -----------------------------------------------------------------------------

DROP POLICY IF EXISTS "Public read showcase votes"
ON showcase_votes;


CREATE POLICY "Public read showcase votes"
ON showcase_votes
FOR SELECT
USING (true);


DROP POLICY IF EXISTS "Service role full access showcase votes"
ON showcase_votes;


CREATE POLICY "Service role full access showcase votes"
ON showcase_votes
FOR ALL
TO service_role
USING (true)
WITH CHECK (true);


-- -----------------------------------------------------------------------------
-- CHALLENGES
-- -----------------------------------------------------------------------------

DROP POLICY IF EXISTS "Public read challenges"
ON challenges;


CREATE POLICY "Public read challenges"
ON challenges
FOR SELECT
USING (true);


DROP POLICY IF EXISTS "Service role full access challenges"
ON challenges;


CREATE POLICY "Service role full access challenges"
ON challenges
FOR ALL
TO service_role
USING (true)
WITH CHECK (true);


-- -----------------------------------------------------------------------------
-- CHALLENGE SUBMISSIONS
-- -----------------------------------------------------------------------------

DROP POLICY IF EXISTS "Public read challenge submissions"
ON challenge_submissions;


CREATE POLICY "Public read challenge submissions"
ON challenge_submissions
FOR SELECT
USING (true);


DROP POLICY IF EXISTS "Service role full access challenge submissions"
ON challenge_submissions;


CREATE POLICY "Service role full access challenge submissions"
ON challenge_submissions
FOR ALL
TO service_role
USING (true)
WITH CHECK (true);


-- -----------------------------------------------------------------------------
-- BOUNTIES
-- -----------------------------------------------------------------------------

DROP POLICY IF EXISTS "Public read bounties"
ON bounties;


CREATE POLICY "Public read bounties"
ON bounties
FOR SELECT
USING (true);


DROP POLICY IF EXISTS "Service role full access bounties"
ON bounties;


CREATE POLICY "Service role full access bounties"
ON bounties
FOR ALL
TO service_role
USING (true)
WITH CHECK (true);


-- =============================================================================
-- 10. EXISTING REPUTATION TABLE COMPATIBILITY
-- =============================================================================

-- -----------------------------------------------------------------------------
-- These columns were added after the original reputation_logs design.
--
-- IF the table already exists, these statements add the missing columns
-- without deleting existing reputation history.
-- -----------------------------------------------------------------------------

ALTER TABLE reputation_logs
ADD COLUMN IF NOT EXISTS amount INTEGER NOT NULL DEFAULT 1;


ALTER TABLE reputation_logs
ADD COLUMN IF NOT EXISTS log_type TEXT NOT NULL DEFAULT 'THANK';


-- =============================================================================
-- 11. REPUTATION CONSTRAINT COMPATIBILITY
-- =============================================================================

-- -----------------------------------------------------------------------------
-- PostgreSQL does not support:
--
--     ADD CONSTRAINT IF NOT EXISTS
--
-- so constraints are checked through pg_constraint.
-- -----------------------------------------------------------------------------

DO $$
BEGIN

    -- -------------------------------------------------------------------------
    -- amount > 0
    -- -------------------------------------------------------------------------

    IF NOT EXISTS (
        SELECT 1
        FROM pg_constraint
        WHERE conname = 'reputation_logs_amount_positive'
          AND conrelid = 'public.reputation_logs'::regclass
    ) THEN

        ALTER TABLE reputation_logs
        ADD CONSTRAINT reputation_logs_amount_positive
        CHECK (amount > 0);

    END IF;


    -- -------------------------------------------------------------------------
    -- Valid log types
    -- -------------------------------------------------------------------------

    IF NOT EXISTS (
        SELECT 1
        FROM pg_constraint
        WHERE conname = 'reputation_logs_log_type_valid'
          AND conrelid = 'public.reputation_logs'::regclass
    ) THEN

        ALTER TABLE reputation_logs
        ADD CONSTRAINT reputation_logs_log_type_valid
        CHECK (
            log_type IN (
                'THANK',
                'REMOVE',
                'RESET'
            )
        );

    END IF;

END
$$;


-- =============================================================================
-- 12. FINAL REPUTATION INDEXES
-- =============================================================================

CREATE INDEX IF NOT EXISTS idx_reputation_guild_points
ON reputation (
    guild_id,
    points DESC
);


CREATE INDEX IF NOT EXISTS idx_reputation_user_guild
ON reputation (
    user_id,
    guild_id
);


-- =============================================================================
-- 13. FINAL SHOWCASE INDEXES
-- =============================================================================

CREATE INDEX IF NOT EXISTS idx_showcases_guild
ON showcases (
    guild_id
);


-- =============================================================================
-- 14. FINAL CHALLENGE INDEXES
-- =============================================================================

CREATE INDEX IF NOT EXISTS idx_challenges_guild
ON challenges (
    guild_id,
    created_at DESC
);


-- =============================================================================
-- 15. FINAL BOUNTY INDEXES
-- =============================================================================

CREATE INDEX IF NOT EXISTS idx_bounties_guild
ON bounties (
    guild_id,
    created_at DESC
);


-- =============================================================================
-- DONE
-- =============================================================================
--
-- Tables:
--
--   reputation
--   reputation_logs
--
--   showcases
--   showcase_votes
--
--   challenges
--   challenge_submissions
--
--   bounties
--
-- Views:
--
--   top_developers
--
-- Functions:
--
--   update_showcase_updated_at()
--   update_reputation_updated_at()
--
-- Supported Karma operations:
--
--   /thank
--   /karma
--   /leaderboard
--   /remove_karma
--   /karma_reset
--   /leaderboard_reset
--
-- =============================================================================