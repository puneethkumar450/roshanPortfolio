#!/usr/bin/env python3
"""Generate Roshan Bharti's portfolio site.

Reads  content.json          every word about Roshan and his clients
       assets/manifest.json  image sizes and board tiles (written by tools/build_assets.py)
       src/                  page.html, project.html, board-strip.html, board-preview.html,
                             404.html, styles.css, main.js, themes.json
Writes index.html, 404.html, assets/site.css, assets/site.js, and tools/og-render.html
       (the page that is screenshotted for assets/og-image.jpg, see README.md)

Python 3 standard library only. Running it twice gives byte-identical output.

    python3 tools/build_site.py

All five projects render from the one template in src/project.html. The board block is
src/board-strip.html when the manifest has a board for the project, and
src/board-preview.html when it is null (Vega today), so adding Vega's board and re-running
tools/build_assets.py and this script turns Vega into a full case automatically.
"""
import base64
import hashlib
import html
import json
import re
import struct
import sys
import urllib.parse
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SRC = ROOT / 'src'
ASSETS = ROOT / 'assets'

# The header's pill colours (--chrome-bg in src/styles.css, light and dark). Each project's dot in
# the now-showing pill is measured against both, and gets a firmer ring where it would vanish.
CHROME_LIGHT, CHROME_DARK = '#E9DFCA', '#2A2A2B'
DOT_MIN_CONTRAST = 1.6


# ---------------------------------------------------------------- helpers

def esc(value):
    return html.escape(str(value), quote=True)


TOKEN = re.compile(r'\{\{(!?)([a-z_][a-z0-9_]*)\}\}')


def render(template, ctx, where):
    """{{key}} inserts ctx[key] HTML-escaped, {{!key}} inserts it raw. Unknown keys stop the build."""
    missing = set()

    def rep(m):
        raw, key = m.group(1), m.group(2)
        if key not in ctx:
            missing.add(key)
            return m.group(0)
        return str(ctx[key]) if raw else esc(ctx[key])

    out = TOKEN.sub(rep, template)
    if missing:
        sys.exit(f'build_site: {where} uses unknown placeholders: {", ".join(sorted(missing))}')
    return out


def read(path):
    return path.read_text(encoding='utf-8')


def hex_rgb(h):
    h = h.lstrip('#')
    return tuple(int(h[i:i + 2], 16) for i in (0, 2, 4))


def luminance(h):
    def lin(c):
        c /= 255
        return c / 12.92 if c <= 0.04045 else ((c + 0.055) / 1.055) ** 2.4
    r, g, b = hex_rgb(h)
    return 0.2126 * lin(r) + 0.7152 * lin(g) + 0.0722 * lin(b)


def contrast(a, b):
    la, lb = sorted((luminance(a), luminance(b)), reverse=True)
    return (la + 0.05) / (lb + 0.05)


def webp_size(path):
    """Width and height of a WebP file, read from its header (VP8, VP8L or VP8X)."""
    b = path.read_bytes()[:40]
    if b[:4] != b'RIFF' or b[8:12] != b'WEBP':
        raise ValueError(f'{path} is not a WebP file')
    kind = b[12:16]
    if kind == b'VP8X':
        return 1 + int.from_bytes(b[24:27], 'little'), 1 + int.from_bytes(b[27:30], 'little')
    if kind == b'VP8 ':
        w, h = struct.unpack('<HH', b[26:30])
        return w & 0x3FFF, h & 0x3FFF
    if kind == b'VP8L':
        bits = int.from_bytes(b[21:25], 'little')
        return (bits & 0x3FFF) + 1, ((bits >> 14) & 0x3FFF) + 1
    raise ValueError(f'{path}: unknown WebP chunk {kind!r}')


def num(n):
    return f'{n:,}'


def rgba(hex_, alpha):
    r, g, b = hex_rgb(hex_)
    return f'rgba({r},{g},{b},{alpha})'


