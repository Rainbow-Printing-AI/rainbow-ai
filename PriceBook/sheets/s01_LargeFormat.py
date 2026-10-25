"""s01_LargeFormat.py - Large Format Xerox Pricing (replaces scan_147 p01)."""
import sheetlib as L

SHEET = {"num": "01", "name": "LargeFormat", "title": "LARGE FORMAT XEROX PRICING",
         "source": "scan_147 p01",
         "covers": ["Large Format - B/W", "Large Format - Color", "Large Format - Vellum"]}

ROW_PT = 26
TAB_IN = 4.75


def build(pb: L.Prices):
    doc = L.new_document(margins_in=(0.5, 0.6, 0.5, 0.6), base_font=L.SERIF)
    m = lambda rid, f="price": pb.money(rid, f)

    # boxed header (thin rectangle, two centred lines)
    t = L.table(doc, 1, 1, widths_in=[6.7], align="center", borders="outer", border_sz=24)
    L.set_table_borders(t, "outer", sz=24, val="thinThickSmallGap")
    c = t.cell(0, 0)
    L.cell_text(c, "RAINBOW PRINTING\n& OFFICE SUPPLY", align="center", before=4, after=4,
                font=L.SERIF, size=32, line=38)

    # former pasted strip -> typeset text, same spot
    scan1 = pb.money("scan-lf-color-first", drop_zero_cents=True)
    scan2 = pb.money("scan-lf-color-add", drop_zero_cents=True)
    L.para(doc, f"COLOR SCAN {scan1} FIRST PAGE {scan2} EACH PAGE AFTER", align="center",
           before=9, after=8, font=L.SANS, size=12, bold=True)

    # title, two lines
    L.para(doc, "LARGE FORMAT XEROX",
           align="center", font=L.SERIF, size=34, line=38)
    L.para(doc, "PRICING", align="center", font=L.SERIF, size=34, line=38, after=6)

    def row(label, rid, first=False):
        p = L.para(doc, before=11 if first else 0, tabs=[(TAB_IN, "left", None)], indent_in=0.1,
                   line=ROW_PT)
        L.add_run(p, label, font=L.SERIF, size=25)
        L.add_run(p, "\t" + m(rid) + " ea", font=L.SERIF, size=25)

    groups = [
        ("18 x 24", "lf-bw-18x24-walkin", "lf-color-18x24", "vellum-18x24"),
        ("24 x 36", "lf-bw-24x36-walkin", "lf-color-24x36", "vellum-24x36"),
        ("30 x 42", "lf-bw-30x42-walkin", "lf-color-30x42", None),
        ("36 x 48", "lf-bw-36x48-walkin", "lf-color-36x48", None),
    ]
    for size, bw, col, vel in groups:
        row(f"{size} B/W copy", bw, first=True)
        row(f"{size} Color (plans)", col)
        if vel:
            row("Copy onto vellum (B/W)", vel)

    # closing paragraph, centred, same style as the original
    sq = pb.money("lf-bw-other-sqft")
    bond = pb.money("lf-color-bond-sqft")
    photo = pb.money("lf-color-photo-sqft")
    transp = pb.money("lf-color-transparency-sqft")
    cs = dict(font=L.SERIF, size=21)
    def closing(text, before):
        pp = L.para(doc, text, align="center", before=before, line=25, indent_in=0.9, **cs)
        pp.paragraph_format.right_indent = L.Inches(0.9)

    closing(f"Otherwise B/W large format Xerox copies charged at {sq} per square foot.", 12)
    closing(f"Color per square foot: posters and graphics on bond {bond}, "
            f"transparency {transp}, photo paper (custom sizes) {photo}.", 6)

    L.rev_stamp(doc, pb)
    return doc
