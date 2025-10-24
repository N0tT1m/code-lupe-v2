#!/usr/bin/env python3
"""
Safety Detection System
Comprehensive content filtering and security analysis for AI training data
"""

import re
import json
import hashlib
import requests
from typing import List, Dict, Tuple, Optional, Set
from dataclasses import dataclass
from enum import Enum
import logging

class SafetyLevel(Enum):
    SAFE = "safe"
    WARNING = "warning"
    BLOCKED = "blocked"
    
class DetectionType(Enum):
    TOXICITY = "toxicity"
    SECURITY_VULN = "security_vulnerability"
    MALICIOUS_CODE = "malicious_code"
    PII = "personally_identifiable_info"
    LICENSE_VIOLATION = "license_violation"
    CODE_INJECTION = "code_injection"
    HARMFUL_INSTRUCTION = "harmful_instruction"
    PROBLEMATIC_CODE = "problematic_code"

@dataclass
class DetectionResult:
    detection_type: DetectionType
    safety_level: SafetyLevel
    confidence: float
    details: str
    matched_patterns: List[str]
    suggestions: List[str]

class ToxicityDetector:
    """Detects toxic content while allowing NSFW content"""
    
    def __init__(self):
        self.toxic_patterns = [
            # Hate speech patterns
            r'\b(?:hate|kill|murder|eliminate)\s+(?:all\s+)?(?:jews|muslims|christians|blacks|whites|asians|latinos|women|men|gays|trans)\b',
            r'\b(?:jews|muslims|christians|blacks|whites|asians|latinos)\s+(?:are|should\s+be)\s+(?:killed|eliminated|destroyed)\b',
            
            # Extreme violence (non-fictional)
            r'\bhow\s+to\s+(?:kill|murder|assassinate|torture)\s+(?:someone|people|a\s+person)\b',
            r'\bways\s+to\s+(?:kill|harm|hurt)\s+(?:yourself|others|children)\b',
            
            # Harassment and bullying
            r'\b(?:kill\s+yourself|kys|go\s+die|should\s+die)\b',
            r'\byou\s+(?:are|should\s+be)\s+(?:worthless|garbage|trash|dead)\b',
            
            # Child exploitation (strict)
            r'\b(?:child|kid|minor|underage).*(?:sexual|nude|naked|porn|sex)\b',
            r'\bsexual.*(?:child|kid|minor|underage)\b',
            
            # Doxxing patterns
            r'\b(?:home\s+address|real\s+name|phone\s+number|ssn|social\s+security).*(?:of|for).*(?:this\s+person|him|her|them)\b',
        ]
        
        # Compiled patterns for performance
        self.compiled_patterns = [re.compile(pattern, re.IGNORECASE) for pattern in self.toxic_patterns]
        
        # NSFW content is explicitly allowed - no filtering
        
    def detect(self, text: str) -> DetectionResult:
        matched_patterns = []
        max_confidence = 0.0
        
        for i, pattern in enumerate(self.compiled_patterns):
            matches = pattern.findall(text)
            if matches:
                matched_patterns.append(self.toxic_patterns[i])
                max_confidence = max(max_confidence, 0.9)
        
        if matched_patterns:
            safety_level = SafetyLevel.BLOCKED if max_confidence > 0.8 else SafetyLevel.WARNING
            return DetectionResult(
                detection_type=DetectionType.TOXICITY,
                safety_level=safety_level,
                confidence=max_confidence,
                details=f"Detected potentially toxic content: {', '.join(matched_patterns[:3])}",
                matched_patterns=matched_patterns,
                suggestions=["Consider rephrasing to remove harmful language", "Review content for bias"]
            )
        
        return DetectionResult(
            detection_type=DetectionType.TOXICITY,
            safety_level=SafetyLevel.SAFE,
            confidence=0.0,
            details="No toxic content detected",
            matched_patterns=[],
            suggestions=[]
        )

