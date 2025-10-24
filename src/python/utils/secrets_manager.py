#!/usr/bin/env python3
"""
Secrets Manager - Secure secrets storage and retrieval
Supports multiple backends: AWS Secrets Manager, HashiCorp Vault, Environment Variables
"""

import os
import json
import logging
from typing import Dict, Optional, Any
from enum import Enum
from abc import ABC, abstractmethod

logger = logging.getLogger(__name__)


class SecretsBackend(Enum):
    """Supported secrets backends"""
    AWS_SECRETS_MANAGER = "aws"
    HASHICORP_VAULT = "vault"
    ENVIRONMENT = "env"  # Fallback


class SecretsProvider(ABC):
    """Abstract base class for secrets providers"""

    @abstractmethod
    def get_secret(self, secret_name: str) -> Optional[str]:
        """Retrieve a secret by name"""
        pass

    @abstractmethod
    def get_secret_json(self, secret_name: str) -> Optional[Dict]:
        """Retrieve a JSON secret"""
        pass


class AWSSecretsManagerProvider(SecretsProvider):
    """AWS Secrets Manager provider"""

    def __init__(self, region_name: str = None):
        try:
            import boto3
            from botocore.exceptions import ClientError

            self.boto3 = boto3
            self.ClientError = ClientError
            self.region_name = region_name or os.getenv('AWS_REGION', 'us-east-1')
            self.client = boto3.client('secretsmanager', region_name=self.region_name)
            logger.info(f"Initialized AWS Secrets Manager in region {self.region_name}")
        except ImportError:
            raise RuntimeError("boto3 is required for AWS Secrets Manager. Install with: pip install boto3")

    def get_secret(self, secret_name: str) -> Optional[str]:
        """Retrieve a secret from AWS Secrets Manager"""
        try:
            response = self.client.get_secret_value(SecretId=secret_name)

            if 'SecretString' in response:
                return response['SecretString']
            else:
                # Binary secrets
                import base64
                return base64.b64decode(response['SecretBinary']).decode('utf-8')

        except self.ClientError as e:
            error_code = e.response['Error']['Code']
            if error_code == 'ResourceNotFoundException':
                logger.warning(f"Secret {secret_name} not found in AWS Secrets Manager")
            elif error_code == 'InvalidRequestException':
                logger.error(f"Invalid request for secret {secret_name}")
            elif error_code == 'InvalidParameterException':
                logger.error(f"Invalid parameter for secret {secret_name}")
            else:
                logger.error(f"Error retrieving secret {secret_name}: {e}")
            return None
        except Exception as e:
            logger.error(f"Unexpected error retrieving secret {secret_name}: {e}")
            return None

    def get_secret_json(self, secret_name: str) -> Optional[Dict]:
        """Retrieve a JSON secret"""
        secret_string = self.get_secret(secret_name)
        if secret_string:
            try:
                return json.loads(secret_string)
            except json.JSONDecodeError:
                logger.error(f"Secret {secret_name} is not valid JSON")
                return None
        return None


class VaultProvider(SecretsProvider):
    """HashiCorp Vault provider"""

    def __init__(self, vault_url: str = None, token: str = None):
        try:
            import hvac

            self.hvac = hvac
            self.vault_url = vault_url or os.getenv('VAULT_ADDR', 'http://localhost:8200')
            self.token = token or os.getenv('VAULT_TOKEN')

            if not self.token:
                raise RuntimeError("VAULT_TOKEN environment variable is required")

            self.client = hvac.Client(url=self.vault_url, token=self.token)

            if not self.client.is_authenticated():
                raise RuntimeError("Failed to authenticate with Vault")

            logger.info(f"Initialized Vault client at {self.vault_url}")

        except ImportError:
            raise RuntimeError("hvac is required for Vault. Install with: pip install hvac")

    def get_secret(self, secret_path: str, key: str = 'value') -> Optional[str]:
        """
        Retrieve a secret from Vault

        Args:
            secret_path: Path to secret in Vault (e.g., 'secret/data/myapp/db')
            key: Key within the secret data (default: 'value')
        """
        try:
            # Read secret from KV v2 secrets engine
            response = self.client.secrets.kv.v2.read_secret_version(path=secret_path)
            data = response['data']['data']

            if key in data:
                return data[key]
            else:
                logger.warning(f"Key '{key}' not found in secret {secret_path}")
                return None

        except Exception as e:
            logger.error(f"Error retrieving secret {secret_path}: {e}")
            return None

    def get_secret_json(self, secret_path: str) -> Optional[Dict]:
        """Retrieve entire secret data as JSON"""
        try:
            response = self.client.secrets.kv.v2.read_secret_version(path=secret_path)
            return response['data']['data']
        except Exception as e:
            logger.error(f"Error retrieving secret {secret_path}: {e}")
            return None


class EnvironmentProvider(SecretsProvider):
    """Environment variables provider (fallback)"""

    def __init__(self):
        logger.info("Using environment variables for secrets (not recommended for production)")

    def get_secret(self, secret_name: str) -> Optional[str]:
        """Retrieve a secret from environment variables"""
        value = os.getenv(secret_name)
        if value is None:
            logger.warning(f"Environment variable {secret_name} not found")
        return value

    def get_secret_json(self, secret_name: str) -> Optional[Dict]:
        """Retrieve a JSON secret from environment variables"""
        value = self.get_secret(secret_name)
        if value:
            try:
                return json.loads(value)
            except json.JSONDecodeError:
                logger.error(f"Environment variable {secret_name} is not valid JSON")
                return None
        return None


