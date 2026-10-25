"""s12_NCREnvelopes.py - NCR Forms / Envelopes / Special Inks grid (replaces scan_147 p12).

Original was an outside trade printer's grid (cost, 'Multiply x2.5' in pen).  The CSV price
column already carries the x2.5, so this sheet prints retail only.  BUS CARDS block retired.
"""
import sheetlib as L

SHEET = {"num": "12", "name": "NCREnvelopes", "title": "NCR FORMS / ENVELOPES / SPECIAL INKS",
         "source": "scan_147 p12", "covers": ["NCR Forms", "Envelopes", "Special Inks"]}

HDR_FILL = None         # no cell fills: prints on blue paper stock, so white/black only
LINE = (12, "000000")   # 1.5pt grid rule
SANS = L.SANS


def build(pb: L.Prices):
    doc = L.new_document(margins_in=(0.5, 0.5, 0.45, 0.5), landscape=True, base_font=SANS, base_size=10)
    m = lambda rid: pb.money(rid, dollar=False)          # bare 99.00 like the original grid

    # columns: 0 label | 1-4 NCR | 5 gap | 6 label | 7-10 envelopes
    widths = [0.78, 1.04, 1.04, 1.04, 1.04, 0.22, 0.78, 1.0, 1.0, 1.0, 1.0]
    NR = 16
    t = L.table(doc, NR, 11, widths_in=widths, align="center", borders="none")
    L.set_cell_margins_table(t, 0.0, 0.04)
    heights = [0.5, 0.22, 0.46] + [0.52] * 5 + [0.14, 0.22, 0.46] + [0.52] * 5
    for r, h in zip(t.rows, heights):
        L.set_row_height(r, h, "exact")

    def clean(c):
        ps = c.paragraphs
        for p in ps[1:]:
            if not p.text and not p.runs:
                p._p.getparent().remove(p._p)

    def box(c, fill=None):
        L.set_cell_borders(c, top=LINE, bottom=LINE, left=LINE, right=LINE)
        if fill:
            L.shade(c, fill)

    def put(c, text, *, size=9, bold=True, align="center", fill=None, border=True, valign="center", **k):
        L.cell_text(c, text, align=align, valign=valign, font=SANS, size=size, bold=bold, color=L.BLACK, **k)
        if border:
            box(c, fill)

    def cellm(r1, c1, r2, c2):
        for rr in range(r1, r2 + 1):          # rule every underlying cell so merged edges draw fully
            for cc in range(c1, c2 + 1):
                box(t.cell(rr, cc))
        c = L.merge(t, r1, c1, r2, c2)
        clean(c)
        return c

    # ---- boxed headings
    c = cellm(0, 1, 0, 4); put(c, "NCR FORMS", size=22, fill=HDR_FILL)
    c = cellm(0, 6, 0, 10); put(c, "ENVELOPES", size=22, fill=HDR_FILL)

    # ---- NCR bands
    parts = [("2\nPART", "3\nPART", "4\nPART", "NCR\n2nd SIDE")]
    for top, size, ids in ((1, "8½ x 11", "8.5x11"), (9, "8½ x 14", "8.5x14")):
        for j in range(4):
            put(t.cell(top, 1 + j), size, size=8)
            put(t.cell(top + 1, 1 + j), parts[0][j], size=10, fill=HDR_FILL, line=11)
        put(t.cell(top + 1, 0), "SETS", size=10, fill=HDR_FILL)
        for i, lab in enumerate(["125", "250", "500", "1000", "ADD'L\n1000"]):
            r = top + 2 + i
            put(t.cell(r, 0), lab, size=10, line=11)
            q = ["125", "250", "500", "1000", "addl-1000"][i]
            for j, part in enumerate(["2-part", "3-part", "4-part", "2ndside"]):
                put(t.cell(r, 1 + j), m(f"ncr-{ids}-{part}-{q}"), size=14)

    # ---- envelopes
    stocks = ["WOVE", "LAID", "LINEN", "WHITE"]
    descr = ["#6¾, #9, #10\nREGULAR", "COTTON LAID\nPARCHMENT\n#10, A-2, A-6",
             "BECKETT\nCLASSIC\nSTRATHMORE", "9 x 12, 10 x 13\nCATALOG\nBOOKLET"]
    slugs = ["wove", "laid", "linen", "white-catalog"]
    for j in range(4):
        put(t.cell(1, 7 + j), stocks[j], size=8)
        put(t.cell(2, 7 + j), descr[j], size=7, fill=HDR_FILL, line=9)
    put(t.cell(2, 6), "QTY", size=10, fill=HDR_FILL)
    for i, lab in enumerate(["125", "250", "500", "1000", "ADD'L\n1000"]):
        r = 3 + i
        put(t.cell(r, 6), lab, size=10, line=11)
        for j in range(4):
            c = t.cell(r, 7 + j)
            if i == 0:                       # no 125 envelope price on the original: stays blank
                put(c, "", size=14)
            else:
                q = ["250", "500", "1000", "addl-1000"][i - 1]
                put(c, m(f"env-{slugs[j]}-{q}"), size=14)

    # ---- special inks (lower right, where bus cards used to sit beside the envelopes)
    c = cellm(9, 6, 10, 10); put(c, "SPECIAL INKS", size=22, fill=HDR_FILL)
    c = cellm(11, 6, 11, 10); put(c, "ADD FOR", size=12, fill=HDR_FILL)
    inks = [("ink-standard", "STANDARD INK CHARGE", ""), ("ink-pms", "PMS INK CHARGE", ""),
            ("ink-metallic", "METALLIC INK CHARGE", ""), ("ink-close-reg", "CLOSE REGISTRATION CHARGE", "per 1,000")]
    for i, (rid, lab, unit) in enumerate(inks):
        r = 12 + i
        c = cellm(r, 6, r, 8); put(c, lab, size=11, align="left")
        c.paragraphs[0].paragraph_format.left_indent = L.Inches(0.08)
        c = cellm(r, 9, r, 10)
        p = put(c, m(rid), size=14)
        if unit:
            L.add_run(c.paragraphs[0], "  " + unit, font=SANS, size=8, bold=True, color=L.BLACK)
    # row 15 on the right is left open (4 inks only)
    for cc in range(6, 11):
        pass

    L.rev_stamp(doc, pb)
    return doc
