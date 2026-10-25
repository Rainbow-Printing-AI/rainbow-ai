"""Run: python3 tests/test_pricebook.py   (works on a temp copy; never touches the real data)"""
import os, shutil, subprocess, sys, tempfile, unittest, csv, json

KIT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

class T(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp = tempfile.mkdtemp(prefix="pbtest-")
        for name in ("pricebook.py", "pb_render.py"):
            shutil.copy(os.path.join(KIT, name), cls.tmp)
        for d in ("data", "templates"):
            shutil.copytree(os.path.join(KIT, d), os.path.join(cls.tmp, d))
        os.makedirs(os.path.join(cls.tmp, "source"))
        shutil.copytree(os.path.join(KIT, "source", "crops"), os.path.join(cls.tmp, "source", "crops"))
        sys.path.insert(0, cls.tmp)

    @classmethod
    def tearDownClass(cls):
        shutil.rmtree(cls.tmp, ignore_errors=True)

    def run_pb(self, *args):
        r = subprocess.run([sys.executable, "pricebook.py", *args], cwd=self.tmp, capture_output=True, text=True)
        return r.returncode, r.stdout + r.stderr

    def rows(self):
        return {r["id"]: r for r in csv.DictReader(open(os.path.join(self.tmp, "data", "prices.csv"), encoding="utf-8"))}

    def test_01_validate(self):
        code, out = self.run_pb("validate")
        self.assertEqual(code, 0, out)
        self.assertIn("RESULT PASS", out)

    def test_02_sizes(self):
        import pricebook as pb
        for a, b in [("36x24", "24x36"), ('24" x 36"', "24x36"), ("8 1/2 x 11", "8.5x11"), ("8½x11", "8.5x11"),
                     ("letter", "8.5x11"), ("11 by 17", "11x17"), ("tabloid", "11x17")]:
            self.assertEqual(pb.norm_size(a), b, a)
        self.assertIsNone(pb.norm_size("banana"))

    def test_03_find(self):
        code, out = self.run_pb("find", "36x24", "color")
        self.assertIn("lf-color-24x36", out)
        code, out = self.run_pb("find", "b/w", "letter", "duplex")
        self.assertIn("bw-8.5x11-side", out)
        code, out = self.run_pb("find", "color", "letter", "30")
        self.assertIn("color-8.5x11-side-21up", out)
        self.assertNotIn("color-8.5x11-side-1-20", out)

    def test_04_quote(self):
        r = self.rows()   # expected total from the live rows, so a routine price change does not break the test
        want = 300 * float(r["bw-8.5x11-side"]["price"]) + 10 * float(r["comb-half-inch"]["price"])
        code, out = self.run_pb("quote", "bw-8.5x11-side", "300", "+", "comb-half-inch", "10")
        self.assertIn(f"${want:,.2f}", out, out)    # comb-cover retired 2026-10-01 (covers included)
        code, out = self.run_pb("quote", "color-8.5x11-side", "20")
        self.assertIn("$15.80", out, out)           # 20 sides at the 1-20 rate
        code, out = self.run_pb("quote", "color-8.5x11-side", "30")
        self.assertIn("$17.70", out, out)           # 30 sides at the 21+ rate
        code, out = self.run_pb("quote", "lf-color-bond-sqft", "2", "--w", "24", "--h", "60")
        self.assertIn("$60.00", out, out)
        code, out = self.run_pb("quote", "scoring-per-1000", "300")
        self.assertIn("$35.00", out, out)          # minimum applies
        code, out = self.run_pb("quote", "photo-24x36", "2", "--tax", "10")
        self.assertIn("$79.20", out, out)
        code, out = self.run_pb("quote", "comb-half-inch", "10", "+", "comb-cover", "20")
        self.assertNotEqual(code, 0, out)          # retired rows are never priced
        self.assertIn("retired", out, out)

    def test_05_set_and_log(self):
        code, out = self.run_pb("set", "vellum-18x24", "3.25", "--source", "test")
        self.assertEqual(code, 0, out)
        self.assertEqual(self.rows()["vellum-18x24"]["price"], "3.25")
        log = open(os.path.join(self.tmp, "data", "changelog.csv"), encoding="utf-8").read()
        self.assertIn("vellum-18x24", log)

    def test_06_resolve_line_card(self):
        code, out = self.run_pb("resolve", "C02", "a=ok")
        self.assertEqual(code, 0, out)
        r = self.rows()["lf-bw-30x42-walkin"]
        self.assertEqual((r["status"], r["price"], r["cards"]), ("active", "3.50", ""))

    def test_07_resolve_writein(self):
        code, out = self.run_pb("resolve", "C06", "a=0.07", "b=0.06")
        r = self.rows()
        self.assertEqual(r["bw-8.5x11-simplex-21-99"]["price"], "0.07")
        self.assertEqual(r["bw-8.5x11-simplex-100up"]["status"], "active")

    def test_08_resolve_option_retire(self):
        code, out = self.run_pb("resolve", "C22", "opt=1")
        self.assertEqual(code, 0, out)
        boxes = [r for r in self.rows().values() if r["unit"] == "box"]
        self.assertTrue(boxes and all(r["status"] == "retired" for r in boxes))

    def test_09_build(self):
        code, out = self.run_pb("build")
        self.assertEqual(code, 0, out)
        for f in ("Rainbow_PriceBook.xlsx", "PriceBook.html", "pricebook_mirror.md"):
            self.assertTrue(os.path.exists(os.path.join(self.tmp, "build", f)), f)
        mirror = open(os.path.join(self.tmp, "build", "pricebook_mirror.md"), encoding="utf-8").read()
        contacts = os.path.join(self.tmp, "data", "contacts.csv")
        internal = [r["value"] for r in csv.DictReader(open(contacts, encoding="utf-8"))
                    if r["visibility"] == "internal"] if os.path.exists(contacts) else []
        for num in internal:
            self.assertNotIn(num, mirror)          # staff numbers stay internal
        code, out = self.run_pb("conflicts-pdf")
        self.assertEqual(code, 0, out)

    def test_10_no_secrets(self):
        import pricebook as pb                     # fragments live in KIT/private/secret_check.txt, never in git
        pb.ROOT = KIT
        for name in ("prices.csv", "contacts.csv", "conflicts.json"):
            p = os.path.join(self.tmp, "data", name)
            if not os.path.exists(p):
                continue
            txt = open(p, encoding="utf-8").read()
            for bad in pb.secret_fragments():
                self.assertNotIn(bad, txt, name)

if __name__ == "__main__":
    unittest.main(verbosity=1)
