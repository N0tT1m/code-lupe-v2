#!/usr/bin/env python3
"""
Unit tests for SecretScanner
"""

import unittest
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from secret_scanner import SecretScanner, SecretMatch


class TestSecretScanner(unittest.TestCase):
    """Test cases for SecretScanner"""

    def setUp(self):
        """Set up test fixtures"""
        self.scanner = SecretScanner()

    def test_safe_code(self):
        """Test that code without secrets passes"""
        code = """
def process_data(data):
    result = transform(data)
    return result
"""
        is_safe, secrets = self.scanner.scan_code(code, 'Python')
        self.assertTrue(is_safe)
        self.assertEqual(len(secrets), 0)

    def test_aws_access_key(self):
        """Test detection of AWS access key"""
        code = """
AWS_ACCESS_KEY_ID = "AKIAIOSFODNN7EXAMPLE"
"""
        is_safe, secrets = self.scanner.scan_code(code, 'Python')
        self.assertFalse(is_safe)
        self.assertGreater(len(secrets), 0)
        self.assertTrue(any(s.secret_type == 'aws_access_key_id' for s in secrets))

    def test_aws_secret_key(self):
        """Test detection of AWS secret key"""
        code = """
config = {
    'aws_secret_access_key': 'wJalrXUtnFEMI/K7MDENG/bPxRfiCYEXAMPLEKEY'
}
"""
        is_safe, secrets = self.scanner.scan_code(code, 'Python')
        self.assertFalse(is_safe)
        self.assertGreater(len(secrets), 0)

    def test_github_token(self):
        """Test detection of GitHub personal access token"""
        code = """
GITHUB_TOKEN = "ghp_1234567890abcdefghijklmnopqrstuv"
headers = {'Authorization': f'token {GITHUB_TOKEN}'}
"""
        is_safe, secrets = self.scanner.scan_code(code, 'Python')
        self.assertFalse(is_safe)
        self.assertGreater(len(secrets), 0)
        self.assertTrue(any(s.secret_type == 'github_personal_access_token' for s in secrets))

    def test_jwt_token(self):
        """Test detection of JWT tokens"""
        code = """
token = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJzdWIiOiIxMjM0NTY3ODkwIn0.dozjgNryP4J3jVmNHl0w5N_XgL0n3I9PlFUP0THsR8U"
"""
        is_safe, secrets = self.scanner.scan_code(code, 'Python')
        self.assertFalse(is_safe)
        self.assertGreater(len(secrets), 0)
        self.assertTrue(any(s.secret_type == 'jwt_token' for s in secrets))

    def test_private_key(self):
        """Test detection of private keys"""
        code = """
key = '''-----BEGIN RSA PRIVATE KEY-----
MIIEpAIBAAKCAQEA1234567890abcdefghijk
-----END RSA PRIVATE KEY-----'''
"""
        is_safe, secrets = self.scanner.scan_code(code, 'Python')
        self.assertFalse(is_safe)
        self.assertGreater(len(secrets), 0)
        self.assertTrue(any(s.secret_type == 'private_key' for s in secrets))

    def test_database_connection_string(self):
        """Test detection of database connection strings with passwords"""
        code = """
DATABASE_URL = "postgresql://user:SuperSecret123@localhost:5432/mydb"
"""
        is_safe, secrets = self.scanner.scan_code(code, 'Python')
        self.assertFalse(is_safe)
        self.assertGreater(len(secrets), 0)
        self.assertTrue(any(s.secret_type == 'database_connection_string' for s in secrets))

    def test_hardcoded_password(self):
        """Test detection of hardcoded passwords"""
        code = """
config = {
    'username': 'admin',
    'password': 'MyS3cr3tP@ssw0rd!'
}
"""
        is_safe, secrets = self.scanner.scan_code(code, 'Python')
        # Note: This might not flag if entropy is too low or it's flagged as test
        # We're testing the pattern matching
        self.assertFalse(is_safe)

    def test_google_api_key(self):
        """Test detection of Google API keys"""
        code = """
GOOGLE_API_KEY = "AIzaSyD1234567890abcdefghijklmnopqrst"
"""
        is_safe, secrets = self.scanner.scan_code(code, 'Python')
        self.assertFalse(is_safe)
        self.assertGreater(len(secrets), 0)
        self.assertTrue(any(s.secret_type == 'google_api_key' for s in secrets))

    def test_slack_token(self):
        """Test detection of Slack tokens"""
        code = """
SLACK_TOKEN = "xoxb-test-1234567890-1234567890-TestTokenNotRealKey"
"""
        is_safe, secrets = self.scanner.scan_code(code, 'Python')
        self.assertFalse(is_safe)
        self.assertGreater(len(secrets), 0)
        self.assertTrue(any(s.secret_type == 'slack_token' for s in secrets))

    def test_stripe_key(self):
        """Test detection of Stripe secret keys"""
        code = """
STRIPE_SECRET = "sk_test_1234567890TestKeyNotRealSecret"
"""
        is_safe, secrets = self.scanner.scan_code(code, 'Python')
        self.assertFalse(is_safe)
        self.assertGreater(len(secrets), 0)
        self.assertTrue(any(s.secret_type == 'stripe_secret_key' for s in secrets))

    def test_false_positive_example_values(self):
        """Test that example/placeholder values are filtered out"""
        code = """
# Example configuration
API_KEY = "your-api-key-here"
PASSWORD = "changeme"
SECRET = "replace-me"
TOKEN = "xxxxxxxxxxxx"
"""
        is_safe, secrets = self.scanner.scan_code(code, 'Python')
        # Should be safe because these are clearly placeholders
        self.assertTrue(is_safe)
        self.assertEqual(len(secrets), 0)

    def test_false_positive_todos(self):
        """Test that TODO/FIXME comments don't trigger false positives"""
        code = """
# TODO: Add API key here
# FIXME: Update password
api_key = None
"""
        is_safe, secrets = self.scanner.scan_code(code, 'Python')
        self.assertTrue(is_safe)

    def test_entropy_calculation(self):
        """Test entropy calculation for randomness detection"""
        # High entropy string (random)
        high_entropy = self.scanner.calculate_entropy("xK9j2Lp8mN4qW7rT3vZ1cY6bH5gF0dS")
        # Low entropy string (repetitive)
        low_entropy = self.scanner.calculate_entropy("aaaaaaaaaaaaaaa")

        self.assertGreater(high_entropy, low_entropy)

    def test_redact_secret(self):
        """Test secret redaction"""
        secret = "MyVeryLongSecretKey1234567890"
        redacted = self.scanner.redact_secret(secret)

        self.assertIn("...", redacted)
        self.assertLess(len(redacted), len(secret))
        # Should show first and last few chars
        self.assertTrue(redacted.startswith("MyVe"))
        self.assertTrue(redacted.endswith("7890"))

    def test_is_likely_false_positive(self):
        """Test false positive detection"""
        self.assertTrue(self.scanner.is_likely_false_positive("your-api-key"))
        self.assertTrue(self.scanner.is_likely_false_positive("changeme"))
        self.assertTrue(self.scanner.is_likely_false_positive("xxxxxxxxxxxx"))
        self.assertTrue(self.scanner.is_likely_false_positive("example-token"))
        self.assertFalse(self.scanner.is_likely_false_positive("xK9j2Lp8mN4qW7rT"))

    def test_get_secret_report(self):
        """Test secret report generation"""
        code = """
AWS_KEY = "AKIAIOSFODNN7EXAMPLE"
GITHUB_TOKEN = "ghp_1234567890abcdefghijklmnopqrstuv"
password = "MyS3cr3tP@ssw0rd!"
"""
        is_safe, secrets = self.scanner.scan_code(code, 'Python')
        report = self.scanner.get_secret_report(secrets)

        self.assertIn('total_secrets', report)
        self.assertIn('high_confidence', report)
        self.assertIn('secret_types', report)
        self.assertFalse(report['is_safe'])
        self.assertGreater(report['total_secrets'], 0)

    def test_multiple_secrets_same_file(self):
        """Test detection of multiple secrets in one file"""
        code = """
config = {
    'aws_key': 'AKIAIOSFODNN7EXAMPLE',
    'github_token': 'ghp_abcdefghijklmnopqrstuvwxyz123456',
    'db_url': 'postgresql://user:pass123@localhost/db'
}
"""
        is_safe, secrets = self.scanner.scan_code(code, 'Python')
        self.assertFalse(is_safe)
        self.assertGreaterEqual(len(secrets), 2)


class TestSecretMatch(unittest.TestCase):
    """Test SecretMatch dataclass"""

    def test_create_secret_match(self):
        """Test creating a SecretMatch"""
        match = SecretMatch(
            secret_type='aws_access_key_id',
            line_number=10,
            matched_text='AKIA...AMPLE',
            entropy=0.85,
            confidence='high'
        )

        self.assertEqual(match.secret_type, 'aws_access_key_id')
        self.assertEqual(match.line_number, 10)
        self.assertEqual(match.confidence, 'high')
        self.assertEqual(match.entropy, 0.85)


if __name__ == '__main__':
    unittest.main()
