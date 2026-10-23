"""Build web-ready images for the portfolio from the original design exports.

Usage:
    python3 tools/build_assets.py "/path/to/Final Portfolio" assets

Needs Pillow (pip install pillow). Re-run it whenever a board changes, or once
"Vega Group Project.png" is added to the source folder: Vega's full board is
then cut into tiles like the others and the site picks it up automatically.
"""
import filecmp
import glob
import json
import os
import shutil
import sys

from PIL import Image, ImageSequence

Image.MAX_IMAGE_PIXELS = None

PROJECTS = [
    # slug, board file, cover file, cover panel
    # "cover panel": when a board opens on a crop of the project's cover (shown just above the board
    # on the page), the width of that opening panel in px at the 1440 px board height. The page then
    # opens the strip just past it, on new material. Measured by eye from board-00-1440.webp; None
    # when the board opens on something else. Re-check it if a board is exported again.
    ("goodshift", "GoodShift Project.png", "Goodshift Thumbnail.png", 1682),
    ("heibuddy", "HeiBuddy Project.png", "HeiBuddy Thumbnail.png", 1249),
    ("iccs", "Iccs Project.png", "Iccs Thumbnail.png", None),
    ("vega", "Vega Group Project.png", "Vega Group Thumbnail.png", None),
    ("netpure", "Netpure Project.png", "Netpure Thumbnail.png", 1384),
]

BOARD_HEIGHTS = (1440, 720)   # 2x and 1x for a strip shown up to ~720 css px tall
TILE_RATIO = 5 / 3            # tile width / height
COVER_WIDTHS = (1800, 1200, 720, 360)   # 360: the index thumbnails
BRAND_BLUE = (0, 119, 255)    # #0077FF, the colour of Roshan's mark
MARK_FRONT_FRAME = 13         # the head faces forward on this frame


def save_webp(im, path, quality):
    im.save(path, "WEBP", quality=quality, method=6)


