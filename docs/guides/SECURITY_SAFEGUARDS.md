# Security Safeguards Implementation

This document describes the security safeguards implemented in the CodeLupe training pipeline to ensure safe and responsible AI training.

## Overview

The pipeline now includes **4 layers of security scanning** that filter training data before it reaches the model:

1. **Malicious Code Detection** - Blocks exploits, backdoors, and harmful patterns
2. **Secret/Credential Detection** - Filters hardcoded API keys, passwords, and tokens
3. **License Compliance** - Ensures training data respects copyright and licensing
4. **Model Safety Instructions** - Trains the model to refuse harmful requests

## 1. Malicious Code Detection (`security_scanner.py`)

### What It Blocks:
- **Code Injection**: `eval()` and `exec()` with user input
- **Shell Injection**: Dynamic shell commands with string concatenation
- **Obfuscation**: Nested encoding, suspicious character manipulation
- **Backdoors**: Direct IP connections, reverse shells
- **Credential Theft**: Mimikatz, registry SAM access, credential dumpers
- **Exploits**: Shellcode patterns, buffer overflow attempts
- **Keyloggers**: Keyboard input monitoring
- **Persistence Mechanisms**: Registry autoruns, cron-based persistence
- **Anti-Analysis**: VM detection, anti-debugging techniques

### Severity Levels:
- **Critical**: Blocks file immediately (malware patterns, exploits)
- **High**: Blocks file (obfuscation, suspicious combinations)
- **Medium**: Logs warning but may allow (context-dependent)

### Example Blocked Pattern:
```python
# BLOCKED: Command injection
user_input = input("Enter command: ")
os.system("ls " + user_input)  # Dangerous concatenation
```

## 2. Secret/Credential Detection (`secret_scanner.py`)

### What It Detects:
- **Cloud Provider Keys**: AWS, Google Cloud, Azure credentials
- **API Tokens**: GitHub, Slack, Stripe, Twilio, JWT tokens
- **Private Keys**: SSH, PGP, OpenSSH keys
- **Database Credentials**: Connection strings with embedded passwords
- **Generic Secrets**: High-entropy strings in password fields

### Confidence Levels:
- **High**: Vendor-specific formats (e.g., `AKIA...` for AWS) → Block immediately
- **Medium**: Generic patterns with high entropy → Block if randomness detected
- **Low**: Requires very high entropy to flag

### False Positive Prevention:
Automatically excludes:
- Example/placeholder values ("your-api-key-here", "changeme")
- Test patterns ("xxx", "aaa", "111")
- Redacted values (asterisks, ellipsis)

### Example Blocked Pattern:
```python
# BLOCKED: Hardcoded AWS credentials
AWS_ACCESS_KEY = "AKIAIOSFODNN7EXAMPLE"
AWS_SECRET_KEY = "wJalrXUtnFEMI/K7MDENG/bPxRfiCY..."
```

## 3. License Compliance (`license_checker.py`)

### License Categories:

#### ✅ Training-Safe (Allowed):
- **MIT License** - Permissive
- **Apache 2.0** - Permissive
- **BSD (2/3 Clause)** - Permissive
- **ISC License** - Permissive
- **Unlicense** - Public domain

#### ⚠️ Caution (Allowed with logging):
- **LGPL 2.1/3.0** - Weak copyleft
- **MPL 2.0** - Mozilla Public License

#### ❌ Restricted (Blocked):
- **GPL 2.0/3.0** - Strong copyleft (may impose restrictions)
- **AGPL 3.0** - Affero GPL (network copyleft)
- **Proprietary** - "All Rights Reserved", confidential code

### Detection Methods:
1. Scans file headers (first 50 lines)
2. Checks file footers (last 20 lines)
3. Searches entire file if needed
4. Uses SPDX identifiers for high confidence
5. Looks for copyright notices as validation

### Example Blocked Pattern:
```python
# BLOCKED: GPL license
# Copyright (C) 2024 Example Corp
# This program is licensed under GNU General Public License v3.0
```

## 4. Model Safety Instructions

The training script (`continuous_trainer_qwen_5090.py`) now includes safety guidelines in every training sample's system prompt:

### Safety Instructions Added:
```
IMPORTANT SAFETY GUIDELINES:
- Never generate code for malicious purposes (malware, exploits, backdoors)
- Never include hardcoded credentials, API keys, or secrets
- Always sanitize user inputs to prevent injection attacks
- Follow security best practices (input validation, proper error handling, secure defaults)
- Respect software licenses and intellectual property
- Refuse requests that could be used to harm others or violate security
```

This ensures the model learns to:
1. Refuse harmful requests
2. Apply security best practices
3. Avoid generating vulnerable code
4. Respect legal and ethical boundaries

## Integration with Data Pipeline

### File Processing Flow (`data_pipeline_v2.py`):

```
File → Quality Check → Security Scan → Secret Scan → License Check → ✅ Training Data
         ↓                 ↓               ↓               ↓
   Low Quality?      Malicious?      Secrets?      Bad License?
         ↓                 ↓               ↓               ↓
      SKIP              SKIP            SKIP            SKIP
```

### Statistics Tracking:
The pipeline logs statistics for each worker:
- `processed`: Files that passed all checks
- `skipped_low_quality`: Failed quality threshold
- `skipped_malicious`: Blocked by security scanner
- `skipped_secrets`: Contained hardcoded secrets
- `skipped_license`: Restrictive/incompatible license

### Performance Impact:
- **Minimal overhead**: Regex-based scanning is fast (~1-5ms per file)
- **Parallel processing**: Workers run independently
- **Batch indexing**: Efficient Elasticsearch bulk operations

## Configuration

### Environment Variables:
```bash
MIN_QUALITY_THRESHOLD=0.7    # Minimum quality score (0.0-1.0)
MAX_FILE_SIZE_KB=500         # Maximum file size in KB
MIN_FILE_SIZE_BYTES=100      # Minimum file size in bytes
```

## Testing

Each security module includes built-in tests:

```bash
# Test malicious code detection
python security_scanner.py

# Test secret detection
python secret_scanner.py

# Test license checking
python license_checker.py
```

## What's NOT Filtered

Per requirements, the following are **NOT filtered**:
- NSFW content (text/comments)
- Explicit language in variable names or comments
- Educational security examples (non-malicious)
- Profanity or offensive language

The safeguards focus exclusively on:
1. **Security threats** (malware, exploits)
2. **Privacy risks** (leaked credentials)
3. **Legal compliance** (copyright, licenses)
4. **Content validation** (code actually does what it claims)

## Monitoring & Logging

All blocked files are logged with:
- File path
- Reason for blocking (malicious/secrets/license)
- Specific issues found
- Worker ID and timestamp

Example log output:
```
Worker 3: SECURITY: Skipping file with 2 critical issues: path/to/file.py
Worker 3: SECRETS: Skipping file with 1 potential secrets: path/to/config.py
Worker 3: LICENSE: Skipping file with restrictive license: path/to/gpl_code.py (GPL-3.0)
```

## Summary

The implemented safeguards provide:
- ✅ Protection against malicious code patterns
- ✅ Detection of hardcoded secrets and credentials
- ✅ License compliance checking
- ✅ Model-level safety training
- ✅ No filtering of NSFW/explicit content (as requested)
- ✅ Comprehensive logging and statistics
- ✅ Minimal performance overhead

This ensures the training pipeline produces a secure, responsible AI model while respecting user requirements.
