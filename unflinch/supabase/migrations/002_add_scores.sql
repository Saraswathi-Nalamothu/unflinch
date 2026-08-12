-- ============================================================
-- Unflinch – Migration 002
-- Add AI advanced analysis fields
-- ============================================================

-- Add to sessions table
ALTER TABLE public.sessions
ADD COLUMN IF NOT EXISTS persona TEXT DEFAULT 'Friendly',
ADD COLUMN IF NOT EXISTS session_context JSONB DEFAULT '[]'::jsonb,
ADD COLUMN IF NOT EXISTS overall_verdict TEXT,
ADD COLUMN IF NOT EXISTS weekly_plan JSONB,
ADD COLUMN IF NOT EXISTS company_specific_tip TEXT,
ADD COLUMN IF NOT EXISTS confidence_trend JSONB DEFAULT '[]'::jsonb;

-- Add to answers table
ALTER TABLE public.answers
ADD COLUMN IF NOT EXISTS clarity_score NUMERIC(5,1),
ADD COLUMN IF NOT EXISTS relevance_score NUMERIC(5,1),
ADD COLUMN IF NOT EXISTS structure_score NUMERIC(5,1),
ADD COLUMN IF NOT EXISTS confidence_score NUMERIC(5,1),
ADD COLUMN IF NOT EXISTS what_worked TEXT,
ADD COLUMN IF NOT EXISTS red_flag TEXT,
ADD COLUMN IF NOT EXISTS hint_used BOOLEAN DEFAULT FALSE,
ADD COLUMN IF NOT EXISTS challenge_question TEXT;
