-- MatUstoz — PostgreSQL sxemasi.
-- Bot ishga tushganda avtomatik qo'llaniladi (bot/db.py -> init).

CREATE TABLE IF NOT EXISTS students (
    telegram_id     BIGINT PRIMARY KEY,
    username        TEXT,
    first_name      TEXT,
    -- Yo'nalish: poydevor | imtihon | milliy | sat
    track           TEXT,
    goal            TEXT,          -- o'quvchining o'z so'zi bilan maqsadi
    deadline        TEXT,          -- "2 oy", "15-may imtihon" va h.k.
    daily_minutes   INTEGER,       -- kuniga necha daqiqa
    level           TEXT,          -- nol | boshlangich | orta | yaxshi
    plan            TEXT,          -- tuzilgan o'quv rejasi (to'liq matn)
    current_topic   TEXT,          -- hozir o'tilayotgan mavzu
    onboarding_done BOOLEAN NOT NULL DEFAULT FALSE,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at      TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS messages (
    id          BIGSERIAL PRIMARY KEY,
    telegram_id BIGINT NOT NULL REFERENCES students(telegram_id) ON DELETE CASCADE,
    role        TEXT NOT NULL CHECK (role IN ('user', 'assistant')),
    content     TEXT NOT NULL,
    created_at  TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS messages_student_idx ON messages (telegram_id, id);

CREATE TABLE IF NOT EXISTS topics (
    id          BIGSERIAL PRIMARY KEY,
    telegram_id BIGINT NOT NULL REFERENCES students(telegram_id) ON DELETE CASCADE,
    topic       TEXT NOT NULL,
    status      TEXT NOT NULL DEFAULT 'jarayonda'
                CHECK (status IN ('jarayonda', 'tugallandi', 'qiynalyapti')),
    note        TEXT,
    updated_at  TIMESTAMPTZ NOT NULL DEFAULT now(),
    UNIQUE (telegram_id, topic)
);
