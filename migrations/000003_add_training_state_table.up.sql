-- Add training state tracking table

CREATE TABLE IF NOT EXISTS training_state (
    id SERIAL PRIMARY KEY,
    model_name TEXT NOT NULL,
    last_trained_id BIGINT DEFAULT 0,
    total_training_runs INTEGER DEFAULT 0,
    total_samples_trained BIGINT DEFAULT 0,
    last_training_time TIMESTAMP,
    best_eval_loss FLOAT,
    best_model_path TEXT,
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW(),
    UNIQUE(model_name)
);

-- Add trigger for updated_at
CREATE TRIGGER update_training_state_updated_at BEFORE UPDATE ON training_state
FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

-- Insert default entry for Qwen model
INSERT INTO training_state (model_name, last_trained_id, total_training_runs, total_samples_trained)
VALUES ('qwen2.5-coder-14b', 0, 0, 0)
ON CONFLICT (model_name) DO NOTHING;

-- Comments
COMMENT ON TABLE training_state IS 'Tracks AI model training state for resumability';
COMMENT ON COLUMN training_state.last_trained_id IS 'Last processed_files.id used in training';
COMMENT ON COLUMN training_state.best_eval_loss IS 'Best validation loss achieved';
