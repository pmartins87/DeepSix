import tempfile
import unittest
from pathlib import Path

from tools.extract_openholdem_source_dump import (
    SourceDumpError,
    parse_dump_text,
    relative_openholdem_path,
    write_entries,
)


class OpenHoldemDumpExtractorTests(unittest.TestCase):
    def test_parse_and_extract_nested_paths(self):
        text = (
            "========== ARQUIVO: C:\\x\\OpenHoldem\\Foo.cpp ==========\n"
            "int foo = 1;\n\n"
            "========== ARQUIVO: C:\\x\\OpenHoldem\\sub\\Bar.h ==========\n"
            "#pragma once\n"
        )
        entries = parse_dump_text(text)
        self.assertEqual([str(e.relative_path) for e in entries], ["Foo.cpp", "sub/Bar.h"])
        self.assertTrue(entries[0].content.startswith("int foo = 1;"))

        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            write_entries(entries, root)
            self.assertEqual((root / "Foo.cpp").read_text(), entries[0].content)
            self.assertEqual((root / "sub" / "Bar.h").read_text(), entries[1].content)

    def test_duplicate_path_rejected(self):
        text = (
            "========== ARQUIVO: C:\\x\\OpenHoldem\\Foo.cpp ==========\nA\n"
            "========== ARQUIVO: C:\\x\\OpenHoldem\\Foo.cpp ==========\nB\n"
        )
        with self.assertRaises(SourceDumpError):
            parse_dump_text(text)

    def test_marker_without_openholdem_root_rejected(self):
        with self.assertRaises(SourceDumpError):
            relative_openholdem_path("C:\\x\\Elsewhere\\Foo.cpp")

    def test_no_markers_rejected(self):
        with self.assertRaises(SourceDumpError):
            parse_dump_text("plain text")


if __name__ == "__main__":
    unittest.main()
