"""Draw docs/img/production_flow.svg, the overview figure in the README.
Run from the repo root: python3 docs/img/make_production_flow.py docs/img/production_flow.svg
Positions are set by hand; text widths are estimates, so check the result in a browser after edits."""
import math
import sys

OUT = sys.argv[1]
W, H = 1000, 684
SANS = "Helvetica, Arial, sans-serif"
MONO = "SFMono-Regular, Menlo, Consolas, 'DejaVu Sans Mono', monospace"
INK, MUTED = "#1f2328", "#57606a"
STAGE = {1: "#6b4fbb", 2: "#a65a1f", 3: "#1f6fb2", 4: "#2a7f4f"}   # GENIE, anniedirt, WCSim, toolchain
out = []
add = out.append


def text(x, y, s, size=13, fill=INK, weight="normal", anchor="start", family=SANS, style="normal"):
    add('<text x="%.1f" y="%.1f" font-family="%s" font-size="%s" fill="%s" font-weight="%s" text-anchor="%s"'
        ' font-style="%s">%s</text>' % (x, y, family, size, fill, weight, anchor, style, s))


def badge(cx, cy, n, r=9.5):
    add('<circle cx="%.1f" cy="%.1f" r="%s" fill="%s"/>' % (cx, cy, r, STAGE[n]))
    text(cx, cy + 4.5, str(n), 12.5, "#ffffff", "bold", "middle")


def pill(x, y, n, label, width):
    add('<rect x="%.1f" y="%.1f" width="%.1f" height="24" rx="12" fill="#ffffff" fill-opacity="0.95" '
        'stroke="%s" stroke-width="1.5"/>' % (x, y, width, STAGE[n]))
    badge(x + 13, y + 12, n, 8.5)
    text(x + 27, y + 16.5, label, 13, STAGE[n], "bold")


def chip(x, y, label):
    w = 7.4 * len(label) + 20
    add('<rect x="%.1f" y="%.1f" width="%.1f" height="24" rx="12" fill="#ffffff" stroke="#8c959f"/>' % (x, y, w))
    text(x + w / 2, y + 16.5, label, 12, INK, "normal", "middle", MONO)
    return w


def arrow(x1, y, x2, color="#8c959f"):
    add('<line x1="%.1f" y1="%.1f" x2="%.1f" y2="%.1f" stroke="%s" stroke-width="1.6"/>' % (x1, y, x2 - 5, y, color))
    add('<path d="M%.1f,%.1f l-6,-4 v8 z" fill="%s"/>' % (x2, y, color))


add('<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 %d %d" width="%d" height="%d" role="img" '
    'aria-labelledby="t d">' % (W, H, W, H))
add('<title id="t">ANNIE MC production: GENIE, anniedirt, WCSim, MC toolchain</title>')
add('<desc id="d">Side view along the beam. A BNB neutrino interacts in the rock (GENIE); Geant4 carries the '
    'outgoing muon through the rock to the tank (anniedirt); the detector response in the FMV, tank and MRD is '
    'simulated (WCSim); ToolAnalysis turns the hits into ntuples (MC toolchain). Below: the output file of each '
    'stage and the mcprod steps used to run each stage.</desc>')
add('<!-- Made by docs/img/make_production_flow.py: edit that and rerun. Opaque background for dark mode. -->')
add('<defs>'
    '<pattern id="rock" width="14" height="14" patternUnits="userSpaceOnUse">'
    '<rect width="14" height="14" fill="#e9dcc6"/><circle cx="3" cy="4" r="1.3" fill="#c9b18c"/>'
    '<circle cx="10" cy="10" r="1.1" fill="#d2bd9b"/></pattern>'
    '<clipPath id="tankbody"><rect x="515" y="150" width="130" height="150"/></clipPath>'
    '</defs>')
add('<rect x="0.5" y="0.5" width="%d" height="%d" rx="14" fill="#fbfaf6" stroke="#dcd6c8"/>' % (W - 1, H - 1))
text(24, 36, "ANNIE MC production: one neutrino, four stages", 21, INK, "bold")
text(24, 58, "Side view along the beam, not to scale. Every run N goes through all four stages, "
     "one grid job per run and stage.", 13, MUTED)

# ---- the scene: rock with the hall cut out (FMV, tank, MRD) ----------------------------------------------
RX0, RX1, RY0, RY1 = 170, 776, 104, 348          # rock (world volume dirt)
HX0, HX1, HFLOOR = 458, 764, 318                 # hall cavity, open at the top
add('<rect x="%d" y="%d" width="%d" height="%d" fill="url(#rock)" stroke="#b39b74"/>' % (RX0, RY0, RX1 - RX0, RY1 - RY0))
add('<rect x="%d" y="%d" width="%d" height="%d" fill="#f4f6f8" stroke="#b39b74"/>' % (HX0, RY0, HX1 - HX0, HFLOOR - RY0))
add('<line x1="%d" y1="%d" x2="%d" y2="%d" stroke="#fbfaf6" stroke-width="2"/>' % (HX0 + 1, RY0, HX1 - 1, RY0))
text(RX0 + 4, RY0 - 6, "upstream dirt face, Z = −10 m", 11.5, "#7a6442")
text(RX0 + 8, RY1 - 9, "rock", 12, "#6e5a3a", style="italic")

