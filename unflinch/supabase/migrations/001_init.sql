-- ============================================================
-- Unflinch – Supabase Database Migration
-- Run this in the Supabase SQL Editor
-- ============================================================

-- 1. Users table (extends auth.users)
CREATE TABLE IF NOT EXISTS public.users (
  id          UUID PRIMARY KEY REFERENCES auth.users(id) ON DELETE CASCADE,
  phone       TEXT,
  full_name   TEXT,
  created_at  TIMESTAMPTZ DEFAULT NOW()
);

-- Automatically create a user row on sign-up
CREATE OR REPLACE FUNCTION public.handle_new_user()
RETURNS TRIGGER LANGUAGE plpgsql SECURITY DEFINER AS $$
BEGIN
  INSERT INTO public.users (id, phone, full_name)
  VALUES (
    NEW.id,
    NEW.phone,
    NEW.raw_user_meta_data->>'full_name'
  )
  ON CONFLICT (id) DO NOTHING;
  RETURN NEW;
END;
$$;

DROP TRIGGER IF EXISTS on_auth_user_created ON auth.users;
CREATE TRIGGER on_auth_user_created
  AFTER INSERT ON auth.users
  FOR EACH ROW EXECUTE FUNCTION public.handle_new_user();

-- 2. Sessions table
CREATE TABLE IF NOT EXISTS public.sessions (
  id                   UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  user_id              UUID NOT NULL REFERENCES auth.users(id) ON DELETE CASCADE,
  company              TEXT NOT NULL,
  role                 TEXT NOT NULL,
  round                TEXT NOT NULL,
  first_time           BOOLEAN DEFAULT FALSE,
  distraction_enabled  BOOLEAN DEFAULT FALSE,
  status               TEXT DEFAULT 'in_progress',  -- 'in_progress' | 'completed'
  overall_nervousness  NUMERIC(5,1),
  created_at           TIMESTAMPTZ DEFAULT NOW()
);

-- 3. Questions table
CREATE TABLE IF NOT EXISTS public.questions (
  id             UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  session_id     UUID NOT NULL REFERENCES public.sessions(id) ON DELETE CASCADE,
  question_text  TEXT NOT NULL,
  order_index    INTEGER NOT NULL,
  created_at     TIMESTAMPTZ DEFAULT NOW()
);

-- 4. Answers table
CREATE TABLE IF NOT EXISTS public.answers (
  id                UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  session_id        UUID NOT NULL REFERENCES public.sessions(id) ON DELETE CASCADE,
  question_id       UUID NOT NULL REFERENCES public.questions(id) ON DELETE CASCADE,
  transcript        TEXT,
  filler_count      INTEGER DEFAULT 0,
  pause_count       INTEGER DEFAULT 0,
  speech_rate       NUMERIC(5,2),
  nervousness_score NUMERIC(5,1),
  improvement_tip   TEXT,
  recovery_time     NUMERIC(6,2),  -- seconds (distraction mode)
  audio_url         TEXT,
  created_at        TIMESTAMPTZ DEFAULT NOW()
);

-- ============================================================
-- Row Level Security (RLS)
-- ============================================================

ALTER TABLE public.users    ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.sessions ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.questions ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.answers  ENABLE ROW LEVEL SECURITY;

-- users: only read/update own row
CREATE POLICY "users_select_own" ON public.users
  FOR SELECT USING (auth.uid() = id);

CREATE POLICY "users_update_own" ON public.users
  FOR UPDATE USING (auth.uid() = id);

-- sessions: full CRUD on own sessions
CREATE POLICY "sessions_all_own" ON public.sessions
  FOR ALL USING (auth.uid() = user_id);

-- questions: accessible if user owns the parent session
CREATE POLICY "questions_via_session" ON public.questions
  FOR ALL USING (
    EXISTS (
      SELECT 1 FROM public.sessions s
      WHERE s.id = questions.session_id AND s.user_id = auth.uid()
    )
  );

-- answers: accessible if user owns the parent session
CREATE POLICY "answers_via_session" ON public.answers
  FOR ALL USING (
    EXISTS (
      SELECT 1 FROM public.sessions s
      WHERE s.id = answers.session_id AND s.user_id = auth.uid()
    )
  );

-- ============================================================
-- Indexes
-- ============================================================

CREATE INDEX IF NOT EXISTS idx_sessions_user_id   ON public.sessions(user_id);
CREATE INDEX IF NOT EXISTS idx_questions_session   ON public.questions(session_id, order_index);
CREATE INDEX IF NOT EXISTS idx_answers_session     ON public.answers(session_id);
CREATE INDEX IF NOT EXISTS idx_answers_question    ON public.answers(question_id);