def strip_sizes(css):
    """The `sizes` for board tiles, read from the --strip-h rules in styles.css so the two can't drift.
    Returns a function of the tile's aspect ratio (width / height)."""
    desk = re.search(r'--strip-h:\s*round\(down,\s*(clamp\([^()]*\)),\s*3px\);\s*\}\s*/\*\s*strip: desktop', css)
    phone = re.search(r'@media\s*([^{}]+?)\s*\{\s*:root\s*\{\s*--strip-h:\s*round\(down,\s*(clamp\([^()]*\)),\s*3px\);'
                      r'\s*\}\s*/\*\s*strip: phone', css)
    if not desk or not phone:
        sys.exit('build_site: could not find the "strip: desktop" / "strip: phone" --strip-h rules in src/styles.css')
    return lambda r: f'{phone.group(1)} calc({phone.group(2)} * {r:.4f}), calc({desk.group(1)} * {r:.4f})'


# ---------------------------------------------------------------- themes

# Every project name is set in its section's ink (fg), never in a client's logo colour, so a
# theme has no separate title colour.
THEME_KEYS = ('bg', 'fg', 'mut', 'line', 'stage', 'stage_fg', 'stage_mut', 'stage_line', 'thumb')


def derive_theme(project):
    """A safe theme for a project that has no entry in src/themes.json: the first palette colour
    that takes near-black, black or white text at 4.5:1, else a neutral dark ground."""
    bg, fg = '#1A1A1A', '#F6F2EA'
    for c in project['palette']:
        ok = [f for f in ('#1A1A1A', '#000000', '#FFFFFF') if contrast(c['hex'], f) >= 4.5]
        if ok:
            bg, fg = c['hex'], ok[0]
            break
    others = [c['hex'] for c in project['palette'] if c['hex'] != bg]
    thumb = others[0] if others else '#F6F2EA'
    return {'bg': bg, 'fg': fg, 'mut': fg, 'line': rgba(fg, .34),
            'stage': '#1A1A1A', 'stage_fg': '#F6F2EA', 'stage_mut': '#BDB8AE',
            'stage_line': 'rgba(246,242,234,.18)', 'thumb': thumb}


def check_theme(slug, t):
    rules = [('fg', 'bg', 4.5), ('mut', 'bg', 4.5),
             ('stage_fg', 'stage', 4.5), ('stage_mut', 'stage', 4.5)]
    problems = []
    for a, b, need in rules:
        r = contrast(t[a], t[b])
        if r < need:
            problems.append(f'{slug}: {a} {t[a]} on {b} {t[b]} is {r:.2f}:1, needs {need}:1')
    return problems


# ---------------------------------------------------------------- parts

ARROW_OUT = ('<svg viewBox="0 0 14 14" aria-hidden="true"><path d="M3.5 10.5l7-7M4.5 3.5h6v6" '
             'fill="none" stroke="currentColor" stroke-width="1.5"/></svg>')


STILL_SET = 'assets/mark/mark-static-160.png 160w, assets/mark/mark-static-512.png 512w'
ANIM_SET = 'assets/mark/mark-320.webp 320w, assets/mark/mark-512.webp 512w'


def mark_picture(sizes, extra_img_attrs='', deferred=False):
    """The turning head. The first <source> (the still PNG) answers prefers-reduced-motion without
    JS; main.js points it at the Pause motion toggle. The animation is picked by rendered size and
    pixel density: phones and 1x desktops get the 320 px file, 2x desktops the 512 px one.
    deferred: the <img> starts on the front-facing still (40 KB, not 260-435 KB) and main.js swaps
    in the animation (data-anim-srcset, which starts on that same frame) once the page has loaded."""
    img_set = STILL_SET if deferred else ANIM_SET
    img_src = 'assets/mark/mark-static-512.png' if deferred else 'assets/mark/mark-512.webp'
    anim = f' data-anim-srcset="{ANIM_SET}"' if deferred else ''
    return ('<picture>'
            '<source data-still media="(prefers-reduced-motion: reduce)" '
            f'srcset="{STILL_SET}" sizes="{sizes}">'
            f'<img src="{img_src}" srcset="{img_set}"{anim} '
            f'sizes="{sizes}" width="512" height="512" alt=""{extra_img_attrs}>'
            '</picture>')


