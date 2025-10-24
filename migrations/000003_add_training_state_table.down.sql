-- Rollback training state table

DROP TRIGGER IF EXISTS update_training_state_updated_at ON training_state;
DROP TABLE IF EXISTS training_state;