class SecurityVulnerabilityDetector:
    """Detects security vulnerabilities in code"""
    
    def __init__(self):
        self.vuln_patterns = [
            # SQL Injection
            (r"(?:SELECT|INSERT|UPDATE|DELETE).*\+.*(?:input|request|param)", "SQL Injection via string concatenation"),
            (r"execute\(.*\+.*\)", "Dynamic SQL execution with concatenation"),
            
            # Command Injection
            (r"(?:system|exec|shell_exec|passthru|popen)\(.*\$", "Command injection vulnerability"),
            (r"subprocess\.(?:call|run|Popen).*shell=True.*input", "Shell injection in subprocess"),
            
            # XSS
            (r"innerHTML\s*=.*(?:input|request|param)", "Potential XSS via innerHTML"),
            (r"document\.write\(.*(?:input|request|param)", "XSS via document.write"),
            
            # Path Traversal
            (r"(?:open|file|read).*\.\./", "Path traversal vulnerability"),
            (r"include.*\$_(?:GET|POST|REQUEST)", "File inclusion vulnerability"),
            
            # Hardcoded credentials
            (r"(?:password|pwd|pass)\s*=\s*['\"][\w!@#$%^&*]{6,}", "Hardcoded password"),
            (r"(?:api_key|secret_key|private_key)\s*=\s*['\"][^'\"]+", "Hardcoded API key"),
            
            # Crypto weaknesses
            (r"MD5|SHA1(?!256|512)", "Weak cryptographic hash"),
            (r"DES|3DES|RC4", "Weak encryption algorithm"),
        ]
        
        self.compiled_vulns = [(re.compile(pattern, re.IGNORECASE), desc) for pattern, desc in self.vuln_patterns]
    
    def detect(self, text: str) -> DetectionResult:
        matched_patterns = []
        vulnerabilities = []
        
        for pattern, description in self.compiled_vulns:
            if pattern.search(text):
                matched_patterns.append(pattern.pattern)
                vulnerabilities.append(description)
        
        if vulnerabilities:
            confidence = min(0.9, len(vulnerabilities) * 0.3)
            return DetectionResult(
                detection_type=DetectionType.SECURITY_VULN,
                safety_level=SafetyLevel.WARNING,
                confidence=confidence,
                details=f"Security vulnerabilities detected: {', '.join(vulnerabilities[:3])}",
                matched_patterns=matched_patterns,
                suggestions=[
                    "Use parameterized queries for database operations",
                    "Validate and sanitize all user inputs",
                    "Use strong cryptographic algorithms",
                    "Avoid hardcoded credentials"
                ]
            )
        
        return DetectionResult(
            detection_type=DetectionType.SECURITY_VULN,
            safety_level=SafetyLevel.SAFE,
            confidence=0.0,
            details="No security vulnerabilities detected",
            matched_patterns=[],
            suggestions=[]
        )

class MaliciousCodeDetector:
    """Detects malicious code patterns"""
    
    def __init__(self):
        self.malicious_patterns = [
            # Malware behaviors
            (r"(?:delete|remove|rm\s+-rf).*(?:\/\*|\*\.)", "File deletion patterns"),
            (r"fork\(\).*while.*fork\(\)", "Fork bomb pattern"),
            (r"(?:keylogger|keystroke|capture.*key)", "Keylogging behavior"),
            
            # Network exploitation
            (r"socket.*(?:reverse|bind).*shell", "Reverse/bind shell"),
            (r"nc\s+-[el].*\/bin\/(?:bash|sh)", "Netcat shell"),
            
            # System exploitation
            (r"\/proc\/self\/mem", "Memory manipulation"),
            (r"mprotect.*PROT_EXEC", "Memory execution modification"),
            (r"ptrace.*PTRACE_POKETEXT", "Process memory injection"),
            
            # Data exfiltration
            (r"(?:curl|wget|fetch).*(?:upload|send).*\/home", "Data exfiltration"),
            (r"tar.*\|.*(?:nc|netcat|curl)", "Data compression and transmission"),
            
            # Persistence mechanisms
            (r"crontab.*(?:wget|curl|download)", "Cron-based persistence"),
            (r"\/etc\/passwd.*echo", "Password file modification"),
        ]
        
        self.compiled_malicious = [(re.compile(pattern, re.IGNORECASE), desc) for pattern, desc in self.malicious_patterns]
    
    def detect(self, text: str) -> DetectionResult:
        matched_patterns = []
        malicious_behaviors = []
        
        for pattern, description in self.compiled_malicious:
            if pattern.search(text):
                matched_patterns.append(pattern.pattern)
                malicious_behaviors.append(description)
        
        if malicious_behaviors:
            confidence = min(0.95, len(malicious_behaviors) * 0.4)
            safety_level = SafetyLevel.BLOCKED if confidence > 0.7 else SafetyLevel.WARNING
            
            return DetectionResult(
                detection_type=DetectionType.MALICIOUS_CODE,
                safety_level=safety_level,
                confidence=confidence,
                details=f"Malicious code patterns detected: {', '.join(malicious_behaviors[:3])}",
                matched_patterns=matched_patterns,
                suggestions=[
                    "Review code for malicious intent",
                    "Verify code source and purpose",
                    "Consider sandboxed execution"
                ]
            )
        
        return DetectionResult(
            detection_type=DetectionType.MALICIOUS_CODE,
            safety_level=SafetyLevel.SAFE,
            confidence=0.0,
            details="No malicious code patterns detected",
            matched_patterns=[],
            suggestions=[]
        )

