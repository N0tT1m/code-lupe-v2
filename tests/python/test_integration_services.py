"""Integration tests for CodeLupe services."""

import os
import pytest
import psycopg2
from elasticsearch import Elasticsearch
import redis


@pytest.fixture
def db_connection():
    """PostgreSQL database connection fixture."""
    conn = psycopg2.connect(
        host=os.getenv("POSTGRES_HOST", "localhost"),
        port=int(os.getenv("POSTGRES_PORT", "5432")),
        database=os.getenv("POSTGRES_DB", "coding_db"),
        user=os.getenv("POSTGRES_USER", "coding_user"),
        password=os.getenv("POSTGRES_PASSWORD", "coding_pass"),
    )
    yield conn
    conn.close()


@pytest.fixture
def es_client():
    """Elasticsearch client fixture."""
    es = Elasticsearch([os.getenv("ELASTICSEARCH_URL", "http://localhost:9200")])
    yield es
    es.close()


@pytest.fixture
def redis_client():
    """Redis client fixture."""
    r = redis.Redis(
        host=os.getenv("REDIS_HOST", "localhost"),
        port=int(os.getenv("REDIS_PORT", "6379")),
        decode_responses=True,
    )
    yield r
    r.close()


@pytest.mark.integration
def test_database_connection(db_connection):
    """Test PostgreSQL database connectivity."""
    cursor = db_connection.cursor()
    cursor.execute("SELECT 1")
    result = cursor.fetchone()
    assert result[0] == 1
    cursor.close()


@pytest.mark.integration
def test_database_tables_exist(db_connection):
    """Test that required tables exist."""
    cursor = db_connection.cursor()
    
    tables = ["repositories", "processed_files", "processing_jobs", "training_state"]
    
    for table in tables:
        cursor.execute("""
            SELECT EXISTS (
                SELECT FROM information_schema.tables 
                WHERE table_name = %s
            )
        """, (table,))
        exists = cursor.fetchone()[0]
        assert exists, f"Table {table} should exist"
    
    cursor.close()


@pytest.mark.integration
def test_elasticsearch_connection(es_client):
    """Test Elasticsearch connectivity."""
    assert es_client.ping(), "Should connect to Elasticsearch"


@pytest.mark.integration
def test_redis_connection(redis_client):
    """Test Redis connectivity."""
    assert redis_client.ping(), "Should connect to Redis"


@pytest.mark.integration
def test_redis_operations(redis_client):
    """Test basic Redis operations."""
    # Set a value
    redis_client.set("test_key", "test_value", ex=60)
    
    # Get the value
    value = redis_client.get("test_key")
    assert value == "test_value"
    
    # Delete the key
    redis_client.delete("test_key")
    assert redis_client.get("test_key") is None


@pytest.mark.integration
def test_repository_crud_operations(db_connection):
    """Test CRUD operations on repositories table."""
    cursor = db_connection.cursor()
    
    # Create
    cursor.execute("""
        INSERT INTO repositories (full_name, clone_url, language, quality_score)
        VALUES (%s, %s, %s, %s)
        RETURNING id
    """, ("test/repo", "https://github.com/test/repo", "Python", 85))
    
    repo_id = cursor.fetchone()[0]
    db_connection.commit()
    
    # Read
    cursor.execute("SELECT full_name, language FROM repositories WHERE id = %s", (repo_id,))
    row = cursor.fetchone()
    assert row[0] == "test/repo"
    assert row[1] == "Python"
    
    # Update
    cursor.execute("""
        UPDATE repositories SET quality_score = %s WHERE id = %s
    """, (90, repo_id))
    db_connection.commit()
    
    cursor.execute("SELECT quality_score FROM repositories WHERE id = %s", (repo_id,))
    score = cursor.fetchone()[0]
    assert score == 90
    
    # Delete
    cursor.execute("DELETE FROM repositories WHERE id = %s", (repo_id,))
    db_connection.commit()
    
    cursor.close()


@pytest.mark.integration
def test_training_state_tracking(db_connection):
    """Test training state tracking functionality."""
    cursor = db_connection.cursor()
    
    # Insert or update training state
    cursor.execute("""
        INSERT INTO training_state (model_name, last_trained_id, total_training_runs)
        VALUES (%s, %s, %s)
        ON CONFLICT (model_name) 
        DO UPDATE SET 
            last_trained_id = EXCLUDED.last_trained_id,
            total_training_runs = training_state.total_training_runs + 1
        RETURNING id
    """, ("test-model", 100, 1))
    
    db_connection.commit()
    
    # Verify
    cursor.execute("""
        SELECT last_trained_id, total_training_runs 
        FROM training_state 
        WHERE model_name = %s
    """, ("test-model",))
    
    row = cursor.fetchone()
    assert row[0] == 100
    assert row[1] >= 1
    
    # Cleanup
    cursor.execute("DELETE FROM training_state WHERE model_name = %s", ("test-model",))
    db_connection.commit()
    cursor.close()
