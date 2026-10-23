# Roshan Bharti — portfolio

The portfolio site of Roshan Bharti, brand designer at Moshi Moshi — The Communication Company.

The idea: Roshan's own identity (warm paper, ink, Signal Blue `#0077FF`, Bricolage Grotesque and his turning-head mark) frames the start and the end of the page. In between, each client project paints its whole section in that brand's own palette, with a full-bleed cover, the brief, the palette as a printer's colour bar, and the full presentation board as a horizontal strip.

It is a static site: one HTML page, plain CSS and JS, no framework and no build step at runtime. It works opened straight from disk and on any static host.

## Preview

Open `index.html` in a browser, or serve the folder:

```sh
python3 -m http.server 8000
# then visit http://localhost:8000
```

## Edit the words

Every word about Roshan and his clients lives in `content.json`: the bio, proof points, experience, contact details, and for each project its sector, disciplines, headline, challenge, approach, idea, deliverables, palette, board description (`board_alt`) and cover description (`cover_alt`, read by screen readers).

The words shown in Signal Blue are named in `content.json` too: `tagline_emphasis` (the end of the hero tagline) and `about.heading_emphasis` (the end of the About heading). If you change the tagline or heading, change these to match; the build stops with a message if the phrase is no longer in the text.

After editing, regenerate the page:

```sh
python3 tools/build_site.py
```

`index.html` and `404.html` are generated (and `tools/og-render.html`, the page behind the share image). Don't edit them by hand; your changes would be overwritten the next time the build runs. The build needs only Python 3 (no packages). Running it twice gives the same output.

## How it is put together

| Path | What it is |
| --- | --- |
| `content.json` | All copy. The single source of truth. |
| `assets/manifest.json` | Image sizes and board tiles, written by `tools/build_assets.py`. |
| `src/page.html` | The page template (head, header, hero, index, about, contact, footer). |
| `src/project.html` | The one template every project is rendered from. |
| `src/board-strip.html` | The board strip, used when a project has a board. |
| `src/board-preview.html` | The "board in preparation" block, used when the manifest says `"board": null`. |
| `src/themes.json` | How each brand's palette maps onto its section (background, text, the dark stage behind the board). Project names are always set in the section's text colour, never in a logo colour. The five grounds are picked from each brand's own palette so that no two sections look alike. The build checks every pair against WCAG AA and stops if one fails. A new project without an entry gets a theme derived from its palette: the first colour that takes near-black, black or white text at AA, or a neutral dark ground if none does. Check how it looks next to its neighbours and add an entry if it needs one. |
| `src/styles.css`, `src/main.js` | Source of `assets/site.css` and `assets/site.js` (copied as is by the build). |
| `src/404.html` | Template for `404.html`. The build puts the stylesheet and the mark inside the page, because hosts serve it at whatever address was missing. |
| `src/og.html` | Template for the share image. The build fills it from `content.json` and `src/themes.json` and writes `tools/og-render.html` (not deployed). |
| `tools/build_site.py` | The site generator. |
| `tools/build_assets.py` | Turns the original exports into web images and writes the manifest. |

## Rebuild the images

The images in `assets/work/` and `assets/mark/` are made from the original "Final Portfolio" export folder by `tools/build_assets.py`. It needs Pillow (`pip install pillow`):

```sh
python3 tools/build_assets.py "/path/to/Final Portfolio" assets
python3 tools/build_site.py
```

Each board is cut into seamless tiles 1440 px and 720 px tall. On the page the strip height is always a whole multiple of 3 px, so every tile lands on whole pixels, and each tile overlaps the next by one pixel, so no seams show at fractional screen scales (125 %, 150 %) either. Each tile's `sizes` is written from the two `--strip-h` rules marked `strip: desktop` and `strip: phone` in `src/styles.css`, so phones download the smaller tiles. The other `sizes` (index thumbnails, the hero and contact marks) are read from `src/styles.css` the same way.

Re-running `build_assets.py` removes a board's old tiles before writing the new ones. It copies the résumé from the export folder only when `assets/` has none; if the two PDFs differ it keeps the one in `assets/` and prints a warning.

Covers are made at 1800, 1200, 720 and 360 px wide (360 is for the index thumbnails).

Some boards open on a crop of the project's cover, which the page already shows just above the board. For those, the `PROJECTS` list in `tools/build_assets.py` gives the width of that opening panel (in px at the 1440 px board height), the manifest records it as `start`, and the page opens the strip just past it, on new material; the panel stays one "Previous" away. Re-check the number if a board is exported again.

