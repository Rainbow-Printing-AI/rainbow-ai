"""s11_Labels.py - Personal Label Printing (replaces scan_147 p11)."""
import sheetlib as L

SHEET = {"num": "11", "name": "Labels", "title": "Personal Label Printing",
         "source": "scan_147 p11", "covers": ["Labels"]}

INDIGO = L.RGBColor(0x3C, 0x2D, 0x74)
ROW_IN = 0.58
LBL = 13
PRC = 14.5


def build(pb: L.Prices):
    doc = L.new_document(margins_in=(0.45, 0.55, 0.45, 0.55), base_font=L.SANS)
    m = lambda rid: pb.money(rid)

    L.logo_header(doc, logo_width_in=4.7, name_size=20, contact_size=12.5, addr_size=9, after=10)
    L.para(doc, "Personal Label Printing", align="center", font=L.SANS, size=42, bold=True,
           color=L.RED, before=4, after=18)
    L.para(doc, "Printed on Avery 5160 White Label - 30 on a Page", align="center",
           font=L.SANS, size=19, bold=True, after=12)

    qtys = [("120", "4", 120), ("250", "9", 250), ("500", "16", 500), ("1000", "34", 1000)]
    addons = [("Extra Charges for Clear Label Stock Per Sheet", "labels-clear-stock"),
              ("Add a Logo Extra Charge", "labels-logo"),
              ("Any Other Avery Label Template Extra Charge", "labels-other-template"),
              ("Misc. Art Work Charges", "labels-artwork")]
    nrows = 1 + len(qtys) + len(addons) + 1
    W = [5.0, 1.2, 1.2]
    t = L.table(doc, nrows, 3, widths_in=W, align="center", borders="outer",
                border_sz=48, border_color="1A1A1A")
    L.set_cell_margins_table(t, 0.02, 0.1)
    L.no_split_rows(t)

    # header row
    L.set_row_height(t.rows[0], 0.72, "exact")
    for i, (txt, al) in enumerate([("Quantity Printed  Labels", "center"),
                                   ("Black Ink", "center"), ("Color Ink", "center")]):
        L.cell_text(t.cell(0, i), txt, align=al, valign="bottom", font=L.SANS, size=15.5,
                    bold=True, underline=True)

    r = 1
    for q, sheets, n in qtys:
        L.set_row_height(t.rows[r], ROW_IN, "exact")
        L.cell_text(t.cell(r, 0), f"{q} Finished Labels {sheets} sheets Includes Type/Set-Up",
                    font=L.SANS, size=LBL, bold=True)
        for ci, col in ((1, "black"), (2, "color")):
            L.cell_text(t.cell(r, ci), m(f"labels-5160-{col}-{q}"), align="center",
                        font=L.SANS, size=PRC, bold=True)
        r += 1
    for label, rid in addons:
        L.set_row_height(t.rows[r], ROW_IN, "exact")
        L.cell_text(t.cell(r, 0), label, font=L.SANS, size=LBL, bold=True)
        row = pb.row(rid)
        txt = m(rid) if row["price"].strip() else "Estimate"
        for ci in (1, 2):
            L.cell_text(t.cell(r, ci), txt, align="center", font=L.SANS, size=PRC, bold=True)
        r += 1

    # closing notice inside the box
    L.set_row_height(t.rows[r], 0.92, "exact")
    c = L.merge(t, r, 0, r, 2)
    L.cell_text(c, "Prices Do Not Include Sales Tax\nTurnaround Time - Same or Next Day",
                align="center", valign="center", font=L.SANS, size=17, bold=True,
                color=INDIGO, line=26)

    L.rev_stamp(doc, pb)
    return doc