class PIIDetector:
    """Detects Personally Identifiable Information"""
    
    def __init__(self):
        self.pii_patterns = [
            # SSN patterns
            (r"\b\d{3}-\d{2}-\d{4}\b", "Social Security Number"),
            (r"\b\d{9}\b", "Potential SSN (9 digits)"),
            
            # Credit card patterns
            (r"\b(?:4\d{3}|5[1-5]\d{2}|3[47]\d{2})\s?\d{4}\s?\d{4}\s?\d{4}\b", "Credit card number"),
            
            # Phone numbers
            (r"\b(?:\+1\s?)?\(?[2-9]\d{2}\)?\s?[2-9]\d{2}\s?\d{4}\b", "Phone number"),
            
            # Email addresses (contextual)
            (r"\b[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}\b", "Email address"),
            
            # IP addresses (when in sensitive context)
            (r"\b(?:\d{1,3}\.){3}\d{1,3}\b", "IP address"),
            
            # Driver's license (general pattern)
            (r"\b[A-Z]{1,2}\d{6,8}\b", "Potential driver's license"),
            
            # Bank account numbers
            (r"\b\d{8,17}\b", "Potential bank account number"),
        ]
        
        self.compiled_pii = [(re.compile(pattern), desc) for pattern, desc in self.pii_patterns]
    
    def detect(self, text: str) -> DetectionResult:
        matched_patterns = []
        pii_types = []
        
        for pattern, description in self.compiled_pii:
            matches = pattern.findall(text)
            if matches:
                matched_patterns.extend(matches)
                pii_types.append(description)
        
        if pii_types:
            confidence = min(0.8, len(set(pii_types)) * 0.25)
            return DetectionResult(
                detection_type=DetectionType.PII,
                safety_level=SafetyLevel.WARNING,
                confidence=confidence,
                details=f"PII detected: {', '.join(set(pii_types))}",
                matched_patterns=matched_patterns,
                suggestions=[
                    "Remove or anonymize personal information",
                    "Replace with placeholder values",
                    "Ensure compliance with privacy regulations"
                ]
            )
        
        return DetectionResult(
            detection_type=DetectionType.PII,
            safety_level=SafetyLevel.SAFE,
            confidence=0.0,
            details="No PII detected",
            matched_patterns=[],
            suggestions=[]
        )