def css_values(css, selector, prop):
    """Every value of `prop` in rules whose selector list contains `selector`, as
    [(max-width of the enclosing @media or None, value)]. Lets `sizes` attributes follow the
    stylesheet instead of copies of its numbers."""
    css = re.sub(r'/\*.*?\*/', '', css, flags=re.S)
    found, stack, buf = [], [], ''
    for ch in css:
        if ch == '{':
            stack.append(buf.strip())
            buf = ''
        elif ch == '}':
            prelude = stack.pop() if stack else ''
            if not prelude.startswith('@') and selector in [x.strip() for x in prelude.split(',')]:
                for decl in buf.split(';'):
                    name, _, value = decl.partition(':')
                    if name.strip() == prop:
                        widths = [int(w) for at in stack for w in re.findall(r'max-width:\s*(\d+)px', at)]
                        found.append((min(widths) if widths else None, value.strip()))
            buf = ''
        else:
            buf += ch
    return found


def sizes_from(css, selector, prop, scale=None):
    """A `sizes` list from css_values(): narrowest breakpoint first, the unconditioned value last.
    scale(value) turns a CSS width into the rendered px width (for em-sized marks)."""
    vals = css_values(css, selector, prop)
    default = [v for w, v in vals if w is None]
    if not default:
        sys.exit(f'build_site: no top-level {prop} for {selector} in src/styles.css')
    conv = scale or (lambda v, w: v)
    parts = [f'(max-width: {w}px) {conv(v, w)}' for w, v in sorted((w, v) for w, v in vals if w is not None)]
    return ', '.join(parts + [conv(default[-1], None)])


def wm_k(css, var):
    m = re.search(r'--' + var + r':\s*([0-9.]+)', css)
    if not m:
        sys.exit(f'build_site: --{var} not found in src/styles.css')
    return float(m.group(1))


def status_of(board):
    return ('Full board', '') if board else ('Preview · full board on request', ' dot--open')


def status_html(text):
    """The status label; 'full board on request' is kept on one line, so where the label has to
    wrap it breaks after 'Preview ·', never inside the phrase."""
    head, sep, tail = text.partition(' · ')
    return f'{esc(head)} · <span class="nw">{esc(tail)}</span>' if sep else esc(text)


def joined(items):
    """'A · B · C' that only breaks after a separator, so a wrapped line never starts with '·'."""
    parts = [esc(x) for x in items]
    return ' '.join(f'<span class="nw">{x}&nbsp;·</span>' for x in parts[:-1]) + \
        (' ' if len(parts) > 1 else '') + (f'<span class="nw">{parts[-1]}</span>' if parts else '')


