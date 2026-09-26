-- Rover Market Intelligence Schema for Supabase PostgreSQL
-- Idempotent setup: safe to run multiple times

-- 1. Search Sessions
CREATE TABLE IF NOT EXISTS public.search_sessions (
    id               BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    timestamp        TIMESTAMPTZ NOT NULL DEFAULT now(),
    location         TEXT NOT NULL,
    service_type     TEXT NOT NULL,
    radius_km        NUMERIC,
    center_lat       DOUBLE PRECISION,
    center_lng       DOUBLE PRECISION,
    pages_requested  INTEGER NOT NULL,
    pages_completed  INTEGER NOT NULL,
    total_sitters    INTEGER NOT NULL,
    min_price        NUMERIC,
    avg_price        NUMERIC,
    median_price     NUMERIC,
    p25_price        NUMERIC,
    p75_price        NUMERIC,
    max_price        NUMERIC
);

-- 2. Master Sitter Profiles
CREATE TABLE IF NOT EXISTS public.sitters (
    id               BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    member_id        TEXT NOT NULL UNIQUE,
    name             TEXT NOT NULL,
    profile_url      TEXT NOT NULL UNIQUE,
    headline         TEXT,
    photo_url        TEXT,
    rating           NUMERIC DEFAULT 5.0,
    reviews_count    INTEGER DEFAULT 0,
    location         TEXT,
    neighborhood     TEXT,
    postal_code      TEXT,
    lat              DOUBLE PRECISION,
    lng              DOUBLE PRECISION,
    platform         TEXT DEFAULT 'rover',
    first_scraped_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    last_updated_at  TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- 3. Session Sitters (Many-to-Many Bridge)
CREATE TABLE IF NOT EXISTS public.session_sitters (
    session_id       BIGINT NOT NULL REFERENCES public.search_sessions(id) ON DELETE CASCADE,
    sitter_id        BIGINT NOT NULL REFERENCES public.sitters(id) ON DELETE CASCADE,
    PRIMARY KEY (session_id, sitter_id)
);

-- 4. Sitter Services & Rates (Multi-Service Matrix)
CREATE TABLE IF NOT EXISTS public.sitter_services (
    id               BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    sitter_id        BIGINT NOT NULL REFERENCES public.sitters(id) ON DELETE CASCADE,
    service_type     TEXT NOT NULL,
    service_name     TEXT NOT NULL,
    price_numeric    NUMERIC NOT NULL,
    rate_unit        TEXT NOT NULL,
    is_active        INTEGER DEFAULT 1,
    last_verified_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    CONSTRAINT uq_sitter_service UNIQUE (sitter_id, service_type)
);

-- Performance Indexes
CREATE INDEX IF NOT EXISTS idx_search_sessions_timestamp ON public.search_sessions(timestamp DESC);
CREATE INDEX IF NOT EXISTS idx_sitters_member_id ON public.sitters(member_id);
CREATE INDEX IF NOT EXISTS idx_sitters_postal_code ON public.sitters(postal_code);
CREATE INDEX IF NOT EXISTS idx_session_sitters_session ON public.session_sitters(session_id);
CREATE INDEX IF NOT EXISTS idx_session_sitters_sitter ON public.session_sitters(sitter_id);
CREATE INDEX IF NOT EXISTS idx_sitter_services_sitter ON public.sitter_services(sitter_id);
CREATE INDEX IF NOT EXISTS idx_sitter_services_type ON public.sitter_services(service_type);

-- Row Level Security (RLS)
ALTER TABLE public.search_sessions ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.sitters ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.session_sitters ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.sitter_services ENABLE ROW LEVEL SECURITY;

-- Anonymous and Authenticated Policies
DROP POLICY IF EXISTS "Allow anon and auth read search_sessions" ON public.search_sessions;
CREATE POLICY "Allow anon and auth read search_sessions" ON public.search_sessions
    FOR SELECT TO anon, authenticated USING (true);

DROP POLICY IF EXISTS "Allow anon and auth insert search_sessions" ON public.search_sessions;
CREATE POLICY "Allow anon and auth insert search_sessions" ON public.search_sessions
    FOR INSERT TO anon, authenticated WITH CHECK (true);

DROP POLICY IF EXISTS "Allow anon and auth delete search_sessions" ON public.search_sessions;
CREATE POLICY "Allow anon and auth delete search_sessions" ON public.search_sessions
    FOR DELETE TO anon, authenticated USING (true);

DROP POLICY IF EXISTS "Allow anon and auth read sitters" ON public.sitters;
CREATE POLICY "Allow anon and auth read sitters" ON public.sitters
    FOR SELECT TO anon, authenticated USING (true);

DROP POLICY IF EXISTS "Allow anon and auth write sitters" ON public.sitters;
CREATE POLICY "Allow anon and auth write sitters" ON public.sitters
    FOR ALL TO anon, authenticated USING (true) WITH CHECK (true);

DROP POLICY IF EXISTS "Allow anon and auth session_sitters" ON public.session_sitters;
CREATE POLICY "Allow anon and auth session_sitters" ON public.session_sitters
    FOR ALL TO anon, authenticated USING (true) WITH CHECK (true);

DROP POLICY IF EXISTS "Allow anon and auth sitter_services" ON public.sitter_services;
CREATE POLICY "Allow anon and auth sitter_services" ON public.sitter_services
    FOR ALL TO anon, authenticated USING (true) WITH CHECK (true);

-- Permissions
GRANT ALL ON TABLE public.search_sessions TO anon, authenticated;
GRANT ALL ON TABLE public.sitters TO anon, authenticated;
GRANT ALL ON TABLE public.session_sitters TO anon, authenticated;
GRANT ALL ON TABLE public.sitter_services TO anon, authenticated;
GRANT USAGE, SELECT ON ALL SEQUENCES IN SCHEMA public TO anon, authenticated;