class LicenseComplianceDetector:
    """Detects license compliance issues"""
    
    def __init__(self):
        self.copyleft_licenses = [
            "GPL", "AGPL", "LGPL", "MPL", "EPL", "CDDL", "CPL"
        ]
        
        self.proprietary_indicators = [
            "All rights reserved", "Proprietary", "Confidential", 
            "Trade secret", "Copyright.*(?:Inc|Corp|Ltd|LLC)"
        ]
        
        self.license_patterns = []
        for license_name in self.copyleft_licenses:
            self.license_patterns.append((
                re.compile(rf"\b{license_name}\b", re.IGNORECASE),
                f"Copyleft license: {license_name}"
            ))
        
        for indicator in self.proprietary_indicators:
            self.license_patterns.append((
                re.compile(indicator, re.IGNORECASE),
                "Proprietary content indicator"
            ))
    
    def detect(self, text: str) -> DetectionResult:
        matched_patterns = []
        license_issues = []
        
        for pattern, description in self.license_patterns:
            if pattern.search(text):
                matched_patterns.append(pattern.pattern)
                license_issues.append(description)
        
        if license_issues:
            confidence = min(0.7, len(license_issues) * 0.3)
            return DetectionResult(
                detection_type=DetectionType.LICENSE_VIOLATION,
                safety_level=SafetyLevel.WARNING,
                confidence=confidence,
                details=f"License compliance issues: {', '.join(set(license_issues))}",
                matched_patterns=matched_patterns,
                suggestions=[
                    "Verify license compatibility",
                    "Check if content can be used for training",
                    "Consider license obligations"
                ]
            )
        
        return DetectionResult(
            detection_type=DetectionType.LICENSE_VIOLATION,
            safety_level=SafetyLevel.SAFE,
            confidence=0.0,
            details="No license compliance issues detected",
            matched_patterns=[],
            suggestions=[]
        )

class CodeInjectionDetector:
    """Detects code injection attempts"""
    
    def __init__(self):
        self.injection_patterns = [
            # Code injection patterns
            (r"eval\(.*(?:input|request|param)", "JavaScript eval injection"),
            (r"exec\(.*(?:input|request|param)", "Python exec injection"),
            (r"Function\(.*(?:input|request|param)", "JavaScript Function constructor injection"),
            
            # Template injection
            (r"\{\{.*(?:request|input|param)", "Template injection"),
            (r"<%.*(?:request|input|param)", "JSP/ASP injection"),
            
            # Command injection
            (r"`.*\$\{", "Command substitution injection"),
            (r"\$\(.*(?:input|request|param)", "Command substitution"),
            
            # NoSQL injection
            (r"\$where.*(?:input|request|param)", "MongoDB injection"),
            (r"\$regex.*(?:input|request|param)", "NoSQL regex injection"),
        ]
        
        self.compiled_injections = [(re.compile(pattern, re.IGNORECASE), desc) for pattern, desc in self.injection_patterns]
    
    def detect(self, text: str) -> DetectionResult:
        matched_patterns = []
        injection_types = []
        
        for pattern, description in self.compiled_injections:
            if pattern.search(text):
                matched_patterns.append(pattern.pattern)
                injection_types.append(description)
        
        if injection_types:
            confidence = min(0.9, len(injection_types) * 0.4)
            return DetectionResult(
                detection_type=DetectionType.CODE_INJECTION,
                safety_level=SafetyLevel.BLOCKED,
                confidence=confidence,
                details=f"Code injection patterns detected: {', '.join(injection_types)}",
                matched_patterns=matched_patterns,
                suggestions=[
                    "Use parameterized queries and prepared statements",
                    "Validate and sanitize all inputs",
                    "Avoid dynamic code execution with user input"
                ]
            )
        
        return DetectionResult(
            detection_type=DetectionType.CODE_INJECTION,
            safety_level=SafetyLevel.SAFE,
            confidence=0.0,
            details="No code injection patterns detected",
            matched_patterns=[],
            suggestions=[]
        )

