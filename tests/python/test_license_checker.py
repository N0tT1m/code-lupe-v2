#!/usr/bin/env python3
"""
Unit tests for LicenseChecker
"""

import unittest
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from license_checker import LicenseChecker, LicenseType, LicenseMatch


class TestLicenseChecker(unittest.TestCase):
    """Test cases for LicenseChecker"""

    def setUp(self):
        """Set up test fixtures"""
        self.checker = LicenseChecker()

    def test_no_license(self):
        """Test file without license"""
        code = """
def calculate_sum(a, b):
    return a + b
"""
        is_safe, license_match = self.checker.scan_file(code, 'test.py')
        self.assertTrue(is_safe)  # No license defaults to safe
        self.assertIsNone(license_match)

    def test_mit_license(self):
        """Test MIT license detection"""
        code = """
# Copyright (c) 2024 Example Corp
#
# Permission is hereby granted, free of charge, to any person obtaining a copy
# of this software and associated documentation files (the "Software"), to deal
# in the Software without restriction, including without limitation the rights
# to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
# copies of the Software.

def main():
    pass
"""
        is_safe, license_match = self.checker.scan_file(code, 'test.py')
        self.assertTrue(is_safe)
        self.assertIsNotNone(license_match)
        self.assertEqual(license_match.license_name, 'MIT')
        self.assertEqual(license_match.license_type, LicenseType.PERMISSIVE)
        self.assertTrue(license_match.is_training_safe)

    def test_apache_license(self):
        """Test Apache 2.0 license detection"""
        code = """
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# SPDX-License-Identifier: Apache-2.0

def process():
    return True
"""
        is_safe, license_match = self.checker.scan_file(code, 'test.py')
        self.assertTrue(is_safe)
        self.assertIsNotNone(license_match)
        self.assertEqual(license_match.license_name, 'Apache-2.0')
        self.assertTrue(license_match.is_training_safe)
        # SPDX identifier should give high confidence
        self.assertEqual(license_match.confidence, 1.0)

    def test_gpl_license(self):
        """Test GPL license detection (should be blocked)"""
        code = """
# Copyright (C) 2024 Example Corp
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, version 3.

def algorithm():
    pass
"""
        is_safe, license_match = self.checker.scan_file(code, 'test.py')
        self.assertFalse(is_safe)
        self.assertIsNotNone(license_match)
        self.assertEqual(license_match.license_name, 'GPL-3.0')
        self.assertEqual(license_match.license_type, LicenseType.COPYLEFT_STRONG)
        self.assertFalse(license_match.is_training_safe)

    def test_proprietary_license(self):
        """Test proprietary license detection (should be blocked)"""
        code = """
# Copyright (c) 2024 MegaCorp Inc.
# All Rights Reserved
# Proprietary and Confidential
# Internal Use Only

def secret_algorithm():
    return 42
"""
        is_safe, license_match = self.checker.scan_file(code, 'test.py')
        self.assertFalse(is_safe)
        self.assertIsNotNone(license_match)
        self.assertEqual(license_match.license_name, 'Proprietary')
        self.assertEqual(license_match.license_type, LicenseType.PROPRIETARY)
        self.assertFalse(license_match.is_training_safe)

    def test_bsd_license(self):
        """Test BSD license detection"""
        code = """
# SPDX-License-Identifier: BSD-3-Clause
# Copyright (c) 2024 Developer

def utility():
    pass
"""
        is_safe, license_match = self.checker.scan_file(code, 'test.py')
        self.assertTrue(is_safe)
        self.assertIsNotNone(license_match)
        self.assertEqual(license_match.license_name, 'BSD-3-Clause')
        self.assertTrue(license_match.is_training_safe)

    def test_lgpl_license(self):
        """Test LGPL license detection (weak copyleft, allowed)"""
        code = """
# This library is free software; you can redistribute it and/or
# modify it under the terms of the GNU Lesser General Public License
# version 3 as published by the Free Software Foundation.

def library_function():
    pass
"""
        is_safe, license_match = self.checker.scan_file(code, 'test.py')
        self.assertTrue(is_safe)  # LGPL is training-safe
        self.assertIsNotNone(license_match)
        self.assertEqual(license_match.license_name, 'LGPL-3.0')
        self.assertEqual(license_match.license_type, LicenseType.COPYLEFT_WEAK)

    def test_mpl_license(self):
        """Test Mozilla Public License detection"""
        code = """
# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at http://mozilla.org/MPL/2.0/.

def component():
    pass
"""
        is_safe, license_match = self.checker.scan_file(code, 'test.py')
        self.assertTrue(is_safe)
        self.assertIsNotNone(license_match)
        self.assertEqual(license_match.license_name, 'MPL-2.0')
        self.assertTrue(license_match.is_training_safe)

    def test_unlicense(self):
        """Test Unlicense (public domain) detection"""
        code = """
# This is free and unencumbered software released into the public domain.
# Anyone is free to copy, modify, publish, use, compile, sell, or
# distribute this software, either in source code form or as a compiled
# binary, for any purpose, commercial or non-commercial, and by any means.

def public_code():
    pass
"""
        is_safe, license_match = self.checker.scan_file(code, 'test.py')
        self.assertTrue(is_safe)
        self.assertIsNotNone(license_match)
        self.assertEqual(license_match.license_name, 'Unlicense')
        self.assertTrue(license_match.is_training_safe)

    def test_agpl_license(self):
        """Test AGPL license detection (should be blocked)"""
        code = """
# SPDX-License-Identifier: AGPL-3.0
# This program is licensed under the GNU Affero General Public License

def server_code():
    pass
"""
        is_safe, license_match = self.checker.scan_file(code, 'test.py')
        self.assertFalse(is_safe)
        self.assertIsNotNone(license_match)
        self.assertEqual(license_match.license_name, 'AGPL-3.0')
        self.assertFalse(license_match.is_training_safe)

    def test_license_in_footer(self):
        """Test license detection in file footer"""
        code = """
def main():
    print("Hello")
    return 0

# ========================
# Copyright (c) 2024
# MIT License
# ========================
"""
        is_safe, license_match = self.checker.scan_file(code, 'test.py')
        self.assertTrue(is_safe)
        self.assertIsNotNone(license_match)
        self.assertEqual(license_match.license_name, 'MIT')
        self.assertEqual(license_match.location, 'footer')

    def test_spdx_identifier_confidence(self):
        """Test that SPDX identifiers have highest confidence"""
        code = """
# SPDX-License-Identifier: MIT

def test():
    pass
"""
        is_safe, license_match = self.checker.scan_file(code, 'test.py')
        self.assertTrue(is_safe)
        self.assertEqual(license_match.confidence, 1.0)

    def test_scan_repository_metadata(self):
        """Test repository-level license checking"""
        # Test safe license
        repo_metadata = {'license': {'key': 'mit'}}
        is_safe, license_name = self.checker.scan_repository(repo_metadata)
        self.assertTrue(is_safe)
        self.assertEqual(license_name, 'mit')

        # Test GPL license
        repo_metadata = {'license': {'key': 'gpl-3.0'}}
        is_safe, license_name = self.checker.scan_repository(repo_metadata)
        self.assertFalse(is_safe)
        self.assertEqual(license_name, 'gpl-3.0')

        # Test unknown license
        repo_metadata = {'license': {'key': 'custom'}}
        is_safe, license_name = self.checker.scan_repository(repo_metadata)
        self.assertTrue(is_safe)  # Defaults to safe for unknown

    def test_get_license_report(self):
        """Test license report generation"""
        matches = [
            LicenseMatch('MIT', LicenseType.PERMISSIVE, 1.0, 'MIT License', 'header', 1, True),
            LicenseMatch('Apache-2.0', LicenseType.PERMISSIVE, 0.9, 'Apache', 'header', 1, True),
            LicenseMatch('GPL-3.0', LicenseType.COPYLEFT_STRONG, 0.8, 'GPL', 'header', 1, False),
        ]

        report = self.checker.get_license_report(matches)

        self.assertEqual(report['total_files'], 3)
        self.assertEqual(report['training_safe'], 2)
        self.assertEqual(report['training_unsafe'], 1)
        self.assertIn('MIT', report['by_license'])
        self.assertEqual(report['by_license']['MIT'], 1)

    def test_copyright_notice_boosts_confidence(self):
        """Test that copyright notice near license text boosts confidence"""
        code_with_copyright = """
# Copyright (c) 2024 Developer
# MIT License

def test():
    pass
"""
        code_without_copyright = """
# MIT License

def test():
    pass
"""

        _, match_with = self.checker.scan_file(code_with_copyright, 'test.py')
        _, match_without = self.checker.scan_file(code_without_copyright, 'test.py')

        # Both should detect MIT, but copyright should boost confidence
        self.assertIsNotNone(match_with)
        self.assertIsNotNone(match_without)
        self.assertGreaterEqual(match_with.confidence, match_without.confidence)


class TestLicenseMatch(unittest.TestCase):
    """Test LicenseMatch dataclass"""

    def test_create_license_match(self):
        """Test creating a LicenseMatch"""
        match = LicenseMatch(
            license_name='MIT',
            license_type=LicenseType.PERMISSIVE,
            confidence=0.95,
            matched_text='MIT License',
            location='header',
            line_number=5,
            is_training_safe=True
        )

        self.assertEqual(match.license_name, 'MIT')
        self.assertEqual(match.license_type, LicenseType.PERMISSIVE)
        self.assertEqual(match.confidence, 0.95)
        self.assertTrue(match.is_training_safe)


class TestLicenseType(unittest.TestCase):
    """Test LicenseType enum"""

    def test_license_types(self):
        """Test license type enum values"""
        self.assertEqual(LicenseType.PERMISSIVE.value, 'permissive')
        self.assertEqual(LicenseType.COPYLEFT_WEAK.value, 'copyleft_weak')
        self.assertEqual(LicenseType.COPYLEFT_STRONG.value, 'copyleft_strong')
        self.assertEqual(LicenseType.PROPRIETARY.value, 'proprietary')
        self.assertEqual(LicenseType.UNKNOWN.value, 'unknown')


if __name__ == '__main__':
    unittest.main()
