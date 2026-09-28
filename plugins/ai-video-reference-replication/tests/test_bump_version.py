import json
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]


class BumpVersionTests(unittest.TestCase):
    def run_bump(self, root, *args):
        result = subprocess.run([sys.executable, str(root / "scripts/bump_version.py"), *args],
                                capture_output=True, text=True, check=True)
        return json.loads(result.stdout)

    def test_changed_content_bumps_once_and_rerun_keeps_version(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory) / ROOT.name
            shutil.copytree(ROOT, root, ignore=shutil.ignore_patterns("__pycache__", "*.pyc"))
            first = self.run_bump(root)
            second = self.run_bump(root)
            self.assertFalse(second["contentChanged"])
            self.assertEqual(first["automationVersion"], second["automationVersion"])
            (root / "README.md").write_text((root / "README.md").read_text() + "\nChange fixture.\n")
            self.assertTrue(self.run_bump(root, "--check")["contentChanged"])
            changed = self.run_bump(root)
            again = self.run_bump(root)
            self.assertTrue(changed["contentChanged"])
            self.assertFalse(again["contentChanged"])
            major, minor = (int(x) for x in second["automationVersion"].split("."))
            self.assertEqual(changed["automationVersion"], f"{major}.{minor + 1}")
            manifest = json.loads((root / ".claude-plugin/plugin.json").read_text())
            self.assertEqual(manifest["version"], changed["automationVersion"] + ".0")
            skill = (root / "skills/ai-video-reference-replication/SKILL.md").read_text()
            self.assertIn(f"- 현재 자동화 버전: `{changed['automationVersion']}`", skill)


if __name__ == "__main__":
    unittest.main()