class HarmfulInstructionDetector:
    """Detects harmful instructions while preserving educational content"""
    
    def __init__(self):
        self.harmful_patterns = [
            # Illegal activities (specific intent)
            (r"how\s+to\s+(?:make|create|build)\s+(?:bombs?|explosives?|weapons?)", "Weapon creation instructions"),
            (r"steps\s+to\s+(?:hack|break\s+into|steal\s+from)", "Hacking/theft instructions"),
            (r"guide\s+to\s+(?:drug\s+manufacturing|money\s+laundering)", "Illegal activity guide"),
            
            # Harm to others
            (r"how\s+to\s+(?:poison|drug|harm)\s+someone", "Instructions to harm others"),
            (r"ways\s+to\s+(?:stalk|harass|intimidate)", "Harassment instructions"),
            
            # Self-harm (specific methods)
            (r"(?:suicide|self-harm)\s+(?:methods|ways|techniques)", "Self-harm instructions"),
            (r"how\s+to\s+(?:cut|hurt)\s+yourself", "Self-injury instructions"),
            
            # Fraud and scams
            (r"how\s+to\s+(?:scam|defraud|steal\s+identity)", "Fraud instructions"),
            (r"fake\s+(?:documents|ids|certificates)", "Document forgery"),
        ]
        
        # Educational exceptions (these are typically okay)
        self.educational_exceptions = [
            r"(?:academic|educational|research|study|learn|understand)",
            r"(?:history|historical|documentary|literature)",
            r"(?:prevention|awareness|safety|security)",
        ]
        
        self.compiled_harmful = [(re.compile(pattern, re.IGNORECASE), desc) for pattern, desc in self.harmful_patterns]
        self.compiled_exceptions = [re.compile(pattern, re.IGNORECASE) for pattern in self.educational_exceptions]
    
    def detect(self, text: str) -> DetectionResult:
        matched_patterns = []
        harmful_instructions = []
        
        # Check for educational context first
        is_educational = any(pattern.search(text) for pattern in self.compiled_exceptions)
        
        for pattern, description in self.compiled_harmful:
            if pattern.search(text):
                matched_patterns.append(pattern.pattern)
                harmful_instructions.append(description)
        
        if harmful_instructions:
            # Reduce severity if educational context is detected
            base_confidence = min(0.9, len(harmful_instructions) * 0.4)
            confidence = base_confidence * (0.5 if is_educational else 1.0)
            
            safety_level = SafetyLevel.WARNING if is_educational else SafetyLevel.BLOCKED
            
            context_note = " (educational context detected)" if is_educational else ""
            
            return DetectionResult(
                detection_type=DetectionType.HARMFUL_INSTRUCTION,
                safety_level=safety_level,
                confidence=confidence,
                details=f"Harmful instructions detected: {', '.join(harmful_instructions)}{context_note}",
                matched_patterns=matched_patterns,
                suggestions=[
                    "Review content for harmful intent",
                    "Consider educational value vs. potential harm",
                    "Add appropriate warnings or disclaimers"
                ]
            )
        
        return DetectionResult(
            detection_type=DetectionType.HARMFUL_INSTRUCTION,
            safety_level=SafetyLevel.SAFE,
            confidence=0.0,
            details="No harmful instructions detected",
            matched_patterns=[],
            suggestions=[]
        )

