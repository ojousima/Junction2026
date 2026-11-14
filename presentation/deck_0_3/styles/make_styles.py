"""Generate three visual styles of deck 0.3. Content stays identical; only CSS and SVG colours change."""
import re, pathlib

ROOT = pathlib.Path(__file__).resolve().parent.parent
src = (ROOT / 'index.html').read_text()
head, rest = src.split('<style>', 1)
_, body = rest.split('</style>', 1)

# Original stylesheet with every colour turned into a token.
BASE = r"""
  * { box-sizing: border-box; margin: 0; padding: 0; }
  html, body { height: 100%; background: var(--outer); color: var(--text); font-family: var(--font-body); }
  body { overflow: hidden; }
  #stage { position: absolute; left: 50%; top: 50%; width: 1280px; height: 720px; transform-origin: center center; }
  .slide { position: absolute; inset: 0; background: var(--bg); padding: 64px 80px 52px;
    display: none; flex-direction: column; overflow: hidden; }
  .slide.active { display: flex; }
  .kicker { font-size: 15px; letter-spacing: .18em; text-transform: uppercase; color: var(--green); font-weight: 600; margin-bottom: 14px; }
  h1 { font-family: var(--font-head); font-size: 88px; line-height: 1.05; font-weight: 750; letter-spacing: -.02em; }
  h2 { font-family: var(--font-head); font-size: 46px; line-height: 1.1; font-weight: 720; letter-spacing: -.015em; margin-bottom: 36px; }
  h3 { font-size: 22px; font-weight: 650; margin-bottom: 14px; }
  p { font-size: 20px; line-height: 1.4; color: var(--muted); }
  strong { color: var(--text); font-weight: 650; }
  .foot { margin-top: auto; padding-top: 14px; font-size: 12.5px; color: var(--dim); line-height: 1.45; }
  .num { position: absolute; right: 36px; bottom: 22px; font-size: 13px; color: var(--dim); }
  .grid { display: grid; gap: 24px; }
  .g2 { grid-template-columns: 1fr 1fr; } .g3 { grid-template-columns: repeat(3, 1fr); } .g4 { grid-template-columns: repeat(4, 1fr); }
  .card { background: var(--panel); border: 1px solid var(--line); border-radius: var(--radius); padding: 26px 28px; }
  .stat { font-family: var(--font-stat); font-size: 54px; font-weight: 750; letter-spacing: -.02em; line-height: 1; }
  .stat small { font-size: 24px; font-weight: 600; color: var(--muted); }
  .label { margin-top: 12px; font-size: 17px; line-height: 1.35; color: var(--muted); }
  .list { display: flex; flex-direction: column; gap: 14px; }
  .list div { font-size: 21px; color: var(--text); display: flex; gap: 14px; align-items: baseline; }
  .list div::before { content: ""; flex: none; width: 9px; height: 9px; border-radius: var(--bullet-radius); background: var(--green); transform: translateY(-3px); }
  .list span { color: var(--muted); }
  .list div.sub-note { font-size: 16px; color: var(--muted); margin-top: 8px; }
  .list div.sub-note::before { display: none; }
  .title-slide { justify-content: center; }
  .title-slide .tag { font-size: 32px; color: var(--text); margin-top: 28px; max-width: 900px; line-height: 1.3; }
  .pills { margin-top: 48px; }
  .pill { display: inline-block; border: 1px solid var(--line); border-radius: 999px; padding: 7px 15px;
    margin-right: 8px; font-size: 15px; color: var(--muted); background: var(--panel); }
  .faults { display: grid; grid-template-columns: repeat(4, 1fr); gap: 24px; margin-top: 30px; }
  .fault { border-top: 3px solid var(--warn); padding-top: 14px; font-size: 20px; font-weight: 650; }
  .fault span { display: block; font-size: 16px; font-weight: 400; color: var(--muted); margin-top: 4px; }
  .impact { display: grid; grid-template-columns: 1fr 1.4fr; gap: 26px; flex: 1; min-height: 0; }
  .money h3, .money .stat { color: var(--warn); }
  .money .row + .row { margin-top: 26px; }
  .env { border-color: color-mix(in srgb, var(--green) 45%, transparent);
    background: linear-gradient(160deg, color-mix(in srgb, var(--green) 10%, transparent), var(--panel) 55%); }
  .env h3 { color: var(--green); }
  .env-row { display: grid; grid-template-columns: 150px 1fr; gap: 18px; align-items: center; padding: 14px 0; border-top: 1px solid var(--line); }
  .env-row:first-of-type { border-top: 0; padding-top: 2px; }
  .env-row .big { font-family: var(--font-stat); font-size: 32px; font-weight: 750; line-height: 1; }
  .env-row p { font-size: 19px; color: var(--text); }
  .sol { display: grid; grid-template-columns: 1.2fr 1fr; gap: 48px; flex: 1; align-items: center; }
  .sol svg { width: 100%; height: auto; }
  .diag .card { display: flex; flex-direction: column; gap: 6px; }
  .diag .icon { width: 52px; height: 52px; border-radius: 12px; display: grid; place-items: center; margin-bottom: 12px; }
  .diag .sensor { font-size: 14px; letter-spacing: .1em; text-transform: uppercase; font-weight: 650; }
  .diag h3 { font-size: 26px; margin-bottom: 18px; }
  .diag .list div { font-size: 20px; }
  .t .sensor, .t .icon svg { color: var(--warn); } .t .icon { background: color-mix(in srgb, var(--warn) 12%, transparent); } .t .list div::before { background: var(--warn); }
  .a .sensor, .a .icon svg { color: var(--green); } .a .icon { background: color-mix(in srgb, var(--green) 12%, transparent); }
  .ui .card { display: flex; flex-direction: column; gap: 18px; }
  .ui-head { display: flex; align-items: center; gap: 12px; }
  .ui-head h3 { margin: 0; }
  .badge { font-size: 13px; font-weight: 650; letter-spacing: .06em; text-transform: uppercase; padding: 5px 10px; border-radius: 6px; white-space: nowrap; }
  .b-green { background: color-mix(in srgb, var(--green) 14%, transparent); color: var(--green); }
  .b-ice { background: color-mix(in srgb, var(--ice) 14%, transparent); color: var(--ice); }
  .notif { background: var(--inset); border: 1px solid var(--inset-line); border-radius: 12px; padding: 12px 16px; }
  .notif-top { font-size: 13px; color: var(--muted); display: flex; align-items: center; gap: 7px; }
  .dot { width: 8px; height: 8px; border-radius: 50%; background: var(--warn); }
  .notif-title { font-size: 17px; font-weight: 650; margin-top: 4px; }
  .notif-body { font-size: 15px; color: var(--muted); }
  .rows { background: var(--inset); border: 1px solid var(--inset-line); border-radius: 12px; padding: 8px 16px; }
  .rows div { display: flex; justify-content: space-between; font-size: 16px; padding: 7px 0; color: var(--muted); }
  .rows div + div { border-top: 1px solid var(--inset-line); }
  .rows b { font-weight: 650; } .ok { color: var(--green); } .watch { color: var(--warn); }
  .one { font-size: 18px; color: var(--muted); }
  .ui h2 { margin-bottom: 22px; }
  .ui .card { gap: 12px; padding: 20px 24px; }
  .pair { display: flex; gap: 14px; align-items: center; font-size: 15.5px; line-height: 1.35; color: var(--muted); }
  .pair svg { width: 40px; height: 40px; flex: none; color: var(--text); }
  .pair b { color: var(--text); }
  .ui .rows div { padding: 5px 0; }
  .trust { display: flex; align-items: center; gap: 10px; margin-top: 18px; }
  .trust div { flex: 1; background: var(--panel); border: 1px solid var(--line); border-radius: var(--radius-sm); padding: 10px 14px; }
  .trust div.aiven { flex: 1.7; border-color: color-mix(in srgb, var(--ice) 50%, transparent); }
  .trust b { display: block; font-size: 16px; }
  .trust span { display: block; font-size: 13.5px; line-height: 1.3; color: var(--muted); margin-top: 2px; }
  .trust i { width: 18px; height: 2px; background: var(--neutral-bar); position: relative; flex: none; }
  .trust i::after { content: ""; position: absolute; right: -2px; top: -4px; border: 5px solid transparent; border-left-color: var(--neutral-bar); }
  .cra { margin-top: 12px; font-size: 14.5px; color: var(--muted); }
  .cra b { color: var(--green); font-size: 12.5px; letter-spacing: .08em; text-transform: uppercase; margin-right: 8px; }
  .biz h2 { margin-bottom: 28px; }
  .tbl { width: 100%; border-collapse: collapse; font-size: 18px; color: var(--muted); }
  .tbl td { padding: 9px 0; border-top: 1px solid var(--line); }
  .tbl tr:first-child td { border-top: 0; }
  .tbl td:last-child { text-align: right; color: var(--text); font-variant-numeric: tabular-nums; }
  .tbl tr.total td { color: var(--text); font-weight: 700; border-top: 1px solid var(--strong-line); }
  .tbl tr.total td:last-child { color: var(--warn); }
  .wf { display: flex; flex-direction: column; gap: 12px; }
  .wf-row { display: grid; grid-template-columns: 170px 1fr 64px; gap: 12px; align-items: center; font-size: 17px; color: var(--muted); }
  .wf-row b { text-align: right; color: var(--text); font-variant-numeric: tabular-nums; }
  .bar { height: 18px; background: var(--track); border-radius: 4px; overflow: hidden; display: flex; }
  .bar i { display: block; height: 100%; background: var(--neutral-bar); border-radius: 4px; }
  .wf-row.neg .bar i { background: color-mix(in srgb, var(--bad) 70%, transparent); } .wf-row.neg b { color: var(--bad); }
  .wf-row.rev .bar i { background: var(--ice); }
  .wf-row.gp .bar i { background: var(--green); } .wf-row.gp, .wf-row.gp b { color: var(--green); font-weight: 700; }
  .duo { display: grid; grid-template-columns: 1fr 1fr; gap: 14px; margin-top: 24px; }
  .duo div { background: var(--track); border: 1px solid var(--line); border-radius: 12px; padding: 14px 16px; font-size: 15px; color: var(--muted); }
  .duo b { display: block; font-family: var(--font-stat); font-size: 30px; color: var(--green); margin-top: 2px; }
  .value { display: grid; grid-template-columns: 1fr 1fr 1.35fr; gap: 14px; margin-top: 16px; }
  .value div { background: var(--panel); border: 1px solid var(--line); border-radius: var(--radius-sm); padding: 10px 16px; }
  .value span { display: block; font-size: 13.5px; color: var(--muted); line-height: 1.3; }
  .value b { display: block; font-family: var(--font-stat); font-size: 24px; letter-spacing: -.01em; margin: 1px 0 2px; }
  .value .us { border-color: color-mix(in srgb, var(--green) 55%, transparent);
    background: linear-gradient(160deg, color-mix(in srgb, var(--green) 12%, transparent), var(--panel) 60%); }
  .value .us b { color: var(--green); }
  .biz h2 { margin-bottom: 20px; }
  .biz .card { padding: 18px 24px; }
  .biz h3 { margin-bottom: 8px; }
  .biz .tbl { font-size: 17px; } .biz .tbl td { padding: 5px 0; }
  .biz .wf { gap: 8px; }
  .biz .duo { margin-top: 14px; } .biz .duo div { padding: 9px 14px; } .biz .duo b { font-size: 26px; }
  .plan { width: 100%; border-collapse: collapse; font-variant-numeric: tabular-nums; }
  .plan td { padding: 13px 0 13px 12px; text-align: right; font-size: 21px; border-top: 1px solid var(--line); }
  .plan td:first-child { text-align: left; padding-left: 0; color: var(--muted); font-size: 18px; }
  .plan tr.head td { border-top: 0; color: var(--green); font-weight: 700; font-size: 19px; }
  .plan tr.head small { display: block; font-size: 13px; color: var(--dim); font-weight: 500; }
  .plan small.pct { display: block; font-size: 13px; color: var(--dim); }
  .plan tr.profit td { font-weight: 750; color: var(--green); border-top: 1px solid var(--strong-line); }
  .plan tr.profit td:first-child { color: var(--text); }
  .plan td.neg { color: var(--bad) !important; }
  .steps { display: flex; flex-direction: column; gap: 16px; }
  .steps div { font-size: 17px; color: var(--muted); }
  .steps b { display: block; color: var(--text); font-size: 19px; }
  .pro { border-color: color-mix(in srgb, var(--ice) 40%, transparent); }
  .pro h3 { font-size: 19px; margin: 12px 0 8px; }
  .wave { width: 100%; height: 56px; display: block; }
  .wave-labels { display: flex; justify-content: space-between; font-size: 14px; color: var(--dim); margin: 4px 0 26px; }
  .wave-labels span:last-child { color: var(--warn); }
  .pillars .card { padding: 22px 26px; }
  .pk { font-size: 14px; letter-spacing: .1em; text-transform: uppercase; font-weight: 650; margin-bottom: 10px; }
  .p-money .pk, .p-money .stat { color: var(--warn); }
  .p-env { border-color: color-mix(in srgb, var(--green) 45%, transparent); } .p-env .pk, .p-env .stat { color: var(--green); }
  .p-people .pk, .p-people .stat { color: var(--ice); }
  .banner { margin-top: 22px; font-size: 24px; color: var(--muted); }
  .banner b { color: var(--text); }
  .sense h2 { margin-bottom: 30px; }
  .sense-grid { display: grid; grid-template-columns: 1.25fr 1fr; gap: 40px; flex: 1; min-height: 0; align-items: center; }
  .sense-grid svg { width: 100%; height: auto; display: block; }
  .steps3 { display: flex; flex-direction: column; gap: 22px; }
  .steps3 div { font-size: 18px; color: var(--muted); border-left: 3px solid var(--line); padding-left: 16px; }
  .steps3 b { display: block; font-size: 22px; color: var(--text); margin-bottom: 2px; }
  .steps3 div:last-child { border-left-color: var(--green); }
  .pipe { display: flex; align-items: center; gap: 10px; margin-bottom: 28px; }
  .pipe div { flex: 1; background: var(--panel); border: 1px solid var(--line); border-radius: var(--radius-sm); padding: 14px 16px; font-size: 19px; font-weight: 650; }
  .pipe div:last-child { border-color: color-mix(in srgb, var(--green) 50%, transparent); }
  .pipe span { display: block; font-size: 14px; font-weight: 400; color: var(--muted); margin-top: 2px; }
  .pipe i { width: 18px; height: 2px; background: var(--neutral-bar); position: relative; flex: none; }
  .pipe i::after { content: ""; position: absolute; right: -2px; top: -4px; border: 5px solid transparent; border-left-color: var(--neutral-bar); }
  .sigs .card { display: flex; flex-direction: column; gap: 4px; padding: 20px 22px; }
  .sigs svg { width: 100%; height: 64px; margin-bottom: 10px; }
  .sigs b { font-size: 20px; } .sigs span { font-size: 16px; color: var(--muted); }
  .note { margin-top: 22px; font-size: 17px; color: var(--muted); }
  .crew .card { padding: 16px 16px 20px; display: flex; flex-direction: column; }
  .crew img { display: block; width: 100%; height: 270px; object-fit: cover; object-position: center 25%; border-radius: var(--radius-sm); }
  .crew b { font-size: 26px; margin: 14px 4px 0; }
  .crew span { font-size: 14px; letter-spacing: .1em; text-transform: uppercase; font-weight: 650; color: var(--green); margin: 4px 4px 0; }
  #hint { position: fixed; left: 16px; bottom: 12px; font-size: 12px; color: var(--dim); }
  @media print {
    @page { size: 1280px 720px; margin: 0; }
    html, body { background: var(--bg); overflow: visible; }
    #stage { position: static; transform: none !important; }
    .slide { position: relative; display: flex !important; width: 1280px; height: 720px; page-break-after: always; break-after: page; }
    #hint { display: none; }
  }
"""

