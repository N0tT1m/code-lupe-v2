#!/usr/bin/env python3
"""
Security Scanner - Detects malicious code patterns
Scans for: obfuscation, backdoors, exploits, suspicious patterns
Does NOT filter educational/research content or NSFW content
"""

import re
import logging
from typing import Dict, List, Tuple
from dataclasses import dataclass

logger = logging.getLogger(__name__)


@dataclass
class SecurityIssue:
    """Represents a security concern found in code"""
    severity: str  # 'critical', 'high', 'medium', 'low'
    category: str
    description: str
    line_number: int = None
    pattern: str = None


class SecurityScanner:
    """Scans code for malicious patterns and security concerns"""

    def __init__(self):
        # Critical patterns that indicate malicious intent
        self.malicious_patterns = {
            # Command injection patterns
            r'eval\s*\(\s*(?:input|raw_input|sys\.argv|request\.|subprocess|os\.system)': {
                'severity': 'critical',
                'category': 'code_injection',
                'description': 'Potential code injection via eval() with user input'
            },
            r'exec\s*\(\s*(?:input|raw_input|sys\.argv|request\.)': {
                'severity': 'critical',
                'category': 'code_injection',
                'description': 'Potential code injection via exec() with user input'
            },
            r'__import__\s*\(\s*(?:input|request\.|sys\.argv)': {
                'severity': 'critical',
                'category': 'code_injection',
                'description': 'Dynamic import with untrusted input'
            },

            # Shell injection patterns
            r'os\.system\s*\([^)]*(?:\+|%|f["\']|\.format)': {
                'severity': 'critical',
                'category': 'shell_injection',
                'description': 'Shell command with dynamic string concatenation'
            },
            r'subprocess\.\w+\([^)]*shell\s*=\s*True[^)]*(?:\+|%|f["\']|\.format)': {
                'severity': 'critical',
                'category': 'shell_injection',
                'description': 'Shell command injection risk with shell=True'
            },

            # Obfuscation indicators
            r'(?:chr|ord)\s*\(\s*(?:chr|ord)\s*\(': {
                'severity': 'high',
                'category': 'obfuscation',
                'description': 'Nested chr/ord obfuscation pattern'
            },
            r'(?:base64|codecs)\.(?:b64decode|decode)\s*\([^)]*\)\s*\.\s*decode': {
                'severity': 'high',
                'category': 'obfuscation',
                'description': 'Multiple layers of encoding/decoding'
            },
            r'compile\s*\(\s*[\'"]{50,}': {
                'severity': 'high',
                'category': 'obfuscation',
                'description': 'Suspiciously long encoded string in compile()'
            },

            # Backdoor patterns
            r'socket\.socket\s*\([^)]*\)\.connect\s*\(\s*\(\s*["\'](?:\d{1,3}\.){3}\d{1,3}': {
                'severity': 'critical',
                'category': 'backdoor',
                'description': 'Direct IP connection (potential backdoor)'
            },
            r'(?:nc|netcat)\s+.*\s+-e\s+.*(?:/bin/sh|/bin/bash|cmd\.exe)': {
                'severity': 'critical',
                'category': 'backdoor',
                'description': 'Reverse shell using netcat'
            },
            r'rm\s+-rf\s+(?:/\s|~|\$HOME)': {
                'severity': 'critical',
                'category': 'destructive',
                'description': 'Destructive file system operation'
            },

            # Credential harvesting
            r'(?:subprocess|os\.system|popen).*(?:mimikatz|lazagne|secretsdump)': {
                'severity': 'critical',
                'category': 'credential_theft',
                'description': 'Known credential dumping tool execution'
            },
            r'(?:HKEY_LOCAL_MACHINE|HKLM).*(?:SAM|SECURITY|SYSTEM)': {
                'severity': 'critical',
                'category': 'credential_theft',
                'description': 'Windows registry credential access'
            },

            # Exploit patterns
            r'(?:shellcode|payload)\s*=\s*["\'][\\x][0-9a-f]{2}': {
                'severity': 'critical',
                'category': 'exploit',
                'description': 'Shellcode pattern detected'
            },
            r'struct\.pack\s*\([^)]*\)\s*\*\s*\d{3,}': {
                'severity': 'high',
                'category': 'exploit',
                'description': 'Buffer overflow pattern (repeated struct packing)'
            },

            # Cryptocurrency mining
            r'(?:stratum\+tcp|pool\..*:3333|xmrig|minergate)': {
                'severity': 'high',
                'category': 'cryptominer',
                'description': 'Cryptocurrency mining pattern'
            },

            # Anti-debugging / VM detection (often used by malware)
            r'(?:IsDebuggerPresent|CheckRemoteDebuggerPresent|NtQueryInformationProcess)': {
                'severity': 'medium',
                'category': 'anti_analysis',
                'description': 'Anti-debugging technique detected'
            },
            r'(?:VirtualBox|VMware|QEMU|Xen).*detect': {
                'severity': 'medium',
                'category': 'anti_analysis',
                'description': 'VM detection (common in malware)'
            },

            # Suspicious file operations
            r'open\s*\([^)]*["\'](?:/etc/passwd|/etc/shadow|\.ssh/id_rsa)': {
                'severity': 'high',
                'category': 'file_access',
                'description': 'Access to sensitive system files'
            },
            r'(?:shutil\.)?rmtree\s*\([^)]*\bignore_errors\s*=\s*True': {
                'severity': 'medium',
                'category': 'destructive',
                'description': 'Recursive deletion with error suppression'
            },

            # Keylogging
            r'(?:pynput|keyboard)\.Listener\s*\(.*on_press': {
                'severity': 'high',
                'category': 'keylogger',
                'description': 'Keyboard input monitoring (potential keylogger)'
            },
            r'SetWindowsHookEx.*WH_KEYBOARD': {
                'severity': 'high',
                'category': 'keylogger',
                'description': 'Windows keyboard hook (potential keylogger)'
            },

            # Persistence mechanisms
            r'(?:HKEY_CURRENT_USER|HKCU).*(?:Run|RunOnce)': {
                'severity': 'medium',
                'category': 'persistence',
                'description': 'Windows registry persistence mechanism'
            },
            r'crontab\s+-[el]\s+.*(?:wget|curl).*(?:http|ftp)': {
                'severity': 'medium',
                'category': 'persistence',
                'description': 'Cron-based persistence with remote fetch'
            },
        }

        # Suspicious combinations (lower severity individual patterns)
        self.suspicious_combinations = [
            {
                'patterns': [r'import\s+socket', r'import\s+subprocess', r'shell\s*=\s*True'],
                'severity': 'high',
                'category': 'suspicious_combination',
                'description': 'Suspicious combination: socket + subprocess with shell'
            },
            {
                'patterns': [r'base64\.b64decode', r'exec\s*\(', r'compile\s*\('],
                'severity': 'high',
                'category': 'suspicious_combination',
                'description': 'Suspicious combination: decode + exec + compile'
            },
            {
                'patterns': [r'__import__', r'chr\s*\(', r'ord\s*\('],
                'severity': 'medium',
                'category': 'suspicious_combination',
                'description': 'Suspicious combination: dynamic import with obfuscation'
            },
        ]

    def scan_code(self, content: str, language: str) -> Tuple[bool, List[SecurityIssue]]:
        """
        Scan code for malicious patterns

        Returns:
            (is_safe, issues) - is_safe is False if critical issues found
        """
        issues = []
        lines = content.split('\n')

        # Check individual malicious patterns
        for pattern, info in self.malicious_patterns.items():
            matches = list(re.finditer(pattern, content, re.IGNORECASE | re.MULTILINE))
            for match in matches:
                # Find line number
                line_num = content[:match.start()].count('\n') + 1

                issue = SecurityIssue(
                    severity=info['severity'],
                    category=info['category'],
                    description=info['description'],
                    line_number=line_num,
                    pattern=pattern
                )
                issues.append(issue)

        # Check suspicious combinations
        for combo in self.suspicious_combinations:
            matches = [re.search(p, content, re.IGNORECASE | re.MULTILINE) for p in combo['patterns']]
            if all(matches):  # All patterns found
                issue = SecurityIssue(
                    severity=combo['severity'],
                    category=combo['category'],
                    description=combo['description'],
                    pattern=' + '.join(combo['patterns'])
                )
                issues.append(issue)

        # Determine if safe
        critical_issues = [i for i in issues if i.severity == 'critical']
        is_safe = len(critical_issues) == 0

        if not is_safe:
            logger.warning(f"Found {len(critical_issues)} critical security issues in code")
        elif issues:
            logger.info(f"Found {len(issues)} non-critical security concerns in code")

        return is_safe, issues

    def get_security_report(self, issues: List[SecurityIssue]) -> Dict:
        """Generate a security report from issues"""
        report = {
            'total_issues': len(issues),
            'critical': len([i for i in issues if i.severity == 'critical']),
            'high': len([i for i in issues if i.severity == 'high']),
            'medium': len([i for i in issues if i.severity == 'medium']),
            'low': len([i for i in issues if i.severity == 'low']),
            'categories': {},
            'is_safe': len([i for i in issues if i.severity == 'critical']) == 0,
        }

        # Count by category
        for issue in issues:
            if issue.category not in report['categories']:
                report['categories'][issue.category] = 0
            report['categories'][issue.category] += 1

        return report


