CREATE TABLE chat_histories (
  id SERIAL PRIMARY KEY,
  session_id UUID NOT NULL UNIQUE,
  history JSONB NOT NULL,
  created_at TIMESTAMP WITH TIME ZONE NOT NULL,
  updated_at TIMESTAMP WITH TIME ZONE NOT NULL
);

CREATE INDEX idx_chat_histories_session_id ON chat_histories(session_id);