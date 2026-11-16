#!/usr/bin/env python3
"""Regression tests: reject the two formerly shipped CRT sampling bugs."""
import os
import shutil
import tempfile
import unittest

import validate_mod as validator


class CRTValidationTest(unittest.TestCase):
    def test_invalid_fetches_are_rejected(self):
        original_mod = validator.MOD
        shader = os.path.join(original_mod, 'shaders', 'crt.frag')
        stage = os.path.join(original_mod, 'data', 'stages', 'trollge.hx')
        with open(shader, encoding='utf-8') as handle:
            source = handle.read()
        with tempfile.TemporaryDirectory() as tmp:
            os.makedirs(os.path.join(tmp, 'shaders'))
            os.makedirs(os.path.join(tmp, 'data', 'stages'))
            shutil.copyfile(stage, os.path.join(tmp, 'data', 'stages', 'trollge.hx'))
            try:
                validator.MOD = tmp
                for replacement, expected in ((None, None),
                                               ('flixel_texture2D', 'unsupported'),
                                               ('texture2D', 'must not fetch')):
                    with self.subTest(replacement=replacement):
                        code = source if replacement is None else source.replace(
                            'textureCam(bitmap, suv)', replacement + '(bitmap, suv)')
                        if replacement:
                            self.assertNotEqual(code, source)
                        with open(os.path.join(tmp, 'shaders', 'crt.frag'), 'w', encoding='utf-8') as handle:
                            handle.write(code)
                        validator.ERRORS.clear()
                        validator.check_crt()
                        if expected is None:
                            self.assertEqual(validator.ERRORS, [])
                        else:
                            self.assertTrue(any(expected in error for error in validator.ERRORS), validator.ERRORS)
            finally:
                validator.MOD = original_mod
                validator.ERRORS.clear()


if __name__ == '__main__':
    unittest.main()