class ProblematicCodeDetector:
    """Detects problematic variable names, comments, and code content"""
    
    def __init__(self):
        self.problematic_patterns = [
            # Racial slurs and offensive terms
            (r'\b(?:nigger|nigga|faggot|fag|retard|retarded|spic|chink|gook|kike|wetback|raghead|towelhead|sandnigger)\w*\b', "Racial/ethnic slur"),
            
            # Offensive variable/function names
            (r'(?:var|let|const|def|function|class|int|string|bool|float|double)\s+(?:hitler|nazi|kkk|genocide|slave|master_race)\w*', "Offensive identifier"),
            
            # Discriminatory comments
            (r'(?://|#|/\*).*(?:women|blacks|jews|muslims|gays|trans|immigrants).*(?:are|should|always|never).*(?:stupid|inferior|bad|useless|trash|garbage)', "Discriminatory comment"),
            (r'(?://|#|/\*).*(?:only|real|true)\s+(?:men|whites|christians).*(?:can|should|deserve)', "Supremacist comment"),
            
            # Holocaust denial/minimization
            (r'(?://|#|/\*).*(?:holocaust|6\s*million).*(?:fake|lie|exaggerated|myth|hoax)', "Holocaust denial"),
            
            # Sexist/misogynistic content
            (r'(?://|#|/\*).*(?:women|girls|females).*(?:belong\s+in|should\s+stay\s+in|only\s+good\s+for)', "Sexist comment"),
            (r'(?:var|let|const|def)\s+(?:kitchen|sandwich|make_me)\w*', "Sexist variable name"),
            
            # Homophobic/transphobic content
            (r'(?://|#|/\*).*(?:gay|trans|lgbt).*(?:mental\s+illness|disorder|disease|wrong|sin)', "Homophobic/transphobic comment"),
            
            # Violence against groups
            (r'(?://|#|/\*).*(?:kill|eliminate|remove)\s+all\s+(?:jews|muslims|blacks|gays|immigrants)', "Violent threat against group"),
            
            # Nazi/white supremacist symbols/references
            (r'\b(?:1488|14/88|blood\s+and\s+soil|jews\s+will\s+not\s+replace\s+us)\b', "White supremacist reference"),
            (r'(?:var|let|const|def)\s+(?:heil|sieg|aryan|pure_blood)\w*', "Nazi reference in code"),
            
            # Derogatory disability terms
            (r'(?://|#|/\*).*(?:disabled|handicapped|autistic).*(?:people\s+are|should\s+be).*(?:useless|burden|waste)', "Ableist comment"),
            
            # Religious bigotry
            (r'(?://|#|/\*).*(?:all\s+)?(?:muslims|jews|christians|hindus).*(?:are|should\s+be).*(?:terrorists|evil|destroyed)', "Religious bigotry"),
            
            # Coded offensive terms (common internet slang)
            (r'\b(?:dindu|googles|skypes|basketball\s+americans|joggers)\b', "Coded racial slur"),
            
            # Offensive function/method names
            (r'(?:function|def|method)\s+(?:lynch|hang|burn|gas)(?:[A-Z][a-z]+)+', "Violent function name"),
        ]
        
        # Common false positives to exclude
        self.exceptions = [
            r'\b(?:master|slave)\b.*(?:database|db|replication|git|branch)',  # Technical terms
            r'\b(?:black|white)(?:list|box|hole|board|screen)',  # Technical color terms
            r'(?:var|let|const)\s+(?:master|slave).*(?:process|thread|connection)',  # System terms
            r'//.*(?:TODO|FIXME|NOTE|WARNING).*master',  # Comments about master branch/process
        ]
        
        self.compiled_patterns = [(re.compile(pattern, re.IGNORECASE), desc) for pattern, desc in self.problematic_patterns]
        self.compiled_exceptions = [re.compile(pattern, re.IGNORECASE) for pattern in self.exceptions]
    
    def detect(self, text: str) -> DetectionResult:
        matched_patterns = []
        problematic_content = []
        
        # Check for exceptions first
        has_exception = any(pattern.search(text) for pattern in self.compiled_exceptions)
        
        for pattern, description in self.compiled_patterns:
            matches = pattern.findall(text)
            if matches and not has_exception:
                matched_patterns.extend(matches if isinstance(matches[0], str) else [m[0] for m in matches])
                problematic_content.append(description)
        
        if problematic_content:
            confidence = min(0.95, len(set(problematic_content)) * 0.3)
            safety_level = SafetyLevel.BLOCKED if confidence > 0.7 else SafetyLevel.WARNING
            
            return DetectionResult(
                detection_type=DetectionType.PROBLEMATIC_CODE,
                safety_level=safety_level,
                confidence=confidence,
                details=f"Problematic code content detected: {', '.join(set(problematic_content))}",
                matched_patterns=matched_patterns,
                suggestions=[
                    "Replace offensive variable/function names with neutral alternatives",
                    "Remove discriminatory comments and replace with professional language",
                    "Review code for bias and inclusive language",
                    "Consider impact on diverse development teams"
                ]
            )
        
        return DetectionResult(
            detection_type=DetectionType.PROBLEMATIC_CODE,
            safety_level=SafetyLevel.SAFE,
            confidence=0.0,
            details="No problematic code content detected",
            matched_patterns=[],
            suggestions=[]
        )

