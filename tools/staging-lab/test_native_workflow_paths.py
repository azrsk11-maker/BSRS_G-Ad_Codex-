"""Keep native CI attached to the actual local Docker build inputs; no network."""
from pathlib import Path, PurePosixPath
import re
import shlex
import tempfile
import unittest


ROOT = Path(__file__).resolve().parents[2]


def workflow_paths(text):
    # Deliberately accept the workflow's existing literal YAML list only.
    # New YAML syntax must extend this check rather than silently omit inputs.
    match = re.search(r"(?m)^on:\n  pull_request:\n((?:    .*(?:\n|$))+)", text)
    if not match:
        raise ValueError("Expected pull_request trigger")
    lines = match.group(1).splitlines()
    if lines.count("    paths:") != 1:
        raise ValueError("Expected one pull_request paths list")
    patterns = []
    for line in lines[lines.index("    paths:") + 1:]:
        if not line.startswith("      "):
            break
        item = re.fullmatch(r"      - '([^']+)'", line)
        if not item:
            raise ValueError("Unsupported path-filter syntax")
        patterns.append(item.group(1))
    if not patterns or not any(not pattern.startswith("!") for pattern in patterns):
        raise ValueError("Expected positive path filters")
    return patterns


def triggered(path, patterns):
    selected = False
    for pattern in patterns:
        negative = pattern.startswith("!")
        glob = pattern[1:] if negative else pattern
        if not glob or any(char in glob for char in "?+[]!\\"):
            raise ValueError("Unsupported path glob")
        regex = ""
        while glob:
            if glob.startswith("**/"):
                regex += "(?:.*/)?"
                glob = glob[3:]
            elif glob.startswith("**"):
                regex += ".*"
                glob = glob[2:]
            elif glob.startswith("*"):
                regex += "[^/]*"
                glob = glob[1:]
            else:
                regex += re.escape(glob[0])
                glob = glob[1:]
        if re.fullmatch(regex, path):
            selected = not negative
    return selected


def copied_files(root, dockerfile):
    files = set()
    for line in re.sub(r"\\\r?\n", " ", dockerfile).splitlines():
        if not re.match(r"(?i)^\s*COPY\s", line):
            continue
        payload = line.strip().split(None, 1)[1]
        if payload.startswith("["):
            raise ValueError("Unsupported COPY syntax")
        tokens = shlex.split(payload)
        if len(tokens) < 2 or any(token.startswith("--") or "$" in token for token in tokens):
            raise ValueError("Unsupported COPY syntax")
        for source in tokens[:-1]:
            if PurePosixPath(source).is_absolute() or ".." in PurePosixPath(source).parts:
                raise ValueError("COPY source must stay in the repository")
            matches = list(root.glob(source))
            if not matches:
                raise ValueError("COPY source does not exist")
            for match in matches:
                if match.is_symlink():
                    raise ValueError("Unsupported symlink COPY source")
                members = [match] if match.is_file() else match.rglob("*")
                for member in members:
                    if member.is_symlink():
                        raise ValueError("Unsupported symlink COPY source")
                    if member.is_file():
                        files.add(member.relative_to(root).as_posix())
    if not files:
        raise ValueError("Expected repository-local COPY inputs")
    return files


def uncovered_inputs(root, dockerfile, workflow):
    patterns = workflow_paths(workflow)
    return sorted(path for path in copied_files(root, dockerfile) if not triggered(path, patterns))


class NativeWorkflowPathTests(unittest.TestCase):
    def test_every_actual_local_copy_input_triggers_native_ci(self):
        missing = uncovered_inputs(ROOT,
            (ROOT / "tools/staging-lab/Dockerfile").read_text(encoding="utf-8"),
            (ROOT / ".github/workflows/isolated-wordpress-lab.yml").read_text(encoding="utf-8"))
        self.assertEqual(missing, [], "Native CI omits Docker inputs: " + ", ".join(missing))

    def test_star_is_segment_bounded_and_globstar_includes_nested_files(self):
        self.assertTrue(triggered("tools/lab/file.php", ["tools/lab/*.php"]))
        self.assertFalse(triggered("tools/lab/nested/file.php", ["tools/lab/*.php"]))
        self.assertTrue(triggered("tools/lab/nested/file.php", ["tools/lab/**"]))
        self.assertTrue(triggered("tools/file.php", ["tools/**/*.php"]))
        self.assertFalse(triggered("other/file.php", ["tools/**"]))

    def test_negative_filters_obey_order(self):
        patterns = ["tools/**", "!tools/lab/**"]
        self.assertFalse(triggered("tools/lab/file.php", patterns))
        self.assertTrue(triggered("tools/lab/file.php", patterns + ["tools/lab/*.php"]))

    def test_copy_sources_are_derived_and_missing_runtime_input_is_detected(self):
        with tempfile.TemporaryDirectory(prefix="bsre-native-paths-") as directory:
            root = Path(directory)
            (root / "tools/lab/nested").mkdir(parents=True)
            (root / "tools/lab/nested/runtime.php").write_bytes(b"synthetic\n")
            (root / "tools/adapter.php").write_bytes(b"synthetic\n")
            docker = "COPY tools/lab " + "\\\n" + " tools/*.php /opt/lab/\n"
            workflow = "on:\n  pull_request:\n    paths:\n      - 'tools/lab/**'\npermissions:\n"
            self.assertEqual(uncovered_inputs(root, docker, workflow), ["tools/adapter.php"])
            self.assertEqual(uncovered_inputs(root, docker,
                workflow.replace("'tools/lab/**'", "'tools/**'")), [])

    def test_unrecognized_filters_and_copy_syntax_fail_instead_of_skipping(self):
        for workflow in ("on:\n  push:\n", "on:\n  pull_request:\n    paths-ignore:\n",
                         "on:\n  pull_request:\n    paths:\n      - tools/**\n"):
            with self.subTest(workflow=workflow), self.assertRaises(ValueError):
                workflow_paths(workflow)
        with self.assertRaises(ValueError):
            triggered("tools/file.php", ["tools/[abc].php"])
        for docker in ("COPY --from=other /app /opt/app", 'COPY ["tools", "/opt"]',
                       "COPY $INPUT /opt", "COPY ../outside /opt", "COPY absent /opt"):
            with self.subTest(docker=docker), self.assertRaises(ValueError):
                copied_files(ROOT, docker)


if __name__ == "__main__":
    unittest.main()
