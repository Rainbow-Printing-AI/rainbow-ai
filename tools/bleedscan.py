"""bleedscan.py — find hard edges that run parallel to a trim edge inside a narrow band.

Shared by impose.py (choose mirror vs edge-extend bleed per side) and verify_print.py
(reject generated bleed that shows a mirrored box/QR/rule). Not a CLI.

A "hard edge" = a step of more than STEP levels (any RGB channel, measured across 2 px)
that holds at the same distance from the trim (+-1 px) for at least MIN_RUN_IN inches
along the edge. Soft gradients, blurred shapes and photo texture don't qualify; a box,
QR code, rule line or large type sitting near the trim does.
"""
import numpy as np

STEP = 60          # 0-255 levels across 2 px
MIN_RUN_IN = 0.15  # inches of continuous edge parallel to the trim
SKIP_PX = 2        # ignore this many px at each end of the band (antialiased trim/bleed lines)


def _longest_run(x):
    x = np.concatenate(([0], x.astype(np.int8), [0]))
    d = np.diff(x)
    s, e = np.where(d == 1)[0], np.where(d == -1)[0]
    return int((e - s).max()) if len(s) else 0


def hard_edge(band, dpi):
    """band: array (L, w[, C]) — rows run ALONG the trim edge, columns run across the band.
    Returns (run_inches, column) of the longest parallel hard edge, or (0.0, None)."""
    b = np.asarray(band).astype(np.int16)
    if b.ndim == 2:
        b = b[..., None]
    if b.shape[1] < 2 * SKIP_PX + 3 or b.shape[0] < 3:
        return 0.0, None
    d = np.abs(b[:, 2:] - b[:, :-2]).max(axis=2)      # column j ~ band column j+1
    hit = d > STEP
    hit[:, :SKIP_PX] = False
    hit[:, -SKIP_PX:] = False
    h = hit.copy()
    h[:, 1:] |= hit[:, :-1]
    h[:, :-1] |= hit[:, 1:]
    best, col = 0, None
    for j in range(h.shape[1]):
        if not h[:, j].any():
            continue
        r = _longest_run(h[:, j])
        if r > best:
            best, col = r, j + 1
    return best / dpi, col


def side_bands(a, pad):
    """The band of art each side's mirrored bleed would copy (pad px + 2 inside the trim),
    oriented rows-along-edge, column 0 at the trim. a: HxW[xC] array of the art at trim."""
    w = min(pad + 2, a.shape[0] // 2, a.shape[1] // 2)
    return {
        "left": a[:, :w],
        "right": a[:, ::-1][:, :w],
        "top": np.swapaxes(a[:w], 0, 1),
        "bottom": np.swapaxes(a[::-1][:w], 0, 1),
    }


def choose_modes(a, pad, dpi):
    """Per-side bleed fill for art array `a`: 'reflect' unless the mirror band holds a hard
    parallel edge, then 'edge'. Returns ({side: mode}, {side: (run_in, col_px)})."""
    modes, why = {}, {}
    for side, band in side_bands(a, pad).items():
        run, col = hard_edge(band, dpi)
        if run >= MIN_RUN_IN:
            modes[side], why[side] = "edge", (run, col)
        else:
            modes[side] = "reflect"
    return modes, why
