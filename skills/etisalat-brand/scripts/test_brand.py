"""Tests for brand.py: python3 -m unittest discover -s skills/etisalat-brand/scripts"""
import importlib.util
import io
import tempfile
import unittest
from contextlib import redirect_stdout
from pathlib import Path

HERE = Path(__file__).resolve().parent
spec = importlib.util.spec_from_file_location("brand", HERE / "brand.py")
brand = importlib.util.module_from_spec(spec)
spec.loader.exec_module(brand)


def run_audit(path):
    buf = io.StringIO()
    with redirect_stdout(buf):
        flagged = brand.audit(path)
    return flagged, buf.getvalue()


def has(module):
    return importlib.util.find_spec(module) is not None


class Contrast(unittest.TestCase):
    def test_known_pairs(self):
        self.assertAlmostEqual(brand.contrast("#E00800", "#FFFFFF"), 5.0, places=1)
        self.assertAlmostEqual(brand.contrast("#140F21", "#FFFFFF"), 18.75, places=1)
        self.assertAlmostEqual(brand.contrast("#E00800", "#140F21"), 3.75, places=1)

    def test_text_colours_pass_aa_on_white(self):
        for group, name in [("core", "red"), ("core", "ink"), ("neutrals", "grey_700"),
                            ("neutrals", "red_dark"), ("status", "good"), ("status", "watch"), ("status", "bad")]:
            with self.subTest(name=name):
                self.assertGreaterEqual(brand.contrast(brand.TOKENS[group][name]["hex"], "#FFFFFF"), 4.5)

    def test_css_tokens_match_json(self):
        css = (HERE.parent / "assets" / "tokens.css").read_text(encoding="utf-8").upper()
        for h in brand.palette():
            self.assertIn(h, css)


class Audit(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.dir = Path(self.tmp.name)

    def tearDown(self):
        self.tmp.cleanup()

    def test_html_on_and_off_brand(self):
        ok = self.dir / "ok.html"
        ok.write_text('<style>h1{color:#E00800;font-family:"Inter",Arial,sans-serif}</style>', encoding="utf-8")
        self.assertFalse(run_audit(ok)[0])
        bad = self.dir / "bad.html"
        bad.write_text('<style>h1{color:#0066ff;font-family:"Comic Sans MS"}</style>', encoding="utf-8")
        flagged, out = run_audit(bad)
        self.assertTrue(flagged)
        self.assertIn("#0066FF", out)
        self.assertIn("Comic Sans MS", out)

    @unittest.skipUnless(has("pptx"), "python-pptx not installed")
    def test_pptx_ignores_theme_noise(self):
        from pptx import Presentation
        from pptx.dml.color import RGBColor
        p = Presentation()
        s = p.slides.add_slide(p.slide_layouts[5])
        s.shapes.title.text = "Results"
        run = s.shapes.title.text_frame.paragraphs[0].runs[0]
        run.font.color.rgb = RGBColor.from_string("1F77B4")
        run.font.name = "Arial"
        f = self.dir / "t.pptx"
        p.save(f)
        flagged, out = run_audit(f)
        self.assertTrue(flagged)
        self.assertIn("#1F77B4", out)
        self.assertNotIn("Mongolian Baiti", out)  # per-script theme fonts are summarised, not listed

    @unittest.skipUnless(has("openpyxl"), "openpyxl not installed")
    def test_xlsx_ignores_legacy_palette(self):
        import openpyxl
        from openpyxl.styles import Font, PatternFill
        wb = openpyxl.Workbook()
        c = wb.active["A1"]
        c.value = "Store"
        c.font = Font(name="Arial", bold=True, color="FFFFFF")
        c.fill = PatternFill("solid", fgColor="140F21")
        f = self.dir / "t.xlsx"
        wb.save(f)
        _, out = run_audit(f)
        self.assertNotIn("#FFFF00", out)  # from Excel's built-in 56-colour palette
        self.assertIn("core.ink", out)

    @unittest.skipUnless(has("docx"), "python-docx not installed")
    def test_docx_ignores_unused_styles(self):
        import docx
        from docx.shared import RGBColor
        d = docx.Document()
        r = d.add_paragraph().add_run("Hello")
        r.font.color.rgb = RGBColor(0xE0, 0x08, 0x00)
        r.font.name = "Arial"
        f = self.dir / "t.docx"
        d.save(f)
        flagged, out = run_audit(f)
        self.assertFalse(flagged, out)


if __name__ == "__main__":
    unittest.main()