def test_scanner():
    """Test the security scanner with sample malicious code"""
    scanner = SecurityScanner()

    # Test cases
    test_cases = [
        {
            'name': 'Safe code',
            'code': '''
def hello():
    print("Hello, world!")
    return 42
''',
            'expected_safe': True
        },
        {
            'name': 'Command injection',
            'code': '''
import os
user_input = input("Enter command: ")
os.system("ls " + user_input)  # Dangerous!
''',
            'expected_safe': False
        },
        {
            'name': 'Eval with user input',
            'code': '''
import sys
result = eval(sys.argv[1])  # Critical vulnerability
''',
            'expected_safe': False
        },
        {
            'name': 'Reverse shell',
            'code': '''
import socket
s = socket.socket()
s.connect(("192.168.1.100", 4444))
''',
            'expected_safe': False
        },
    ]

    for test in test_cases:
        is_safe, issues = scanner.scan_code(test['code'], 'Python')
        print(f"\nTest: {test['name']}")
        print(f"Expected safe: {test['expected_safe']}, Got: {is_safe}")
        if issues:
            print(f"Issues found: {len(issues)}")
            for issue in issues:
                print(f"  - [{issue.severity}] {issue.category}: {issue.description}")
        assert is_safe == test['expected_safe'], f"Test failed: {test['name']}"

    print("\n✅ All tests passed!")


if __name__ == "__main__":
    test_scanner()