def build_tiles(slug, board, sizes_for):
    d = f'assets/work/{slug}'
    n = len(board['tiles'])
    tiles, ticks = [], []
    for i, t in enumerate(board['tiles']):
        w, h = t['w'], t['h']
        base = f'{d}/{t["src"]}'
        half = ASSETS / 'work' / slug / f'{t["src"]}-720.webp'
        hw, hh = webp_size(half)
        if (hw, hh) != (w // 2, h // 2):
            sys.exit(f'build_site: {half} is {hw}x{hh}, expected {w // 2}x{h // 2}')
        sizes = sizes_for(w / h)
        tiles.append(
            f'              <a class="tile" href="{base}-1440.webp" style="--w:{w}" '
            f'aria-label="Tile {i + 1:02d} of {n:02d}, full size">'
            f'<img src="{base}-720.webp" srcset="{base}-720.webp {hw}w, {base}-1440.webp {w}w" sizes="{sizes}" '
            f'width="{w}" height="{h}" loading="lazy" decoding="async" draggable="false" alt=""></a>')
        ticks.append(f'<span style="flex-grow:{w}"><b>{i + 1:02d}</b></span>')
    return '\n'.join(tiles), ''.join(ticks)


def build_board(p, board, email, sizes_for):
    slug, name = p['slug'], p['name']
    if board:
        tiles, ticks = build_tiles(slug, board, sizes_for)
        start = int(board.get('start') or 0)
        return render(read(SRC / 'board-strip.html'), {
            'start_attr': f' data-start="{start}"' if start else '',
            'slug': slug, 'name': name, 'count': len(board['tiles']),
            'tiles': tiles, 'ticks': ticks, 'board_alt': p.get('board_alt', f'{name} brand presentation.'),
            'board_w': num(board['width']), 'board_h': num(board['height']),
        }, 'board-strip.html')

    # Board not available yet: honest preview, built from a low-res overview if there is one.
    overview = sorted((ASSETS / 'work' / slug).glob('overview-*.webp'))
    if overview:
        ov = overview[0]
        ow, oh = webp_size(ov)
        url = f'assets/work/{slug}/{ov.name}'
        # Lazy <img> windows onto the overview (CSS shifts each row along), so it loads only when near.
        rows = '\n'.join(
            f'                <span class="sheet-row"><img src="{url}" width="{ow}" height="{oh}" loading="lazy" '
            f'decoding="async" alt=""></span>' for _ in range(4))
        alt = p.get('board_alt', f'{name} brand presentation.')
        box_style = f' style="max-width:{round(ow / 2 * 1.2)}px"'
        sheet = (
            f'          <figure class="sheet">\n'
            f'            <div class="sheet-rows" role="img" aria-label="{esc(alt)} Low-resolution overview of the whole board.">\n'
            f'{rows}\n'
            f'            </div>\n'
            f'            <figcaption class="board-cap mono">Fig. — the whole {esc(name)} board at preview resolution, '
            f'{num(ow)} × {num(oh)} px, cut into rows.</figcaption>\n'
            f'          </figure>')
        note, shown = f'Preview resolution · {num(ow)} × {num(oh)} px', 'Cover and low-res overview'
    else:
        sheet, note, shown, box_style = '', 'Preview', 'Cover', ''
    return render(read(SRC / 'board-preview.html'), {
        'slug': slug, 'name': name, 'sheet': sheet, 'preview_note': note, 'shown': shown, 'box_style': box_style,
        'email': email, 'subject_q': urllib.parse.quote(f'{name} case study'),
    }, 'board-preview.html')


def idea_html(text):
    """The idea as a pull-quote. Each sentence is kept whole (lines break only between sentences);
    the quote marks ride on the first and last sentence so they never sit alone."""
    parts = [x for x in re.split(r'(?<=[.!?])\s+', text.strip().strip('“”"')) if x]
    if len(parts) < 2:
        return f'“{esc(parts[0] if parts else "")}”'
    parts[0], parts[-1] = '“' + parts[0], parts[-1] + '”'
    return ' '.join(f'<span class="s">{esc(x)}</span>' for x in parts)


def build_project(i, p, total, manifest, theme, email, sizes_for):
    slug = p['slug']
    m = manifest['projects'][slug]
    board = m.get('board')
    cover = m['cover']
    status, dot_mod = status_of(board)
    t = theme
    css_vars = (f'--bg:{t["bg"]};--fg:{t["fg"]};--mut:{t["mut"]};--line:{t["line"]};'
                f'--st-bg:{t["stage"]};--st-fg:{t["stage_fg"]};--st-mut:{t["stage_mut"]};'
                f'--st-line:{t["stage_line"]};--thumb:{t["thumb"]}')
    chips = []
    for c in p['palette']:
        r, g, b = hex_rgb(c['hex'])
        chips.append(
            f'            <li><button type="button" class="chip" data-hex="{esc(c["hex"])}">'
            f'<span class="chip-c" style="background:{esc(c["hex"])}"></span>'
            f'<span class="chip-n"><span class="sr-only">Copy </span>{esc(c["name"])}</span>'
            f'<span class="chip-v">{esc(c["hex"].upper())}</span><span class="chip-v">RGB {r} {g} {b}</span></button></li>')
    n_col = len(p['palette'])
    note = f'{n_col} colour{"s" if n_col != 1 else ""}'
    if p.get('palette_source'):
        note += f', {p["palette_source"]}'
    deliverables = '\n'.join(f'              <li>{esc(x)}</li>' for x in p['deliverables'])
    return render(read(SRC / 'project.html'), {
        'slug': slug, 'name': p['name'], 'no': p['no'], 'total': f'{total:02d}',
        'side': ' proj--r' if i % 2 else '', 'vars': css_vars,
        'sector': p['sector'], 'disciplines': joined(p['disciplines']),
        'status': status_html(status), 'dot_mod': dot_mod, 'headline': p['headline'],
        'dir': f'assets/work/{slug}', 'cover_w': cover['width'], 'cover_h': cover['height'],
        'cover_avg': cover.get('avg', t['bg']), 'cover_alt': p.get('cover_alt', f'{p["name"]} — cover image.'),
        'palette_note': note, 'chips': '\n'.join(chips),
        'challenge': p['challenge'], 'approach': p['approach'], 'idea': idea_html(p['idea']),
        'deliverables': deliverables, 'board': build_board(p, board, email, sizes_for),
    }, f'project.html ({slug})')


def build_index_row(p, manifest, theme, thumb_sizes):
    slug = p['slug']
    m = manifest['projects'][slug]
    status, dot_mod = status_of(m.get('board'))
    cw, ch = webp_size(ASSETS / 'work' / slug / 'cover-720.webp')
    sw_, _ = webp_size(ASSETS / 'work' / slug / 'cover-360.webp')
    sw = ''.join(f'<i style="background:{esc(c["hex"])}"></i>' for c in p['palette'])
    return (f'        <li><a href="#{slug}" style="--rbg:{theme["bg"]};--rfg:{theme["fg"]}">\n'
            f'          <span class="idx-no">{esc(p["no"])}</span>\n'
            f'          <span class="idx-name">{esc(p["name"])}</span>\n'
            f'          <span class="idx-meta"><b>{esc(p["sector"])}</b><span class="idx-disc mut">{joined(p["disciplines"])}</span></span>\n'
            f'          <span class="idx-sw" aria-hidden="true">{sw}</span>\n'
            f'          <span class="idx-status"><i class="dot{dot_mod}" aria-hidden="true"></i><span>{status_html(status)}</span></span>\n'
            f'          <span class="idx-cover"><img src="assets/work/{slug}/cover-720.webp" '
            f'srcset="assets/work/{slug}/cover-360.webp {sw_}w, assets/work/{slug}/cover-720.webp {cw}w" sizes="{thumb_sizes}" '
            f'width="{cw}" height="{ch}" '
            f'loading="lazy" decoding="async" style="background:{esc(m["cover"].get("avg", theme["bg"]))}" alt=""></span>\n'
            f'        </a></li>')


def emphasise(text, phrase):
    """Wrap `phrase` (the end of `text`, from content.json) in <em>, shown in Signal Blue. Stops the
    build if the copy and the phrase disagree. No no-break spaces: the headings use text-wrap:
    balance against a lone last word, and a glued phrase would overflow under user text spacing."""
    if not phrase:
        return esc(text)
    i = text.rfind(phrase)
    if i < 0:
        sys.exit(f'build_site: emphasis "{phrase}" is not in "{text}" (content.json)')
    head, tail = text[:i], text[i:]
    return esc(head) + f'<em>{esc(tail)}</em>'


def plural(n, word):
    return f'{n} {word}{"" if n == 1 else "s"}'


def seq_dot(slug, colour):
    """One dot of the now-showing pill, flagged where it would melt into the light or dark pill."""
    cls = ' '.join(c for c, ground in (('lo-l', CHROME_LIGHT), ('lo-d', CHROME_DARK))
                   if contrast(colour, ground) < DOT_MIN_CONTRAST)
    cls_attr = f' class="{cls}"' if cls else ''
    return f'<i data-k="{slug}"{cls_attr} style="--c:{colour}"></i>'


def hero_mark_sizes(css):
    """Rendered width of the hero mark, read from src/styles.css: the wordmark's font size is the
    measure (100vw less two --gut) / --wm-k, and the mark is .wm-mark's width in em of that."""
    ks = {w: float(v) for w, v in css_values(css, '.wordmark', '--wm-k')}
    gut = [v for w, v in css_values(css, ':root', '--gut') if w is None]
    if None not in ks or not gut:
        sys.exit('build_site: expected --wm-k on .wordmark and --gut on :root in src/styles.css')

    def width(v, w):
        em = float(v.rstrip('em'))
        k = ks.get(w, ks[None])
        return f'calc((100vw - 2 * {gut[0]}) * {em / k:.4f})'
    return sizes_from(css, '.wm-mark', 'width', width)


def data_uri(path, mime):
    return f'data:{mime};base64,' + base64.b64encode(path.read_bytes()).decode('ascii')


def not_found_ctx(ctx, css, url, person):
    """404.html is served at whatever address was missing (/work/anything), so it can't point at
    files by relative paths. It carries the site stylesheet inline and the mark as a data URI, and
    links from the site root (site.url when it is set, else '/')."""
    root = f'{url}/' if url else '/'
    font = f'{root}assets/fonts/BricolageGrotesque-var.woff2'
    face = re.search(r'@font-face\s*\{[^}]*\}\s*', css)
    if not face or 'url("fonts/BricolageGrotesque-var.woff2")' not in face.group(0):
        sys.exit('build_site: expected the Bricolage @font-face at the top of src/styles.css')
    return {
        'lang': ctx['lang'], 'name': person['name'], 'year': ctx['year'],
        'font_face': face.group(0).strip().replace('url("fonts/', f'url("{root}assets/fonts/'),
        'font_url': font, 'css': css.replace(face.group(0), '', 1).strip(),
        'mark': data_uri(ASSETS / 'mark' / 'mark-static-512.png', 'image/png'),
        'favicon': data_uri(ASSETS / 'mark' / 'favicon-32.png', 'image/png'),
        'home': root, 'resume': f'{root}{person["resume_pdf"]}',
    }


# ---------------------------------------------------------------- page

def build():
    content = json.loads(read(ROOT / 'content.json'))
    manifest = json.loads(read(ASSETS / 'manifest.json'))
    themes = json.loads(read(SRC / 'themes.json'))
    site, person, about, contact = content['site'], content['person'], content['about'], content['contact']
    projects = content['projects']
    total = len(projects)

    # Themes: use src/themes.json, derive one for any new project, refuse to build below AA.
    theme_of, problems = {}, []
    for p in projects:
        if p['slug'] not in manifest['projects']:
            sys.exit(f'build_site: {p["slug"]} is in content.json but not in assets/manifest.json')
        t = themes.get(p['slug']) or derive_theme(p)
        missing = [k for k in THEME_KEYS if k not in t]
        if missing:
            sys.exit(f'build_site: theme for {p["slug"]} lacks {missing}')
        theme_of[p['slug']] = t
        problems += check_theme(p['slug'], t)
    if problems:
        sys.exit('build_site: contrast below WCAG AA\n  ' + '\n  '.join(problems))

    css = read(SRC / 'styles.css')
    js = read(SRC / 'main.js')
    sizes_for = strip_sizes(css)
    css_v = hashlib.sha1(css.encode()).hexdigest()[:10]
    js_v = hashlib.sha1(js.encode()).hexdigest()[:10]

    first, _, last = person['name'].partition(' ')
    url = (site.get('url') or '').strip().rstrip('/')
    if not url:
        print('note      site.url in content.json is empty: set it before going live, so the share image and '
              'JSON-LD image get absolute addresses and 404.html links back to the right place.')
    og_image = f'{url}/assets/og-image.jpg' if url else 'assets/og-image.jpg'
    mark_img = f'{url}/assets/mark/mark-static-512.png' if url else 'assets/mark/mark-static-512.png'

    jsonld = {
        '@context': 'https://schema.org', '@type': 'Person',
        'name': person['name'], 'jobTitle': person['role'],
        'worksFor': {'@type': 'Organization', 'name': person['studio']},
        'email': f'mailto:{person["email"]}',
        'sameAs': list(person['links'].values()),
        'image': mark_img,
        'description': site['description'],
    }
    if url:
        jsonld['url'] = url + '/'
    jsonld_txt = json.dumps(jsonld, ensure_ascii=False, indent=2).replace('</', '<\\/')

    full = sum(1 for p in projects if manifest['projects'][p['slug']].get('board'))
    previews = total - full
    summary = plural(total, 'project') + ' · ' + plural(full, 'full board')
    if previews:
        summary += ' · ' + plural(previews, 'preview')

    exp = []
    for x in about['experience']:
        exp.append(f'        <li><p class="when">{esc(x["when"])}</p><p class="role">{esc(x["role"])}'
                   f'<span class="org">{esc(x["org"])}</span></p><p class="note">{esc(x["note"])}</p></li>')
    ed, cert = about['education'], about.get('certificate')
    edu = [f'        <li><p class="when">{esc(ed["when"])}</p><p class="role">{esc(ed["degree"])}'
           f'<span class="org">{esc(ed["school"])}</span></p><p class="note">{esc(ed["note"])}</p></li>']
    if cert:
        edu.append(f'        <li><p class="when">{esc(cert["when"])}</p><p class="role">{esc(cert["name"])}'
                   f'<span class="org">{esc(cert["by"])}</span></p></li>')
    tools = '\n'.join(f'        <div><dt>{esc(k)}</dt><dd>{esc(v)}</dd></div>' for k, v in about['toolkit'].items())
    links = '\n'.join(
        f'          <li><a class="btn" href="{esc(href)}" target="_blank" rel="noopener">{esc(label)} {ARROW_OUT}'
        f'<span class="sr-only"> (opens in a new tab)</span></a></li>' for label, href in person['links'].items())

    ctx = {
        'lang': site.get('lang', 'en'), 'title': site['title'], 'description': site['description'],
        'name': person['name'], 'first': first, 'last': last,
        'canonical': f'<link rel="canonical" href="{esc(url)}/">\n' if url else '',
        'og_url': f'<meta property="og:url" content="{esc(url)}/">\n' if url else '',
        'og_image': og_image, 'og_alt': f'{person["name"]} — {person["role"]}',
        'deva_text': urllib.parse.quote(person['greeting']['hi']),
        'css_v': css_v, 'js_v': js_v, 'jsonld': jsonld_txt,
        'seq_dots': ''.join(seq_dot(p['slug'], theme_of[p['slug']]['bg']) for p in projects),
        'resume': person['resume_pdf'],
        'greet_hi': person['greeting']['hi'], 'greet_ja': person['greeting']['ja'],
        'role': person['role'], 'studio': person['studio'], 'studio_short': person['studio'].split(' — ')[0],
        'location': person.get('location_hint', ''), 'since': person['since'],
        'tagline': emphasise(person['tagline'], person.get('tagline_emphasis')),
        'lead': person['lead'], 'lead2': person['lead2'],
        'mark_hero': mark_picture(hero_mark_sizes(css), deferred=True),
        'mark_contact': mark_picture(sizes_from(css, '.contact-mark', 'width'), ' loading="lazy" decoding="async"'),
        'proof': '\n      '.join(f'<li>{esc(x)}</li>' for x in person['proof_points']),
        'range': f'{esc(projects[0]["no"])}<span class="en">–</span>{esc(projects[-1]["no"])}', 'summary': summary,
        'index_rows': '\n'.join(build_index_row(p, manifest, theme_of[p['slug']], sizes_from(css, '.idx a', '--thumb-w'))
                                for p in projects),
        'projects': '\n'.join(build_project(i, p, total, manifest, theme_of[p['slug']], person['email'], sizes_for)
                              for i, p in enumerate(projects)),
        'about_heading': emphasise(about['heading'], about.get('heading_emphasis')),
        'mark_alt': f'{first}’s mark: an illustrated head in {person["brand_colour"]["name"]}, facing front.',
        'about_paras': '\n'.join(f'        <p>{esc(x)}</p>' for x in about['paragraphs']),
        'experience': '\n'.join(exp), 'education': '\n'.join(edu), 'toolkit': tools,
        'contact_heading': contact['heading'], 'contact_body': contact['body'], 'contact_cta': contact['cta'],
        'email': person['email'], 'contact_links': links, 'year': site['year'],
    }
    index_html = render(read(SRC / 'page.html'), ctx, 'page.html')

    nf_html = render(read(SRC / '404.html'), not_found_ctx(ctx, css, url, person), '404.html')
    og_html = render(read(SRC / 'og.html'), {
        'role': person['role'], 'studio': person['studio'], 'location': person.get('location_hint', ''),
        'first': first, 'last': last, 'tagline': ctx['tagline'], 'wm_k': f'{wm_k(css, "wm-k"):g}',
        'covers': '\n'.join(f'    <figure style="--c:{theme_of[p["slug"]]["bg"]}"><img src="../assets/work/{p["slug"]}/cover-720.webp" alt=""></figure>'
                            for p in projects),
    }, 'og.html')

    outputs = {
        ROOT / 'index.html': index_html,
        ROOT / '404.html': nf_html,
        ASSETS / 'site.css': css,
        ASSETS / 'site.js': js,
        ROOT / 'tools' / 'og-render.html': og_html,
    }
    for path, text in outputs.items():
        old = path.read_text(encoding='utf-8') if path.exists() else None
        if old != text:
            path.write_text(text, encoding='utf-8')
            print(f'wrote     {path.relative_to(ROOT)}  ({len(text.encode()):,} bytes)')
        else:
            print(f'unchanged {path.relative_to(ROOT)}')
    check_refs(index_html, 'index.html')
    check_refs(nf_html, '404.html')


REF = re.compile(r'''(?:src|href|data-anim)="([^"]+)"|srcset="([^"]+)"|url\(["\']?([^"\')]+)["\']?\)''')


def check_refs(text, where):
    """Every local file the page points at must exist. Root-relative paths (404.html) are read from ROOT."""
    missing = set()
    for m in REF.finditer(text):
        vals = [m.group(1) or m.group(3)] if (m.group(1) or m.group(3)) else [c.strip().split(' ')[0] for c in m.group(2).split(',')]
        for v in vals:
            path = html.unescape(v).split('#')[0].split('?')[0].lstrip('/')
            if not path or v.startswith(('http:', 'https:', 'mailto:', 'data:', '#')):
                continue
            if not (ROOT / path).exists():
                missing.add(path)
    if missing:
        sys.exit(f'build_site: {where} points at missing files:\n  ' + '\n  '.join(sorted(missing)))


if __name__ == '__main__':
    build()