`assets/work/vega/overview-142.webp` (the low-resolution Vega overview) was placed by hand; `build_assets.py` doesn't make or delete it. Keep it until Vega's full board is added.

## Add Vega's board

Vega Group's full board ("Vega Group Project.png") isn't in the source folder yet, so the site shows its cover, a low-resolution overview and a "Request the Vega Group case study" link. To make Vega a full case:

1. Add `Vega Group Project.png` to the "Final Portfolio" folder.
2. Run `python3 tools/build_assets.py "/path/to/Final Portfolio" assets`.
3. Run `python3 tools/build_site.py`.

Vega's section then uses the same board strip as the others, and its status changes from "Preview · full board on request" to "Full board", in the index too.

To add a new project, give it an entry in `content.json` and a row in the `PROJECTS` list at the top of `tools/build_assets.py` (slug, board file, cover file, cover panel), then run both scripts. Until it has that row, `build_site.py` stops with "… is in content.json but not in assets/manifest.json".

## Share image and site address

`assets/og-image.jpg` (1200 × 630) is used for link previews. It's a screenshot of `tools/og-render.html`, which the build makes from `src/og.html`, `content.json` (name, role, studio, place, tagline, the projects in order) and `src/themes.json` (each project's colour). Make it again whenever any of those change:

1. Run `python3 tools/build_site.py`.
2. Open `tools/og-render.html` in a browser at exactly 1200 × 630 (a headless browser screenshot is easiest) and save the screenshot as a PNG. Screenshots are PNG files, not JPEG.
3. Convert it with Pillow:

   ```sh
   python3 -c "from PIL import Image; Image.open('og.png').convert('RGB').save('assets/og-image.jpg', quality=88)"
   ```

Once the site has a public address, set it in `content.json`:

```json
"site": { "url": "https://example.com", ... }
```

and rebuild. The build then adds the canonical link and `og:url`, and makes the share image and JSON-LD image addresses absolute (link previews need that). Until then the build prints a reminder.

`404.html` works at any missing address either way: its styles and images are inside the page, and its links start from the site root (`/`, or `site.url` when it is set). If the site lives in a sub-folder (a GitHub Pages project site such as `user.github.io/portfolio/`), set `site.url` so the 404 page links back to the right place.

## Deploy

Upload the folder to any static host. Everything the site needs is in `index.html`, `404.html` and `assets/`. You don't need to upload `src/`, `tools/`, `content.json`, `README.md` or `NEXT-STEPS.md`, but uploading them does no harm.

- **Netlify:** drag the folder onto app.netlify.com/drop. `404.html` is picked up automatically.
- **GitHub Pages:** push the folder to a repository and turn on Pages for the branch. `404.html` is used automatically.
- **Vercel:** import the repository as a static project with no build command and the project root as the output folder.

## Accessibility and motion

- All text meets WCAG AA contrast in every palette, in light and dark mode, at phone and desktop widths. The build refuses theme colours below AA.
- "Pause motion" (in the hero and the footer) stops the turning marks and smooth scrolling. The choice is remembered on that device. Motion starts paused if the system asks for reduced motion.
- Boards can be used with the keyboard. Tab to a board, use the arrow keys (or Home / End) to move, and press Enter to see the tile in view at full size. In the viewer, the arrow keys move between tiles and Esc closes it.
- The page is complete without JavaScript. Boards still scroll, and each tile links to its full-size image.
- It holds up under user text spacing (WCAG 1.4.12): the header pills wrap and the wordmark scales to fit. In Windows High Contrast mode the focus rings switch to system colours and the palettes keep their real colours.
- DM Mono and the Devanagari greeting load from Google Fonts without blocking the first paint; system fonts stand in until they arrive.

## Content notes

- **Résumé date:** the résumé PDF dates the FrozeHive role "January 2012 – January 2013". That looks like a typo, because university was 2021–2025. Fix it in the source Google Doc, export the PDF again and put it in both `assets/Roshan_Bharti_Resume.pdf` and the "Final Portfolio" folder. (`build_assets.py` never overwrites the copy in `assets/`, but keeping both the same avoids its warning.)
- **Vega board:** the full Vega Group board is missing from the source exports (see "Add Vega's board" above). Its palette is labelled "sampled from the cover" until the brand guidelines are available.
- **Cover descriptions:** the five `cover_alt` texts in `content.json` were drafted while building the site (they describe each cover and quote the line printed on it). They are awaiting Roshan's approval; edit them like any other copy.