# Original hard-coded SVG / inline colours, by role.
ROLES = {
    '#5fd38d': 'green', '#8fd3ff': 'ice', '#ffb454': 'warn', '#ff6b6b': 'bad',
    '#9fb3a9': 'muted', '#6f857a': 'dim', '#eef4f0': 'text', '#0d1512': 'bg',
    '#1b2a24': 'fin_bg', '#3a5146': 'fin_line', '#2c3d35': 'ground', '#1f2e28': 'unit',
    '#4a6257': 'unit_line', '#16221d': 'fan_bg', '#33473e': 'ring', '#3d5449': 'blade',
    '#5c7469': 'hub', '#123a26': 'box',
    'rgba(95,211,141,.12)': 'green_soft', 'rgba(255,180,84,.14)': 'warn_soft',
}

THEMES = {
  'nordic': dict(
    title='Nordic paper',
    vars=dict(bg='#f6f3ec', outer='#e8e3d7', panel='#ffffff', line='#e1dbcd', text='#1c2420', muted='#58635c',
              dim='#8b938c', green='#2e7d50', ice='#2a6f9e', warn='#bf6a10', bad='#c0392b', inset='#f6f3ec',
              inset_line='#e4dfd2', track='#f1ede4', neutral_bar='#b9b4a6', strong_line='#c9c2b2'),
    svg=dict(fin_bg='#efeadf', fin_line='#a7a99c', ground='#cfc8b8', unit='#ece7dc', unit_line='#8f978d', fan_bg='#f9f7f2',
             ring='#d7d1c3', blade='#bdb8aa', hub='#8f978d', box='#e3f1e8', green_soft='rgba(46,125,80,.12)',
             warn_soft='rgba(191,106,16,.14)'),
    fonts=dict(head='"Iowan Old Style", "Palatino Linotype", Palatino, Georgia, serif',
               body='-apple-system, BlinkMacSystemFont, "Segoe UI", Inter, Roboto, Helvetica, Arial, sans-serif',
               stat='"Iowan Old Style", "Palatino Linotype", Palatino, Georgia, serif'),
    radius='6px', radius_sm='6px', bullet='50%',
    css=r"""
  h1 { font-weight: 600; letter-spacing: -.01em; font-size: 96px; }
  h2 { font-weight: 600; letter-spacing: -.005em; }
  .stat, .env-row .big, .duo b { font-weight: 600; letter-spacing: -.01em; }
  .card { box-shadow: 0 1px 2px rgba(60,50,30,.06), 0 8px 24px rgba(60,50,30,.05); }
  .kicker { display: flex; align-items: center; gap: 12px; letter-spacing: .14em; font-size: 13px; }
  .kicker::before { content: ""; width: 28px; height: 1px; background: currentColor; }
  .title-slide { background: var(--bg); }
  .title-slide::after { content: ""; position: absolute; right: 80px; top: 64px; bottom: 52px; width: 1px; background: var(--line); }
  .title-slide .tag { font-family: var(--font-head); font-style: italic; font-size: 34px; max-width: 860px; color: var(--muted); }
  .pill { background: transparent; }
  .foot { border-top: 1px solid var(--line); }
""",
  ),
  'blueprint': dict(
    title='Blueprint',
    vars=dict(bg='#0a1c33', outer='#050f1d', panel='rgba(16,42,72,.72)', line='#24476f', text='#e8f1ff', muted='#9db5d3',
              dim='#6787ab', green='#46e0a0', ice='#6fd0ff', warn='#ffc35a', bad='#ff7d7d', inset='#0c2340',
              inset_line='#24476f', track='#081629', neutral_bar='#3b6797', strong_line='#3b6797'),
    svg=dict(fin_bg='#0f2a48', fin_line='#4f81b6', ground='#3b6797', unit='#0e2744', unit_line='#7fb0e0', fan_bg='#0b2139',
             ring='#2c5585', blade='#2a5a8c', hub='#7fb0e0', box='#0d3a35', green_soft='rgba(70,224,160,.12)',
             warn_soft='rgba(255,195,90,.14)'),
    fonts=dict(head='-apple-system, BlinkMacSystemFont, "Segoe UI", Inter, Roboto, Helvetica, Arial, sans-serif',
               body='-apple-system, BlinkMacSystemFont, "Segoe UI", Inter, Roboto, Helvetica, Arial, sans-serif',
               stat='ui-monospace, "SF Mono", Menlo, Consolas, monospace'),
    radius='2px', radius_sm='2px', bullet='0',
    css=r"""
  .slide { background:
      linear-gradient(rgba(111,208,255,.06) 1px, transparent 1px) 0 0 / 40px 40px,
      linear-gradient(90deg, rgba(111,208,255,.06) 1px, transparent 1px) 0 0 / 40px 40px,
      linear-gradient(rgba(111,208,255,.03) 1px, transparent 1px) 0 0 / 8px 8px,
      linear-gradient(90deg, rgba(111,208,255,.03) 1px, transparent 1px) 0 0 / 8px 8px,
      var(--bg); }
  .slide::before { content: ""; position: absolute; inset: 22px; border: 1px solid rgba(111,208,255,.18); pointer-events: none; }
  .kicker, .pk, .diag .sensor, .badge, .foot, .num, .wave-labels, .pill, .plan small, .pipe span
    { font-family: ui-monospace, "SF Mono", Menlo, Consolas, monospace; }
  .kicker { letter-spacing: .08em; font-size: 14px; }
  .kicker::before { content: "// "; opacity: .6; }
  .num::before { content: "SHEET "; opacity: .6; }
  h1 { font-weight: 700; letter-spacing: -.03em; }
  h2 { font-weight: 650; letter-spacing: -.02em; }
  .stat { font-weight: 600; letter-spacing: -.04em; font-size: 50px; }
  .card { position: relative; backdrop-filter: blur(1px); }
  .card::after { content: ""; position: absolute; left: -1px; top: -1px; width: 12px; height: 12px;
    border-left: 2px solid var(--ice); border-top: 2px solid var(--ice); }
  .title-slide { background:
      radial-gradient(circle at 82% 45%, rgba(111,208,255,.14), transparent 40%),
      linear-gradient(rgba(111,208,255,.07) 1px, transparent 1px) 0 0 / 40px 40px,
      linear-gradient(90deg, rgba(111,208,255,.07) 1px, transparent 1px) 0 0 / 40px 40px, var(--bg); }
  .title-slide .tag { color: var(--muted); }
  .pill { border-radius: 2px; background: transparent; color: var(--ice); border-color: color-mix(in srgb, var(--ice) 40%, transparent); }
  .notif, .rows, .duo div { border-radius: 2px; }
  .env-row .big { font-family: var(--font-head); font-weight: 700; letter-spacing: -.02em; }
""",
  ),
  'signal': dict(
    title='Signal',
    vars=dict(bg='#ffffff', outer='#d9d9d6', panel='#f3f3f0', line='#d6d6d2', text='#0b0b0b', muted='#4d4d4d',
              dim='#8a8a86', green='#00995a', ice='#0a6fd6', warn='#ff5a1f', bad='#e01e1e', inset='#ffffff',
              inset_line='#d6d6d2', track='#ebebe7', neutral_bar='#0b0b0b', strong_line='#0b0b0b'),
    svg=dict(fin_bg='#ffffff', fin_line='#0b0b0b', ground='#0b0b0b', unit='#f3f3f0', unit_line='#0b0b0b', fan_bg='#ffffff',
             ring='#cfcfcb', blade='#0b0b0b', hub='#0b0b0b', box='#e5f5ed', green_soft='rgba(0,153,90,.12)',
             warn_soft='rgba(255,90,31,.16)'),
    fonts=dict(head='"Helvetica Neue", Helvetica, Arial, sans-serif',
               body='"Helvetica Neue", Helvetica, Arial, sans-serif',
               stat='"Helvetica Neue", Helvetica, Arial, sans-serif'),
    radius='0', radius_sm='0', bullet='0',
    css=r"""
  h1 { font-size: 124px; font-weight: 800; letter-spacing: -.045em; line-height: .95; }
  h2 { font-size: 54px; font-weight: 800; letter-spacing: -.035em; line-height: 1.02; }
  h3 { font-weight: 800; letter-spacing: -.01em; }
  .stat { font-weight: 800; letter-spacing: -.05em; font-size: 60px; }
  .stat small { letter-spacing: 0; margin-left: 6px; }
  .kicker { align-self: flex-start; background: var(--text); color: #fff; padding: 6px 10px 5px; letter-spacing: .12em; font-size: 13px; font-weight: 700; }
  .card { background: transparent; border: 0; border-top: 4px solid var(--text); padding: 18px 0 0; }
  .card .card { border-top-width: 2px; }
  .ui .card, .biz .card, .pro, .steps { padding-right: 4px; }
  .env, .pro, .p-env { background: transparent; border-top-color: var(--text); }
  .p-money { border-top-color: var(--warn); } .p-env { border-top-color: var(--green); } .p-people { border-top-color: var(--ice); }
  .money { border-top-color: var(--warn); } .env { border-top-color: var(--green); }
  .t { border-top-color: var(--warn); } .a { border-top-color: var(--green); }
  .fault { border-top-width: 4px; }
  .sense-grid > .card { border-top: 0; padding: 0; }
  .sigs .card { padding: 14px 0 0; }
  .pipe div, .trust div, .value div { background: transparent; border: 2px solid var(--text); }
  .value .us { background: var(--green); border-color: var(--green); } .value .us b, .value .us span { color: #fff; }
  .trust div.aiven { border-color: var(--ice); }
  .pipe div:last-child { background: var(--text); color: #fff; border-color: var(--text); }
  .pipe div:last-child span { color: #cfcfcf; }
  .title-slide { background: linear-gradient(90deg, var(--bg) 64%, var(--warn) 64%); }
  .title-slide h1, .title-slide .tag { max-width: 700px; }
  .title-slide .tag { font-size: 30px; font-weight: 500; letter-spacing: -.01em; }
  .title-slide::after { content: ""; position: absolute; right: 120px; top: 50%; width: 220px; height: 220px; margin-top: -110px;
    border-radius: 50%; border: 18px solid #fff; box-shadow: 0 0 0 40px var(--warn), 0 0 0 58px #fff; }
  .pill { border-radius: 0; background: transparent; border: 2px solid var(--text); color: var(--text); font-weight: 600; }
  .badge { border-radius: 0; }
  .duo div { border-radius: 0; border: 0; background: var(--panel); }
  .notif, .rows { border-radius: 0; }
  #hint { display: none; }
  .crew .card { padding: 0; border-top: 0; }
  .banner { font-size: 26px; color: var(--text); } .banner b { background: var(--warn); color: #fff; padding: 0 6px; }
""",
  ),
}

for key, t in THEMES.items():
    v = {**t['vars'], **t['svg']}
    tokens = '\n'.join(f'    --{k.replace("_", "-")}: {val};' for k, val in t['vars'].items())
    root = (f":root {{\n{tokens}\n    --font-head: {t['fonts']['head']};\n    --font-body: {t['fonts']['body']};\n"
            f"    --font-stat: {t['fonts']['stat']};\n    --radius: {t['radius']}; --radius-sm: {t['radius_sm']};"
            f" --bullet-radius: {t['bullet']};\n  }}")
    pattern = re.compile('|'.join(re.escape(c) for c in ROLES))
    new_body = pattern.sub(lambda m: v[ROLES[m.group(0)]], body)
    new_body = new_body.replace('src="img/', 'src="../img/')
    html = head.replace('<title>Heat Pump Doctor</title>', f'<title>Heat Pump Doctor · {t["title"]}</title>')
    html += f'<style>\n  /* Style: {t["title"]}. Generated from ../index.html. */\n  {root}\n{BASE}{t["css"]}</style>{new_body}'
    out = ROOT / 'styles' / f'{key}.html'
    out.write_text(html)
    print(out, len(html))
