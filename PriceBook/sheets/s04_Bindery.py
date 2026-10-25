"""s04_Bindery.py - Bindery prices (replaces scan_147 p04)."""
import sheetlib as L

SHEET = {"num": "04", "name": "Bindery", "title": "BINDERY PRICES", "source": "scan_147 p04",
         "covers": ["Bindery & Finishing", "Laminating", "Labor & Design"]}

FS = 13          # body size (original is small Calibri-like; enlarged for the counter)
GAP = 7            # space after each group, pt


def build(pb: L.Prices):
    doc = L.new_document(margins_in=(0.55, 0.7, 0.5, 0.7), base_font=L.SANS, base_size=FS)
    m = lambda rid, f="price", **k: pb.money(rid, f, dollar=False, **k)          # 50.00
    md = lambda rid, f="price": pb.money(rid, f)                                  # $10.00
    lead = lambda rid: pb.money(rid, dollar=False, cents_style="leading")        # .50
    cents = lambda rid: f"{int(pb.value(rid) * 100)}¢"                       # 5¢

    L.para(doc, "BINDERY PRICES", align="center", font=L.SANS, size=22, after=12)

    rows = [
        (["Cutting"], [f"{m('cutting')} per cut"]),
        (["Padding"], [f"{m('padding-base')} base plus per pad price; {md('padding-base','min_charge')} minimum",
                       f"    {lead('padding-per-pad')} per pad"]),
        (["Numbering"], [f"{m('numbering-per-1000')} per 1,000 (numbering machine);",
                       f"or copy cost plus {lead('numbering-per-page')} per page (printed)"]),
        (["Folding"], [f"{m('folding-per-1000')} per 1,000", f"{m('folding-per-1000','min_charge')} minimum"]),
        (["Scoring"], [f"{m('scoring-per-1000')} per 1,000", f"{m('scoring-per-500')} per 500",
                       f"{m('scoring-per-1000','min_charge')} minimum"]),
        (["Perfing"], [f"{m('perfing-per-1000')} per 1,000", f"{m('perfing-per-500')} per 500",
                       f"{m('perfing-per-1000','min_charge')} minimum"]),
        (["Drilling"], [f"{m('drilling')} per hole, up to 2” thick"]),
        (["Sorting (manual)"], [f"{cents('sorting-manual')} per page"]),
        (["Stapling (manual)"], [f"{cents('stapling-manual')} per staple"]),
        (["Spiral Binding", "(Ibico comb)"], [f"{m('comb-half-inch')} per book,", "any thickness, covers included"]),
        (["Coil Binding"], [f"{m('coil-half-inch')} per book,", "any thickness, covers included"]),
        None,  # laminating block
        (["Shrink wrapping"], [f"{m('shrink-wrap')} per 500 sheets"]),
        (["Booklet making", "(by machine)"], [f"{cents('booklet-making')} per book"]),
        (["Corner Rounder"], [f"{m('corner-round-per-1000')} per 1,000, 4 sides",
                              f"{m('corner-round-per-500')} per 500, 4 sides",
                              f"{m('corner-round-per-1000','min_charge')} minimum"]),
        (["Mounting"], [f"{m('mounting')} per piece (board not included)"]),
        (["Labor"], [f"{m('labor-hourly')} per hour"]),
        (["Graphic Services"], [f"{m('graphic-services')} per hour / get estimate"]),
    ]
    lam = [("Card size", m("laminate-card")), ("8.5x11", m("laminate-8.5x11")),
           ("8.5x14", m("laminate-8.5x14")), ("11x17", m("laminate-11x17")),
           ("24” wide", f"{m('laminate-24in-sqft')} per square foot")]

    t = L.table(doc, len(rows) + len(lam), 2, widths_in=[2.55, 4.55], align="center")
    L.set_cell_margins_table(t, 0.0, 0.06)
    ri = 0
    for r in rows:
        if r is None:
            row = t.rows[ri]
            L.cell_text(row.cells[0], "Laminating", valign="top", font=L.SANS, size=FS)
            L.cell_text(row.cells[1], "", valign="top", font=L.SANS, size=FS)
            ri += 1
            for i, (lab, val) in enumerate(lam):
                row = t.rows[ri]
                last = i == len(lam) - 1
                c0 = row.cells[0]
                L.cell_text(c0, lab, valign="top", after=GAP if last else 0, font=L.SANS, size=FS)
                c0.paragraphs[0].paragraph_format.left_indent = L.Inches(0.55)
                L.cell_text(row.cells[1], val, valign="top", after=GAP if last else 0, font=L.SANS, size=FS)
                ri += 1
            continue
        lab, val = r
        row = t.rows[ri]
        L.cell_text(row.cells[0], "\n".join(lab), valign="top", after=GAP, font=L.SANS, size=FS)
        L.cell_text(row.cells[1], "\n".join(val), valign="top", after=GAP, font=L.SANS, size=FS)
        ri += 1
    L.no_split_rows(t)
    L.rev_stamp(doc, pb)
    return doc