# FMV paddles
for x in (488, 496):
    add('<rect x="%d" y="160" width="5" height="136" fill="#f0c36b" stroke="#b58a2e" stroke-width="0.8"/>' % x)
# tank: side view of the vertical cylinder
add('<path d="M515,150 L515,300 A65,11 0 0 0 645,300 L645,150 Z" fill="#d6eaf8" stroke="#4f7391" stroke-width="2"/>')
# Cherenkov cone of the muon (41 degrees in water), clipped to the tank
mu = (330, 222, 726, 262)
slope = (mu[3] - mu[1]) / (mu[2] - mu[0])
ax, ay = 517, mu[1] + (517 - mu[0]) * slope
th = math.atan(slope)
up, dn = math.tan(th - math.radians(41)), math.tan(th + math.radians(41))
add('<polygon points="%.1f,%.1f %.1f,%.1f %.1f,%.1f" fill="#3d9be0" fill-opacity="0.22" clip-path="url(#tankbody)"/>'
    % (ax, ay, 645, ay + 128 * up, 645, ay + 128 * dn))
add('<ellipse cx="580" cy="150" rx="65" ry="11" fill="#e8f4fc" stroke="#4f7391" stroke-width="2"/>')
for y in range(170, 290, 22):                    # PMTs on the side walls
    for x in (523, 637):
        add('<circle cx="%d" cy="%d" r="3.2" fill="#2b2f33"/>' % (x, y))
for x in range(547, 620, 22):                    # PMTs on the floor
    add('<circle cx="%d" cy="294" r="3.2" fill="#2b2f33"/>' % x)
for y in (180, 244):                             # LAPPDs (downstream side)
    add('<rect x="625" y="%d" width="7" height="18" fill="#e3b23c" stroke="#9a7417" stroke-width="0.8"/>' % y)
# MRD: iron + scintillator layers
for i in range(10):
    x = 672 + 8 * i
    add('<rect x="%d" y="168" width="4.5" height="124" fill="#8d969e"/>' % x)
    add('<rect x="%.1f" y="168" width="3" height="124" fill="#f0c36b"/>' % (x + 4.5))
for x, label in ((493, "FMV"), (580, "tank"), (712, "MRD")):
    text(x, 336, label, 12, "#3d3020", "bold", "middle")

# ---- the neutrino and its interaction ---------------------------------------------------------------------
add('<line x1="24" y1="222" x2="318" y2="222" stroke="%s" stroke-width="2" stroke-dasharray="7 5"/>' % STAGE[1])
add('<path d="M160,222 l-9,-5 v10 z" fill="%s"/>' % STAGE[1])
add('<text x="30" y="212" font-family="%s" font-size="19" fill="%s" font-weight="bold">ν<tspan font-size="12" '
    'dy="4">μ</tspan></text>' % (SANS, STAGE[1]))
text(24, 246, "from the BNB", 12, MUTED)
text(24, 262, "gsimple_flux_N.root", 11.5, MUTED, family=MONO)
add('<line x1="%d" y1="%d" x2="%d" y2="%d" stroke="%s" stroke-width="2.4" stroke-linecap="round"/>' % (mu + (INK,)))
text(440, 224, "μ", 15, INK, "bold")
add('<line x1="330" y1="222" x2="366" y2="198" stroke="#a65a1f" stroke-width="3.2" stroke-linecap="round"/>')
text(370, 197, "p", 13, "#a65a1f", "bold")
add('<line x1="330" y1="222" x2="392" y2="254" stroke="#57606a" stroke-width="1.6" stroke-dasharray="2 3"/>')
text(397, 262, "n", 13, MUTED, "bold")
star = []
for k in range(10):
    r = 10.5 if k % 2 == 0 else 4.4
    a = math.radians(-90 + 36 * k)
    star.append("%.1f,%.1f" % (330 + r * math.cos(a), 222 + r * math.sin(a)))
add('<polygon points="%s" fill="%s" stroke="#ffffff" stroke-width="1.2"/>' % (" ".join(star), STAGE[1]))

# stage call-outs on the scene
pill(236, 142, 1, "GENIE: interaction", 168)
add('<line x1="330" y1="166" x2="330" y2="209" stroke="%s" stroke-width="1.3"/>' % STAGE[1])
pill(214, 280, 2, "anniedirt: through the rock", 228)
add('<line x1="420" y1="280" x2="420" y2="236" stroke="%s" stroke-width="1.3"/>' % STAGE[2])
pill(505, 112, 3, "WCSim: detector response", 210)

