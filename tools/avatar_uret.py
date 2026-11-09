"""DSP bot avatarlarini (SVG) uretir: python tools/avatar_uret.py -> img/*.svg"""
import math
from pathlib import Path

P, L, A, G = "#d6b15a", "#f6e7b8", "#c9a6ff", "#a36dff"   # karışım paleti

def frame(uid):
    studs = "".join(f'<rect x="{256+223*math.cos(math.radians(i*45-90))-6:.1f}" y="{256+223*math.sin(math.radians(i*45-90))-6:.1f}" width="12" height="12" fill="{P}" transform="rotate(45 {256+223*math.cos(math.radians(i*45-90)):.1f} {256+223*math.sin(math.radians(i*45-90)):.1f})"/>' for i in range(8))
    ticks = "".join(f'<line x1="{256+200*math.cos(math.radians(i*7.5)):.1f}" y1="{256+200*math.sin(math.radians(i*7.5)):.1f}" x2="{256+(206 if i%2 else 210)*math.cos(math.radians(i*7.5)):.1f}" y2="{256+(206 if i%2 else 210)*math.sin(math.radians(i*7.5)):.1f}" stroke="{P}" stroke-width="1.4" opacity=".55"/>' for i in range(48))
    return f'''<defs>
 <radialGradient id="bg{uid}" cx="50%" cy="45%" r="70%"><stop offset="0" stop-color="#2a1448"/><stop offset="1" stop-color="#050308"/></radialGradient>
 <linearGradient id="gold{uid}" x1="0" y1="0" x2="0" y2="1"><stop offset="0" stop-color="#fff6dc"/><stop offset=".45" stop-color="{L}"/><stop offset="1" stop-color="{P}"/></linearGradient>
 <linearGradient id="void{uid}" x1="0" y1="0" x2="0" y2="1"><stop offset="0" stop-color="#ffffff"/><stop offset=".4" stop-color="{A}"/><stop offset="1" stop-color="{G}"/></linearGradient>
 <filter id="glow{uid}" x="-50%" y="-50%" width="200%" height="200%"><feGaussianBlur stdDeviation="6" result="b"/><feFlood flood-color="{G}" flood-opacity=".95"/><feComposite in2="b" operator="in" result="g"/><feMerge><feMergeNode in="g"/><feMergeNode in="SourceGraphic"/></feMerge></filter>
 <filter id="soft{uid}" x="-50%" y="-50%" width="200%" height="200%"><feGaussianBlur stdDeviation="22"/></filter>
</defs>
<rect width="512" height="512" fill="url(#bg{uid})"/>
<circle cx="256" cy="256" r="130" fill="{G}" opacity=".30" filter="url(#soft{uid})"/>
<circle cx="256" cy="256" r="232" fill="none" stroke="{P}" stroke-width="3.5"/>
<circle cx="256" cy="256" r="214" fill="none" stroke="{P}" stroke-width="1.2" opacity=".6"/>{ticks}{studs}'''