class SecretsManager:
    """
    Unified secrets manager with multiple backend support

    Usage:
        # Auto-detect backend based on environment
        manager = SecretsManager()

        # Or specify backend explicitly
        manager = SecretsManager(backend=SecretsBackend.AWS_SECRETS_MANAGER)

        # Retrieve secrets
        db_password = manager.get_secret('database/password')
        api_keys = manager.get_secret_json('api/keys')
    """

    def __init__(self, backend: SecretsBackend = None):
        """
        Initialize secrets manager

        Args:
            backend: Secrets backend to use. If None, auto-detect from environment.
        """
        if backend is None:
            backend = self._detect_backend()

        self.backend = backend
        self.provider = self._initialize_provider()

    def _detect_backend(self) -> SecretsBackend:
        """Auto-detect secrets backend from environment"""
        # Check for AWS credentials
        if os.getenv('AWS_ACCESS_KEY_ID') or os.path.exists(os.path.expanduser('~/.aws/credentials')):
            logger.info("Detected AWS credentials, using AWS Secrets Manager")
            return SecretsBackend.AWS_SECRETS_MANAGER

        # Check for Vault
        if os.getenv('VAULT_ADDR') and os.getenv('VAULT_TOKEN'):
            logger.info("Detected Vault configuration, using HashiCorp Vault")
            return SecretsBackend.HASHICORP_VAULT

        # Fallback to environment variables
        logger.warning("No secrets backend detected, falling back to environment variables")
        return SecretsBackend.ENVIRONMENT

    def _initialize_provider(self) -> SecretsProvider:
        """Initialize the appropriate secrets provider"""
        if self.backend == SecretsBackend.AWS_SECRETS_MANAGER:
            return AWSSecretsManagerProvider()
        elif self.backend == SecretsBackend.HASHICORP_VAULT:
            return VaultProvider()
        elif self.backend == SecretsBackend.ENVIRONMENT:
            return EnvironmentProvider()
        else:
            raise ValueError(f"Unsupported backend: {self.backend}")

    def get_secret(self, secret_name: str, default: Any = None) -> Optional[str]:
        """
        Retrieve a secret by name

        Args:
            secret_name: Name/path of the secret
            default: Default value if secret not found

        Returns:
            Secret value or default
        """
        value = self.provider.get_secret(secret_name)
        return value if value is not None else default

    def get_secret_json(self, secret_name: str, default: Any = None) -> Optional[Dict]:
        """
        Retrieve a JSON secret

        Args:
            secret_name: Name/path of the secret
            default: Default value if secret not found

        Returns:
            Parsed JSON dict or default
        """
        value = self.provider.get_secret_json(secret_name)
        return value if value is not None else default

    def get_database_config(self, secret_name: str = 'database/config') -> Dict[str, str]:
        """
        Retrieve database configuration from secrets

        Expected JSON format:
        {
            "host": "localhost",
            "port": "5432",
            "database": "mydb",
            "user": "myuser",
            "password": "secret123"
        }

        Returns:
            Database configuration dict
        """
        config = self.get_secret_json(secret_name)
        if config:
            return config

        # Fallback to individual secrets
        return {
            'host': self.get_secret('POSTGRES_HOST', 'localhost'),
            'port': self.get_secret('POSTGRES_PORT', '5432'),
            'database': self.get_secret('POSTGRES_DB', 'coding_db'),
            'user': self.get_secret('POSTGRES_USER', 'coding_user'),
            'password': self.get_secret('POSTGRES_PASSWORD', 'coding_pass'),
        }


# Convenience function for simple usage
_default_manager = None


def get_secrets_manager() -> SecretsManager:
    """Get or create default secrets manager instance"""
    global _default_manager
    if _default_manager is None:
        _default_manager = SecretsManager()
    return _default_manager


def get_secret(secret_name: str, default: Any = None) -> Optional[str]:
    """Convenience function to get a secret"""
    return get_secrets_manager().get_secret(secret_name, default)


def get_secret_json(secret_name: str, default: Any = None) -> Optional[Dict]:
    """Convenience function to get a JSON secret"""
    return get_secrets_manager().get_secret_json(secret_name, default)


# Example usage
if __name__ == "__main__":
    # Set up logging
    logging.basicConfig(level=logging.INFO)

    # Initialize manager
    manager = SecretsManager()

    # Example: Get database config
    print("\nRetrieving database configuration...")
    db_config = manager.get_database_config()
    print(f"Database host: {db_config['host']}")
    print(f"Database user: {db_config['user']}")
    print(f"Password: {'*' * len(db_config['password'])}")  # Redacted

    # Example: Get individual secret
    print("\nRetrieving API key...")
    api_key = manager.get_secret('API_KEY', default='not-found')
    print(f"API Key: {api_key[:4]}...{api_key[-4:] if len(api_key) > 8 else ''}")