# ToolAnalysis panel
PX0, PX1 = 800, 978
arrow(767, 212, PX0 - 2, STAGE[4])
add('<rect x="%d" y="%d" width="%d" height="%d" rx="10" fill="#eef6f1" stroke="%s" stroke-width="1.5"/>'
    % (PX0, RY0, PX1 - PX0, RY1 - RY0, STAGE[4]))
badge(PX0 + 20, RY0 + 22, 4)
text(PX0 + 36, RY0 + 27, "MC toolchain", 14, STAGE[4], "bold")
text(PX0 + 16, RY0 + 50, "ToolAnalysis", 12.5, MUTED)
for i, label in enumerate(("hits", "clusters", "reconstruction", "ntuple trees")):
    y = RY0 + 82 + 40 * i
    add('<rect x="%d" y="%d" width="%d" height="26" rx="6" fill="#ffffff" stroke="#9cc5ad"/>' % (PX0 + 16, y, 146))
    text(PX0 + 89, y + 17.5, label, 12.5, INK, "normal", "middle")
    if i < 3:
        add('<path d="M%d,%d l-5,-7 h10 z" fill="%s"/>' % (PX0 + 89, y + 39, STAGE[4]))

# ---- one card per stage -------------------------------------------------------------------------------------
CARDS = [
    (1, "GENIE", "gevgen_fnal",
     ["Where each neutrino interacts", "(rock, hall or tank) and what", "comes out"],
     ["gntp.N.ghep.root"], "+ gst file, POT per run"),
    (2, "anniedirt", "Geant4",
     ["Carries the outgoing particles", "through the rock; keeps those", "that reach the tank"],
     ["annie_tank_flux.N.root"], ""),
    (3, "WCSim", "Geant4",
     ["Detector response: Cherenkov", "light, PMT and LAPPD hits,", "FMV and MRD hits"],
     ["wcsim_N.root", "+ wcsim_lappd_N.root"], ""),
    (4, "MC toolchain", "ToolAnalysis",
     ["Your toolchain: clustering,", "reconstruction, then the tree", "maker (PhaseIITreeMaker)"],
     ["MC_N.root"], "the analysis ntuples"),
]
CY, CH, CW, GAP = 368, 132, 226, 18
for i, (n, name, tool, lines, files, note) in enumerate(CARDS):
    x = 20 + i * (CW + GAP)
    add('<rect x="%d" y="%d" width="%d" height="%d" rx="9" fill="#ffffff" stroke="%s" stroke-width="1.5"/>'
        % (x, CY, CW, CH, STAGE[n]))
    add('<path d="M%d,%d h%d a9,9 0 0 1 9,9 v19 h-%d v-19 a9,9 0 0 1 9,-9 z" fill="%s"/>'
        % (x + 9, CY, CW - 18, CW, STAGE[n]))
    text(x + 12, CY + 19, "%d  %s" % (n, name), 14, "#ffffff", "bold")
    text(x + CW - 10, CY + 19, tool, 11.5, "#ffffff", "normal", "end")
    for k, line in enumerate(lines):
        text(x + 12, CY + 46 + 16 * k, line, 12.5)
    for k, f in enumerate(files):
        text(x + 12, CY + 102 + 15 * k, f, 11.5, STAGE[n], "bold", family=MONO)
    if note:
        text(x + 12, CY + 119, note, 11.5, MUTED)
    if i < 3:
        arrow(x + CW + 2, CY + CH / 2, x + CW + GAP - 1)

# ---- running it ------------------------------------------------------------------------------------------------
text(24, 532, "Running it with ./mcprod", 15, INK, "bold")
ROWS = [
    ("Test chain", 548, [("submit --test", "10 jobs"), ("validate", "GREEN / YELLOW / RED"),
                         ("estimate", "resources into the YAML")],
     "stages 1 → 4, ten runs each"),
    ("Full production", 604, [("submit", "all runs"), ("status", "progress, failures"),
                              ("submit --missing", "recovery, to ≥ 95 %"), ("verify + purge", "toolchain only"),
                              ("copy", "to persistent + POT")],
     "one stage at a time"),
]
for label, y, steps, trail in ROWS:
    text(24, y + 17, label, 13.5, INK, "bold")
    x = 150
    for k, (cmd, sub) in enumerate(steps):
        slot = max(7.4 * len(cmd) + 20, 5.9 * len(sub) + 6)      # room for the caption under the chip
        w = chip(x + (slot - 7.4 * len(cmd) - 20) / 2, y, cmd)
        text(x + slot / 2, y + 38, sub, 11, MUTED, "normal", "middle")
        x += slot
        if k < len(steps) - 1:
            arrow(x + 4, y + 12, x + 22)
            x += 26
    text(x + 16, y + 17, trail, 12.5, MUTED, style="italic")
text(24, H - 14, "mcprod starts a stage (test or full) only when the stage before it is DONE. Details: docs/workflow.md",
     12.5, MUTED, style="italic")
add('</svg>')
with open(OUT, "w") as handle:
    handle.write("\n".join(out) + "\n")
