#!/usr/bin/env python3
"""
Unit tests for SecurityScanner
"""

import unittest
import sys
from pathlib import Path

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from security_scanner import SecurityScanner, SecurityIssue


class TestSecurityScanner(unittest.TestCase):
    """Test cases for SecurityScanner"""

    def setUp(self):
        """Set up test fixtures"""
        self.scanner = SecurityScanner()

    def test_safe_code(self):
        """Test that safe code passes"""
        code = """
def hello_world():
    print("Hello, World!")
    return 42
"""
        is_safe, issues = self.scanner.scan_code(code, 'Python')
        self.assertTrue(is_safe)
        self.assertEqual(len(issues), 0)

    def test_eval_with_user_input(self):
        """Test detection of eval with user input"""
        code = """
import sys
result = eval(sys.argv[1])
print(result)
"""
        is_safe, issues = self.scanner.scan_code(code, 'Python')
        self.assertFalse(is_safe)
        self.assertGreater(len(issues), 0)
        self.assertTrue(any(i.category == 'code_injection' for i in issues))

    def test_exec_with_user_input(self):
        """Test detection of exec with user input"""
        code = """
user_input = input("Enter code: ")
exec(user_input)
"""
        is_safe, issues = self.scanner.scan_code(code, 'Python')
        self.assertFalse(is_safe)
        self.assertGreater(len(issues), 0)
        self.assertTrue(any(i.category == 'code_injection' for i in issues))

    def test_shell_injection(self):
        """Test detection of shell injection"""
        code = """
import os
filename = input("Enter filename: ")
os.system("cat " + filename)
"""
        is_safe, issues = self.scanner.scan_code(code, 'Python')
        self.assertFalse(is_safe)
        self.assertGreater(len(issues), 0)
        self.assertTrue(any(i.category == 'shell_injection' for i in issues))

    def test_subprocess_shell_true(self):
        """Test detection of subprocess with shell=True"""
        code = """
import subprocess
user_cmd = input("Command: ")
subprocess.run(user_cmd, shell=True)
"""
        is_safe, issues = self.scanner.scan_code(code, 'Python')
        self.assertFalse(is_safe)
        self.assertGreater(len(issues), 0)

    def test_reverse_shell(self):
        """Test detection of reverse shell"""
        code = """
import socket
s = socket.socket()
s.connect(("192.168.1.100", 4444))
"""
        is_safe, issues = self.scanner.scan_code(code, 'Python')
        self.assertFalse(is_safe)
        self.assertGreater(len(issues), 0)
        self.assertTrue(any(i.category == 'backdoor' for i in issues))

    def test_obfuscation(self):
        """Test detection of obfuscation patterns"""
        code = """
import base64
payload = base64.b64decode("payload").decode()
exec(compile(payload, '<string>', 'exec'))
"""
        is_safe, issues = self.scanner.scan_code(code, 'Python')
        # Should detect suspicious combination
        self.assertGreater(len(issues), 0)

    def test_keylogger_pattern(self):
        """Test detection of keylogger"""
        code = """
from pynput import keyboard

def on_press(key):
    log_file.write(str(key))

listener = keyboard.Listener(on_press=on_press)
listener.start()
"""
        is_safe, issues = self.scanner.scan_code(code, 'Python')
        self.assertFalse(is_safe)
        self.assertGreater(len(issues), 0)
        self.assertTrue(any(i.category == 'keylogger' for i in issues))

    def test_sensitive_file_access(self):
        """Test detection of sensitive file access"""
        code = """
with open('/etc/passwd', 'r') as f:
    users = f.read()
"""
        is_safe, issues = self.scanner.scan_code(code, 'Python')
        # Should flag sensitive file access
        self.assertGreater(len(issues), 0)
        self.assertTrue(any(i.category == 'file_access' for i in issues))

    def test_destructive_command(self):
        """Test detection of destructive commands"""
        code = """
import os
os.system("rm -rf /")
"""
        is_safe, issues = self.scanner.scan_code(code, 'Python')
        self.assertFalse(is_safe)
        self.assertGreater(len(issues), 0)
        self.assertTrue(any(i.category == 'destructive' for i in issues))

    def test_cryptominer_pattern(self):
        """Test detection of cryptocurrency mining"""
        code = """
import requests
pool_url = "stratum+tcp://pool.example.com:3333"
requests.post(pool_url, json={"method": "mining.subscribe"})
"""
        is_safe, issues = self.scanner.scan_code(code, 'Python')
        self.assertGreater(len(issues), 0)
        self.assertTrue(any(i.category == 'cryptominer' for i in issues))

    def test_safe_subprocess_without_shell(self):
        """Test that safe subprocess usage doesn't trigger false positive"""
        code = """
import subprocess
# Safe usage - no shell=True, fixed command
result = subprocess.run(['ls', '-la'], capture_output=True)
"""
        is_safe, issues = self.scanner.scan_code(code, 'Python')
        # This should be safe or only have low-severity warnings
        critical_issues = [i for i in issues if i.severity == 'critical']
        self.assertEqual(len(critical_issues), 0)

    def test_get_security_report(self):
        """Test security report generation"""
        code = """
import os
user_input = input()
os.system(user_input)
eval(user_input)
"""
        is_safe, issues = self.scanner.scan_code(code, 'Python')
        report = self.scanner.get_security_report(issues)

        self.assertIn('total_issues', report)
        self.assertIn('critical', report)
        self.assertIn('categories', report)
        self.assertFalse(report['is_safe'])
        self.assertGreater(report['critical'], 0)


class TestSecurityIssue(unittest.TestCase):
    """Test SecurityIssue dataclass"""

    def test_create_issue(self):
        """Test creating a SecurityIssue"""
        issue = SecurityIssue(
            severity='critical',
            category='code_injection',
            description='Eval with user input',
            line_number=42,
            pattern=r'eval\(.*input'
        )

        self.assertEqual(issue.severity, 'critical')
        self.assertEqual(issue.category, 'code_injection')
        self.assertEqual(issue.line_number, 42)


if __name__ == '__main__':
    unittest.main()
