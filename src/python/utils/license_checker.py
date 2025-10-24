#!/usr/bin/env python3
"""
License Checker - Detects and validates software licenses
Identifies copyleft, proprietary, and permissive licenses
Helps ensure training data compliance
"""

import re
import logging
from typing import Dict, List, Optional, Tuple
from dataclasses import dataclass
from enum import Enum

logger = logging.getLogger(__name__)


class LicenseType(Enum):
    """License categories"""
    PERMISSIVE = "permissive"  # MIT, Apache, BSD - safe for training
    COPYLEFT_WEAK = "copyleft_weak"  # LGPL, MPL - use with caution
    COPYLEFT_STRONG = "copyleft_strong"  # GPL - may restrict model usage
    PROPRIETARY = "proprietary"  # Proprietary/closed source - avoid
    UNKNOWN = "unknown"  # No license detected


@dataclass
class LicenseMatch:
    """Represents a license found in code"""
    license_name: str
    license_type: LicenseType
    confidence: float  # 0.0 to 1.0
    matched_text: str
    location: str  # 'header', 'footer', 'inline'
    line_number: int
    is_training_safe: bool


class LicenseChecker:
    """Checks code for license information and compliance"""

    def __init__(self):
        # License patterns with SPDX identifiers
        self.license_patterns = {
            # Permissive licenses (safe for training)
            'MIT': {
                'patterns': [
                    r'MIT License',
                    r'SPDX-License-Identifier:\s*MIT',
                    r'Permission is hereby granted, free of charge',
                ],
                'type': LicenseType.PERMISSIVE,
                'training_safe': True,
                'description': 'MIT License (permissive, training-safe)'
            },
            'Apache-2.0': {
                'patterns': [
                    r'Apache License.*Version 2\.0',
                    r'SPDX-License-Identifier:\s*Apache-2\.0',
                    r'Licensed under the Apache License',
                ],
                'type': LicenseType.PERMISSIVE,
                'training_safe': True,
                'description': 'Apache License 2.0 (permissive, training-safe)'
            },
            'BSD-2-Clause': {
                'patterns': [
                    r'BSD 2-Clause',
                    r'SPDX-License-Identifier:\s*BSD-2-Clause',
                    r'Redistribution and use in source and binary forms.*with or without modification',
                ],
                'type': LicenseType.PERMISSIVE,
                'training_safe': True,
                'description': 'BSD 2-Clause (permissive, training-safe)'
            },
            'BSD-3-Clause': {
                'patterns': [
                    r'BSD 3-Clause',
                    r'SPDX-License-Identifier:\s*BSD-3-Clause',
                ],
                'type': LicenseType.PERMISSIVE,
                'training_safe': True,
                'description': 'BSD 3-Clause (permissive, training-safe)'
            },
            'ISC': {
                'patterns': [
                    r'ISC License',
                    r'SPDX-License-Identifier:\s*ISC',
                ],
                'type': LicenseType.PERMISSIVE,
                'training_safe': True,
                'description': 'ISC License (permissive, training-safe)'
            },
            'Unlicense': {
                'patterns': [
                    r'This is free and unencumbered software released into the public domain',
                    r'SPDX-License-Identifier:\s*Unlicense',
                ],
                'type': LicenseType.PERMISSIVE,
                'training_safe': True,
                'description': 'Unlicense (public domain, training-safe)'
            },
            '0BSD': {
                'patterns': [
                    r'SPDX-License-Identifier:\s*0BSD',
                    r'BSD Zero Clause License',
                ],
                'type': LicenseType.PERMISSIVE,
                'training_safe': True,
                'description': 'BSD Zero Clause (permissive, training-safe)'
            },

            # Weak copyleft (caution advised)
            'LGPL-2.1': {
                'patterns': [
                    r'GNU Lesser General Public License.*version 2\.1',
                    r'SPDX-License-Identifier:\s*LGPL-2\.1',
                ],
                'type': LicenseType.COPYLEFT_WEAK,
                'training_safe': True,  # Generally OK for training, but review
                'description': 'LGPL 2.1 (weak copyleft, review recommended)'
            },
            'LGPL-3.0': {
                'patterns': [
                    r'GNU Lesser General Public License.*version 3',
                    r'SPDX-License-Identifier:\s*LGPL-3\.0',
                ],
                'type': LicenseType.COPYLEFT_WEAK,
                'training_safe': True,
                'description': 'LGPL 3.0 (weak copyleft, review recommended)'
            },
            'MPL-2.0': {
                'patterns': [
                    r'Mozilla Public License.*Version 2\.0',
                    r'SPDX-License-Identifier:\s*MPL-2\.0',
                ],
                'type': LicenseType.COPYLEFT_WEAK,
                'training_safe': True,
                'description': 'Mozilla Public License 2.0 (weak copyleft)'
            },

            # Strong copyleft (review carefully)
            'GPL-2.0': {
                'patterns': [
                    r'GNU General Public License.*version 2',
                    r'SPDX-License-Identifier:\s*GPL-2\.0',
                    r'This program is free software.*redistribute it.*GNU General Public License',
                ],
                'type': LicenseType.COPYLEFT_STRONG,
                'training_safe': False,  # Caution: may impose restrictions
                'description': 'GPL 2.0 (strong copyleft, USE WITH CAUTION)'
            },
            'GPL-3.0': {
                'patterns': [
                    r'GNU General Public License.*version 3',
                    r'SPDX-License-Identifier:\s*GPL-3\.0',
                ],
                'type': LicenseType.COPYLEFT_STRONG,
                'training_safe': False,
                'description': 'GPL 3.0 (strong copyleft, USE WITH CAUTION)'
            },
            'AGPL-3.0': {
                'patterns': [
                    r'GNU Affero General Public License.*version 3',
                    r'SPDX-License-Identifier:\s*AGPL-3\.0',
                ],
                'type': LicenseType.COPYLEFT_STRONG,
                'training_safe': False,
                'description': 'AGPL 3.0 (strong copyleft, USE WITH CAUTION)'
            },

            # Proprietary indicators
            'Proprietary': {
                'patterns': [
                    r'All [Rr]ights [Rr]eserved',
                    r'Proprietary and [Cc]onfidential',
                    r'[Cc]onfidential.*not.*distribut',
                    r'Internal [Uu]se [Oo]nly',
                    r'[Pp]rivate.*[Cc]opyright',
                ],
                'type': LicenseType.PROPRIETARY,
                'training_safe': False,
                'description': 'Proprietary license (AVOID FOR TRAINING)'
            },
        }

        # Copyright patterns (help identify license location)
        self.copyright_patterns = [
            r'Copyright\s+\(c\)\s+\d{4}',
            r'Copyright\s+©\s+\d{4}',
            r'©\s+\d{4}',
            r'Copr\.\s+\d{4}',
        ]

    def scan_file(self, content: str, file_path: str) -> Tuple[bool, Optional[LicenseMatch]]:
        """
        Scan a file for license information

        Returns:
            (is_training_safe, license_match)
        """
        lines = content.split('\n')

        # Check header (first 50 lines) - most common location
        header = '\n'.join(lines[:50])
        license_match = self._scan_text(header, 'header')

        if not license_match:
            # Check footer (last 20 lines)
            footer = '\n'.join(lines[-20:])
            license_match = self._scan_text(footer, 'footer')

        if not license_match:
            # Check entire file (slower, but thorough)
            license_match = self._scan_text(content, 'inline')

        # Default to safe if no license found (may indicate public code)
        is_training_safe = True
        if license_match:
            is_training_safe = license_match.is_training_safe

            if not is_training_safe:
                logger.warning(
                    f"License concern in {file_path}: {license_match.license_name} "
                    f"({license_match.license_type.value})"
                )

        return is_training_safe, license_match

    def _scan_text(self, text: str, location: str) -> Optional[LicenseMatch]:
        """Scan text for license patterns"""
        best_match = None
        best_confidence = 0.0

        for license_name, info in self.license_patterns.items():
            for pattern in info['patterns']:
                match = re.search(pattern, text, re.IGNORECASE | re.MULTILINE | re.DOTALL)
                if match:
                    # Calculate confidence based on match quality
                    confidence = 1.0 if 'SPDX-License-Identifier' in match.group(0) else 0.8

                    # Boost confidence if copyright notice nearby
                    context = text[max(0, match.start() - 200):match.end() + 200]
                    if any(re.search(p, context, re.IGNORECASE) for p in self.copyright_patterns):
                        confidence = min(1.0, confidence + 0.1)

                    if confidence > best_confidence:
                        line_num = text[:match.start()].count('\n') + 1
                        best_match = LicenseMatch(
                            license_name=license_name,
                            license_type=info['type'],
                            confidence=confidence,
                            matched_text=match.group(0)[:100],  # First 100 chars
                            location=location,
                            line_number=line_num,
                            is_training_safe=info['training_safe']
                        )
                        best_confidence = confidence

        return best_match

    def scan_repository(self, repo_metadata: Dict) -> Tuple[bool, Optional[str]]:
        """
        Check repository-level license from metadata

        Args:
            repo_metadata: Dict with 'license' field from GitHub API

        Returns:
            (is_training_safe, license_name)
        """
        license_key = repo_metadata.get('license', {}).get('key', 'unknown')

        # Map GitHub license keys to our system
        safe_licenses = [
            'mit', 'apache-2.0', 'bsd-2-clause', 'bsd-3-clause',
            'isc', 'unlicense', '0bsd', 'cc0-1.0'
        ]

        caution_licenses = ['lgpl-2.1', 'lgpl-3.0', 'mpl-2.0']

        unsafe_licenses = [
            'gpl-2.0', 'gpl-3.0', 'agpl-3.0',
            'proprietary', 'other', 'unlicensed'
        ]

        if license_key in safe_licenses:
            return True, license_key
        elif license_key in caution_licenses:
            return True, license_key  # Allow but log
        elif license_key in unsafe_licenses:
            return False, license_key
        else:
            # Unknown license - default to safe but log
            logger.info(f"Unknown license key: {license_key}, defaulting to safe")
            return True, license_key

    def get_license_report(self, matches: List[LicenseMatch]) -> Dict:
        """Generate a license report"""
        report = {
            'total_files': len(matches),
            'training_safe': len([m for m in matches if m.is_training_safe]),
            'training_unsafe': len([m for m in matches if not m.is_training_safe]),
            'license_types': {},
            'by_license': {},
        }

        for match in matches:
            # Count by type
            type_key = match.license_type.value
            if type_key not in report['license_types']:
                report['license_types'][type_key] = 0
            report['license_types'][type_key] += 1

            # Count by specific license
            if match.license_name not in report['by_license']:
                report['by_license'][match.license_name] = 0
            report['by_license'][match.license_name] += 1

        return report


