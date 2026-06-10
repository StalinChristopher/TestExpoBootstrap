#!/usr/bin/env python3
"""Regression tests for bootstrap_rn_workflow_ids.py patch helpers."""
from __future__ import annotations

import importlib.util
import sys
import unittest
from pathlib import Path

_SCRIPT = Path(__file__).resolve().parent / "bootstrap_rn_workflow_ids.py"
_spec = importlib.util.spec_from_file_location("bootstrap_rn_workflow_ids", _SCRIPT)
assert _spec and _spec.loader
bootstrap = importlib.util.module_from_spec(_spec)
sys.modules["bootstrap_rn_workflow_ids"] = bootstrap
_spec.loader.exec_module(bootstrap)


class TestAndroidGradleCiValues(unittest.TestCase):
    def test_expo_single_flavor_uses_assemble_release(self) -> None:
        dev, prod, glob_dev, glob_prod = bootstrap.android_gradle_ci_values(False, False)
        self.assertEqual(dev, "assembleRelease")
        self.assertEqual(prod, "assembleRelease")
        self.assertEqual(glob_dev, "app/build/outputs/apk/release/*.apk")
        self.assertEqual(glob_prod, glob_dev)

    def test_ct_bare_keeps_flavor_tasks(self) -> None:
        dev, prod, glob_dev, glob_prod = bootstrap.android_gradle_ci_values(True, True)
        self.assertEqual(dev, "assembleDevRelease")
        self.assertEqual(prod, "assembleProdRelease")
        self.assertEqual(glob_dev, "app/build/outputs/apk/dev/release/*.apk")
        self.assertEqual(glob_prod, "app/build/outputs/apk/prod/release/*.apk")


class TestPatchAndroidGradleSnippets(unittest.TestCase):
    def test_expo_scheme_does_not_double_gradle_task(self) -> None:
        yaml = """
      gradle_task: assembleDevRelease
      default: assembleProdRelease
"""
        out = bootstrap.patch_text_android_gradle_snippets(
            yaml,
            "assembleRelease",
            "assembleRelease",
            "app/build/outputs/apk/release/*.apk",
            "app/build/outputs/apk/release/*.apk",
        )
        self.assertIn("gradle_task: assembleRelease", out)
        self.assertIn("default: assembleRelease", out)
        self.assertNotIn("ExpoWorkflowTestExpo", out)

    def test_ct_bare_gradle_tasks_unchanged(self) -> None:
        yaml = "default: assembleProdRelease\nrun: ./gradlew assembleProdRelease\n"
        out = bootstrap.patch_text_android_gradle_snippets(
            yaml,
            "assembleDevRelease",
            "assembleProdRelease",
            bootstrap.OLD_APK_GLOB_DEV,
            bootstrap.OLD_APK_GLOB_PROD,
        )
        self.assertIn("default: assembleProdRelease", out)
        self.assertIn("./gradlew assembleProdRelease", out)


class TestPatchIosSchemeSnippets(unittest.TestCase):
    def test_orchestrator_scheme_without_doubling_workspace(self) -> None:
        yaml = """
      ios_scheme: Dev
      ios_workspace: ios/ExpoWorkflowTestDev.xcworkspace
"""
        out = bootstrap.patch_text_ios_scheme_snippets(yaml, "ExpoWorkflowTestDev", "ExpoWorkflowTestDev")
        self.assertIn("ios_scheme: ExpoWorkflowTestDev", out)
        self.assertIn("ios/ExpoWorkflowTestDev.xcworkspace", out)
        self.assertNotIn("ExpoWorkflowTestExpoWorkflowTestDev", out)

    def test_job_input_default_dev_scheme(self) -> None:
        yaml = """
      ios_scheme:
        required: false
        type: string
        default: Dev
"""
        out = bootstrap.patch_text_ios_scheme_snippets(yaml, "ExpoWorkflowTestDev", "ExpoWorkflowTestDev")
        self.assertIn("default: ExpoWorkflowTestDev", out)

    def test_ct_bare_dev_prod_unchanged(self) -> None:
        yaml = "ios_scheme: Dev\nios_scheme: Prod\n"
        out = bootstrap.patch_text_ios_scheme_snippets(yaml, "Dev", "Prod")
        self.assertEqual(yaml, out)


class TestSafeGlobalReplace(unittest.TestCase):
    def test_build_config_whole_token_only(self) -> None:
        text = "default: Debug-Dev\nIOS_BUILD_CONFIGURATION: Release-Prod\n"
        mapping = [
            (bootstrap.OLD_IOS_BUILD_CONFIG_DEV, "Debug"),
            (bootstrap.OLD_IOS_BUILD_CONFIG_DIST, "Release"),
        ]
        out = bootstrap.apply_replacements(text, mapping)
        self.assertIn("default: Debug", out)
        self.assertIn("IOS_BUILD_CONFIGURATION: Release", out)
        self.assertNotIn("Debug-Dev", out)

    def test_no_bare_dev_replace_in_gradle_task(self) -> None:
        """Simulates old bug: global Dev replace must not run on gradle tasks."""
        text = "default: assembleProdRelease\n"
        # Old buggy mapping would include (OLD_SCHEME_PROD, "ExpoWorkflowTestDev") then (OLD_SCHEME, "ExpoWorkflowTestDev")
        buggy = [
            (bootstrap.OLD_SCHEME_PROD, "ExpoWorkflowTestDev"),
            (bootstrap.OLD_SCHEME, "ExpoWorkflowTestDev"),
        ]
        corrupted = bootstrap.apply_replacements(text, buggy)
        self.assertIn("assembleExpoWorkflowTestExpoWorkflowTestDevRelease", corrupted)
        fixed = bootstrap.patch_text_android_gradle_snippets(
            text,
            "assembleRelease",
            "assembleRelease",
            "app/build/outputs/apk/release/*.apk",
            "app/build/outputs/apk/release/*.apk",
        )
        self.assertIn("default: assembleRelease", fixed)
        self.assertNotIn("ExpoWorkflowTestExpo", fixed)


class TestFastfileTargetedReplacements(unittest.TestCase):
    def test_full_string_workspace_replace(self) -> None:
        mapping = bootstrap.fastfile_targeted_replacements(
            "ExpoWorkflowTestDev",
            "ios/ExpoWorkflowTestDev.xcworkspace",
            "ExpoWorkflowTestDev",
            "ExpoWorkflowTestDev",
        )
        text = bootstrap.apply_replacements(
            'workspace: "ios/TemplatePipelineReactNative.xcworkspace"\n'
            'scheme: ENV.fetch("IOS_SCHEME", "Prod")\n'
            'output_name: "TemplatePipelineReactNative.ipa"\n'
            'path: "../ios/TemplatePipelineReactNative/GoogleService-Info.plist"\n',
            mapping,
        )
        self.assertIn("ios/ExpoWorkflowTestDev.xcworkspace", text)
        self.assertIn('ENV.fetch("IOS_SCHEME", "ExpoWorkflowTestDev")', text)
        self.assertIn('output_name: "ExpoWorkflowTestDev.ipa"', text)
        self.assertIn("../ios/ExpoWorkflowTestDev/GoogleService-Info.plist", text)
        self.assertNotIn("ExpoWorkflowTestExpoWorkflowTestDev", text)
        self.assertNotIn("TemplatePipelineReactNative.ipa", text)


if __name__ == "__main__":
    unittest.main()