def build_board(src, out_dir, cover_panel=None):
    # A board exported again with fewer tiles must not leave the old extra tiles behind.
    for old in glob.glob(os.path.join(out_dir, "board-*.webp")):
        os.remove(old)
    board = Image.open(src).convert("RGB")
    w, h = board.size
    big_h = BOARD_HEIGHTS[0]
    big_w = round(w * big_h / h)
    big_w += big_w % 2  # keep it even so the 1x tiles line up exactly
    big = board.resize((big_w, big_h), Image.LANCZOS)
    small = big.resize((big_w // 2, big_h // 2), Image.LANCZOS)
    tile_w = round(big_h * TILE_RATIO)
    tile_w += tile_w % 2
    tiles = []
    x = 0
    i = 0
    while x < big_w:
        x1 = min(big_w, x + tile_w)
        # fold a sliver of a last tile into the previous one
        if big_w - x1 < tile_w // 4:
            x1 = big_w
        name = f"board-{i:02d}"
        save_webp(big.crop((x, 0, x1, big_h)), os.path.join(out_dir, f"{name}-1440.webp"), 80)
        save_webp(small.crop((x // 2, 0, x1 // 2, big_h // 2)), os.path.join(out_dir, f"{name}-720.webp"), 82)
        tiles.append({"src": name, "w": x1 - x, "h": big_h})
        x = x1
        i += 1
    board = {"width": big_w, "height": big_h}
    if cover_panel:
        board["start"] = cover_panel
    board["tiles"] = tiles
    return board


def build_cover(src, out_dir):
    cover = Image.open(src).convert("RGB")
    w, h = cover.size
    for cw in COVER_WIDTHS:
        ch = round(h * cw / w)
        save_webp(cover.resize((cw, ch), Image.LANCZOS), os.path.join(out_dir, f"cover-{cw}.webp"), 80)
    avg = cover.resize((1, 1), Image.BOX).getpixel((0, 0))
    return {"width": w, "height": h, "avg": "#%02X%02X%02X" % avg}


def tint(frame, rgb):
    """Turn a GIF frame into a clean anti-aliased mask filled with one colour."""
    rgba = frame.convert("RGBA")
    r, _, _, a = rgba.split()
    # the mark is pure blue (R=0) on transparency; near-white fringe pixels
    # in the GIF become (almost) transparent instead of showing as specks
    alpha = Image.eval(r, lambda v: 255 - v)
    alpha = Image.composite(alpha, a, a)
    solid = Image.new("RGBA", rgba.size, rgb + (255,))
    solid.putalpha(alpha)
    return solid


def build_mark(src, out_dir):
    gif = Image.open(src)
    frames = [tint(f, BRAND_BLUE) for f in ImageSequence.Iterator(gif)]
    # start the loop facing forward, so first paint and stills show the face
    frames = frames[MARK_FRONT_FRAME:] + frames[:MARK_FRONT_FRAME]
    duration = gif.info.get("duration", 170)
    for size in (512, 320, 160):
        seq = [f.resize((size, size), Image.LANCZOS) for f in frames]
        seq[0].save(os.path.join(out_dir, f"mark-{size}.webp"), "WEBP", save_all=True,
                    append_images=seq[1:], duration=duration, loop=0, quality=82,
                    alpha_quality=80, method=6)
    # The encoder merges identical neighbouring frames, so record what was actually written.
    with Image.open(os.path.join(out_dir, "mark-512.webp")) as written:
        written_frames = getattr(written, "n_frames", 1)
    # turnaround sheet: eight evenly spaced views in one row, for a figure
    views = [frames[round(i * len(frames) / 8) % len(frames)] for i in range(8)]
    cell = 240
    sheet = Image.new("RGBA", (cell * len(views), cell), (0, 0, 0, 0))
    for i, f in enumerate(views):
        sheet.alpha_composite(f.resize((cell, cell), Image.LANCZOS), (i * cell, 0))
    sheet.save(os.path.join(out_dir, "mark-turnaround.webp"), "WEBP", quality=90, method=6)
    front = frames[0]
    front.resize((512, 512), Image.LANCZOS).save(os.path.join(out_dir, "mark-static-512.png"), optimize=True)
    front.resize((160, 160), Image.LANCZOS).save(os.path.join(out_dir, "mark-static-160.png"), optimize=True)
    for size, name in ((32, "favicon-32.png"), (180, "apple-touch-icon.png")):
        tile = Image.new("RGBA", (size, size), (233, 223, 202, 255) if size == 180 else (0, 0, 0, 0))
        pad = size // 10 if size == 180 else 0
        m = front.resize((size - 2 * pad, size - 2 * pad), Image.LANCZOS)
        tile.alpha_composite(m, (pad, pad))
        tile.save(os.path.join(out_dir, name), optimize=True)
    return {"frames": written_frames, "duration": duration}


def copy_resume(src_dir, assets_dir):
    """Copy the résumé only when assets/ has none. A corrected PDF placed in assets/ by hand is
    never overwritten by an older export; when the two differ, say so."""
    src = os.path.join(src_dir, "Roshan_Bharti_Resume.pdf")
    dst = os.path.join(assets_dir, "Roshan_Bharti_Resume.pdf")
    if not os.path.exists(src):
        print("résumé: not in the export folder, assets/ copy kept")
    elif not os.path.exists(dst):
        shutil.copyfile(src, dst)
        print("résumé copied")
    elif not filecmp.cmp(src, dst, shallow=False):
        print("WARNING résumé: the export folder's PDF differs from assets/Roshan_Bharti_Resume.pdf.\n"
              "        Kept the one in assets/. To use the export's, copy it over by hand.")


def main(src_dir, assets_dir, only=None):
    manifest_path = os.path.join(assets_dir, "manifest.json")
    if only == "mark":
        with open(manifest_path) as fh:
            manifest = json.load(fh)
        manifest["mark"] = build_mark(os.path.join(src_dir, "Logo-GIF.gif"), os.path.join(assets_dir, "mark"))
        with open(manifest_path, "w") as fh:
            json.dump(manifest, fh, indent=2)
        print("mark rebuilt")
        return
    manifest = {"projects": {}}
    work_dir = os.path.join(assets_dir, "work")
    for slug, board_file, cover_file, cover_panel in PROJECTS:
        out = os.path.join(work_dir, slug)
        os.makedirs(out, exist_ok=True)
        entry = {"cover": build_cover(os.path.join(src_dir, cover_file), out)}
        board_path = os.path.join(src_dir, board_file)
        entry["board"] = build_board(board_path, out, cover_panel) if os.path.exists(board_path) else None
        manifest["projects"][slug] = entry
        tiles = len(entry["board"]["tiles"]) if entry["board"] else "no board"
        print(f"{slug}: cover ok, tiles: {tiles}")

    mark_dir = os.path.join(assets_dir, "mark")
    os.makedirs(mark_dir, exist_ok=True)
    manifest["mark"] = build_mark(os.path.join(src_dir, "Logo-GIF.gif"), mark_dir)
    print("mark ok")

    copy_resume(src_dir, assets_dir)
    with open(manifest_path, "w") as fh:
        json.dump(manifest, fh, indent=2)
    print("manifest written")


if __name__ == "__main__":
    if len(sys.argv) not in (3, 4):
        sys.exit(__doc__)
    main(sys.argv[1], sys.argv[2], sys.argv[3] if len(sys.argv) == 4 else None)