def test_checker():
    """Test the license checker"""
    checker = LicenseChecker()

    test_cases = [
        {
            'name': 'MIT License',
            'code': '''
# Copyright (c) 2024 Example Corp
#
# Permission is hereby granted, free of charge, to any person obtaining a copy
# of this software and associated documentation files (the "Software"), to deal
# in the Software without restriction, including without limitation the rights
# to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
# copies of the Software.

def hello():
    return "world"
''',
            'expected_safe': True,
            'expected_license': 'MIT'
        },
        {
            'name': 'GPL License',
            'code': '''
# Copyright (C) 2024 Example Corp
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, version 3.

def process():
    pass
''',
            'expected_safe': False,
            'expected_license': 'GPL-3.0'
        },
        {
            'name': 'Apache License',
            'code': '''
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# SPDX-License-Identifier: Apache-2.0

def main():
    print("Hello")
''',
            'expected_safe': True,
            'expected_license': 'Apache-2.0'
        },
        {
            'name': 'Proprietary',
            'code': '''
# Copyright (c) 2024 MegaCorp
# All Rights Reserved
# Proprietary and Confidential
# Internal Use Only

def secret_algorithm():
    return 42
''',
            'expected_safe': False,
            'expected_license': 'Proprietary'
        },
        {
            'name': 'No License',
            'code': '''
def hello():
    print("Hello, world!")
''',
            'expected_safe': True,
            'expected_license': None
        },
    ]

    for test in test_cases:
        is_safe, license_match = checker.scan_file(test['code'], 'test.py')
        license_name = license_match.license_name if license_match else None

        print(f"\nTest: {test['name']}")
        print(f"Expected safe: {test['expected_safe']}, Got: {is_safe}")
        print(f"Expected license: {test['expected_license']}, Got: {license_name}")

        if license_match:
            print(f"  License: {license_match.license_name}")
            print(f"  Type: {license_match.license_type.value}")
            print(f"  Confidence: {license_match.confidence:.2f}")
            print(f"  Location: {license_match.location}")

        assert is_safe == test['expected_safe'], f"Safety mismatch in test: {test['name']}"

    print("\n✅ All tests passed!")


if __name__ == "__main__":
    test_checker()