def sym(name, u):
    gold, void, glow = f"url(#gold{u})", f"url(#void{u})", f"url(#glow{u})"
    if name == "pano":
        return f'''<path d="M256 82 L380 256 L256 430 L132 256 Z" fill="none" stroke="{P}" stroke-width="4"/>
<path d="M256 114 L356 256 L256 398 L156 256 Z" fill="none" stroke="{L}" stroke-width="1.4" opacity=".7"/>
<path d="M244 292 C200 286 166 254 150 208 C178 244 212 262 246 266 Z" fill="{P}"/><path d="M268 292 C312 286 346 254 362 208 C334 244 300 262 266 266 Z" fill="{P}"/>
<path d="M244 320 C214 322 190 308 176 286 C200 302 222 306 246 304 Z" fill="{P}" opacity=".6"/><path d="M268 320 C298 322 322 308 336 286 C312 302 290 306 266 304 Z" fill="{P}" opacity=".6"/>
<g filter="{glow}"><path d="M256 132 C272 184 286 222 270 276 L263 366 L256 384 L249 366 L242 276 C226 222 240 184 256 132 Z" fill="{gold}"/>
<rect x="224" y="284" width="64" height="7" rx="3" fill="{L}"/><circle cx="256" cy="287.5" r="8" fill="{A}"/></g>'''
    if name == "baro":
        return f'''<circle cx="256" cy="256" r="118" fill="none" stroke="{P}" stroke-width="2" opacity=".5" stroke-dasharray="4 10"/>
<rect x="176" y="128" width="160" height="16" rx="6" fill="{gold}"/><rect x="176" y="368" width="160" height="16" rx="6" fill="{gold}"/>
<path d="M196 144 L316 144 C316 200 270 230 262 256 C270 282 316 312 316 368 L196 368 C196 312 242 282 250 256 C242 230 196 200 196 144 Z" fill="none" stroke="{L}" stroke-width="5"/>
<g filter="{glow}"><path d="M214 166 L298 166 C292 200 266 222 256 244 C246 222 220 200 214 166 Z" fill="{void}" opacity=".9"/>
<path d="M256 268 L256 330" stroke="{A}" stroke-width="4" stroke-dasharray="3 7"/><path d="M206 360 C220 324 292 324 306 360 Z" fill="{void}"/></g>
<circle cx="350" cy="350" r="40" fill="#1a0f2a" stroke="{P}" stroke-width="4"/><circle cx="350" cy="350" r="30" fill="none" stroke="{L}" stroke-width="2"/>
<path d="M350 330 L362 350 L350 370 L338 350 Z" fill="{gold}"/>'''
    if name == "sortie":
        blade = lambda rot: f'''<g transform="rotate({rot} 256 256)"><path d="M256 96 L270 130 L266 316 L256 334 L246 316 L242 130 Z" fill="{gold}"/>
<rect x="216" y="316" width="80" height="12" rx="5" fill="{P}"/><rect x="249" y="328" width="14" height="52" rx="4" fill="{P}"/><circle cx="256" cy="388" r="11" fill="{L}"/></g>'''
        return f'''<circle cx="256" cy="256" r="120" fill="none" stroke="{P}" stroke-width="3"/><circle cx="256" cy="256" r="80" fill="none" stroke="{L}" stroke-width="1.5" opacity=".6"/>
<path d="M256 120 V150 M256 362 V392 M120 256 H150 M362 256 H392" stroke="{P}" stroke-width="4"/>
<g filter="{glow}">{blade(-40)}{blade(40)}</g><circle cx="256" cy="256" r="12" fill="{A}" filter="{glow}"/>'''
    if name == "fissure":
        return f'''<g filter="{glow}"><path d="M256 92 L332 172 L312 352 L256 420 L200 352 L180 172 Z" fill="{void}" opacity=".85"/>
<path d="M256 92 L256 420 M180 172 L256 236 L332 172 M200 352 L256 300 L312 352" stroke="#ffffff" stroke-width="2" opacity=".55" fill="none"/></g>
<path d="M256 92 L332 172 L312 352 L256 420 L200 352 L180 172 Z" fill="none" stroke="{L}" stroke-width="5"/>
<path d="M236 120 L262 196 L238 250 L276 318 L250 396" fill="none" stroke="#fff6dc" stroke-width="5" filter="{glow}"/>
<path d="M150 160 L170 168 M342 160 L362 152 M140 300 L176 296 M336 300 L372 308" stroke="{P}" stroke-width="4"/>'''
    if name == "signal":
        arcs = "".join(f'<path d="M{300+i*28} {196-i*24} A{60+i*34} {60+i*34} 0 0 1 {300+i*28} {316+i*24}" fill="none" stroke="{P if i else L}" stroke-width="{6-i}" opacity="{1-i*.2}"/>' for i in range(3))
        return f'''<g filter="{glow}"><path d="M262 140 A120 120 0 1 0 262 372 A92 92 0 1 1 262 140 Z" fill="{gold}"/></g>
{arcs}<circle cx="300" cy="256" r="12" fill="{A}" filter="{glow}"/>
<path d="M300 268 L282 384 M300 268 L318 384 M288 340 H312" stroke="{P}" stroke-width="5" fill="none"/>'''
    if name == "haber":
        lines = "".join(f'<rect x="196" y="{210+i*34}" width="{120 if i%2 else 104}" height="9" rx="4" fill="{P}" opacity=".85"/>' for i in range(4))
        return f'''<path d="M176 140 H306 L346 180 V380 H176 Z" fill="#1a0f2a" stroke="{L}" stroke-width="5"/><path d="M306 140 V180 H346" fill="none" stroke="{L}" stroke-width="5"/>
<rect x="196" y="164" width="88" height="22" rx="6" fill="{gold}"/>{lines}
<g filter="{glow}"><circle cx="352" cy="352" r="12" fill="{A}"/>
<path d="M372 316 A44 44 0 0 1 388 360" fill="none" stroke="{A}" stroke-width="6"/><path d="M386 290 A76 76 0 0 1 414 366" fill="none" stroke="{A}" stroke-width="5" opacity=".75"/></g>'''

NAMES = ["pano", "baro", "sortie", "fissure", "signal", "haber"]

if __name__ == "__main__":
    out = Path(__file__).resolve().parent.parent / "img"
    out.mkdir(exist_ok=True)
    for n in NAMES:
        svg = f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 512 512" width="512" height="512">{frame(n)}{sym(n, n)}</svg>'
        (out / f"{n}.svg").write_text(svg)
        print("yazildi:", n)