class ComprehensiveSafetyDetector:
    """Main safety detection system that coordinates all detectors"""
    
    def __init__(self):
        self.detectors = {
            DetectionType.TOXICITY: ToxicityDetector(),
            DetectionType.SECURITY_VULN: SecurityVulnerabilityDetector(),
            DetectionType.MALICIOUS_CODE: MaliciousCodeDetector(),
            DetectionType.PII: PIIDetector(),
            DetectionType.LICENSE_VIOLATION: LicenseComplianceDetector(),
            DetectionType.CODE_INJECTION: CodeInjectionDetector(),
            DetectionType.HARMFUL_INSTRUCTION: HarmfulInstructionDetector(),
            DetectionType.PROBLEMATIC_CODE: ProblematicCodeDetector(),
        }
        
        self.logger = logging.getLogger(__name__)
    
    def analyze_content(self, text: str, skip_detectors: Optional[List[DetectionType]] = None) -> Dict[DetectionType, DetectionResult]:
        """Run all safety detections on the given text"""
        results = {}
        skip_detectors = skip_detectors or []
        
        for detection_type, detector in self.detectors.items():
            if detection_type not in skip_detectors:
                try:
                    results[detection_type] = detector.detect(text)
                except Exception as e:
                    self.logger.error(f"Error in {detection_type.value} detection: {e}")
                    results[detection_type] = DetectionResult(
                        detection_type=detection_type,
                        safety_level=SafetyLevel.WARNING,
                        confidence=0.0,
                        details=f"Detection error: {str(e)}",
                        matched_patterns=[],
                        suggestions=["Review content manually due to detection error"]
                    )
        
        return results
    
    def get_overall_safety_assessment(self, results: Dict[DetectionType, DetectionResult]) -> Tuple[SafetyLevel, float, List[str]]:
        """Get overall safety assessment from all detection results"""
        blocked_count = sum(1 for result in results.values() if result.safety_level == SafetyLevel.BLOCKED)
        warning_count = sum(1 for result in results.values() if result.safety_level == SafetyLevel.WARNING)
        
        max_confidence = max((result.confidence for result in results.values()), default=0.0)
        
        issues = []
        for result in results.values():
            if result.safety_level != SafetyLevel.SAFE:
                issues.append(f"{result.detection_type.value}: {result.details}")
        
        if blocked_count > 0:
            return SafetyLevel.BLOCKED, max_confidence, issues
        elif warning_count > 0:
            return SafetyLevel.WARNING, max_confidence, issues
        else:
            return SafetyLevel.SAFE, 0.0, []
    
    def should_include_in_training(self, text: str, strict_mode: bool = False) -> Tuple[bool, str]:
        """Determine if content should be included in training data"""
        results = self.analyze_content(text)
        safety_level, confidence, issues = self.get_overall_safety_assessment(results)
        
        if safety_level == SafetyLevel.BLOCKED:
            return False, f"Content blocked: {'; '.join(issues[:3])}"
        
        if safety_level == SafetyLevel.WARNING and strict_mode:
            return False, f"Content flagged in strict mode: {'; '.join(issues[:3])}"
        
        if safety_level == SafetyLevel.WARNING:
            return True, f"Content included with warnings: {'; '.join(issues[:3])}"
        
        return True, "Content approved for training"

def main():
    """Test the safety detection system"""
    detector = ComprehensiveSafetyDetector()
    
    test_cases = [
        "How to implement secure authentication in Python",
        "SELECT * FROM users WHERE id = " + str(1),
        "password = 'hardcoded123'",
        "My SSN is 123-45-6789",
        "This code is GPL licensed",
        "eval(user_input)",
        "How to make a bomb",  # Should be blocked
        "Historical analysis of WWII bombing strategies",  # Should be educational
        "Adult content with explicit descriptions",  # Should be allowed (NSFW OK)
        "var nigger_count = 0; // offensive variable name",  # Should be blocked
        "function master_slave_connection() { }",  # Should be allowed (technical term)
    ]
    
    for i, test_text in enumerate(test_cases, 1):
        print(f"\n=== Test Case {i} ===")
        print(f"Text: {test_text}")
        
        should_include, reason = detector.should_include_in_training(test_text)
        print(f"Include in training: {should_include}")
        print(f"Reason: {reason}")
        
        # Detailed results
        results = detector.analyze_content(test_text)
        for detection_type, result in results.items():
            if result.safety_level != SafetyLevel.SAFE:
                print(f"  {detection_type.value}: {result.safety_level.value} (confidence: {result.confidence:.2f})")

if __name__ == "__main__":
    main()
