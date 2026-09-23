"""Run navigation using the bundled Agent Trace palette and components."""
import json
from pathlib import Path

from .traces import e, safe_path


def run_summary(run: Path) -> dict:
    try:
        value = json.loads(safe_path(run, 'summary.json').read_text())
        return value if isinstance(value, dict) else {}
    except (OSError, ValueError):
        return {}


def listing_page(title: str, subtitle: str, cards: list[str], *, back: bool = False) -> str:
    noun = 'session' if back else 'run'
    count_label = f'{len(cards)} {noun}' + ('' if len(cards) == 1 else 's')
    # Share the actual trace stylesheet rather than maintaining a second palette.
    trace = Path(__file__).with_name('agent-trace.html').read_text(encoding='utf-8')
    style = trace[trace.index('<style>'):trace.index('</style>') + len('</style>')]
    return ('<!doctype html><html lang="en"><head><meta charset="utf-8">'
            '<meta name="viewport" content="width=device-width, initial-scale=1">'
            f'<title>{e(title)} · Agent Trace</title>' + style + '''
<style>
.directory {max-width:1100px; width:100%; margin:0 auto; padding:48px 24px 64px}
.directory h1 {font-size:32px; margin:12px 0 8px; overflow-wrap:anywhere}
.lede {color:var(--text-muted); margin:0 0 28px}
.directory-bar {display:flex; flex-wrap:wrap; align-items:center; gap:16px; margin:28px 0 20px; font-family:var(--sans)}
.directory-bar input {flex:1; min-width:180px; padding:11px 14px; border:1px solid var(--border); border-radius:8px; background:var(--panel); color:var(--text); font:inherit}
.card-grid {display:grid; grid-template-columns:repeat(auto-fit,minmax(min(100%,340px),1fr)); gap:16px}
.run-card {display:block; padding:24px; border:1px solid var(--border); border-radius:12px; background:var(--panel); color:var(--text); overflow-wrap:anywhere}
.run-card:hover {text-decoration:none; border-color:var(--orange)}
.run-card:focus-visible {outline:2px solid var(--orange); outline-offset:3px}
.run-card h2 {font-size:18px; margin:14px 0}
.card-meta {font-family:var(--mono); font-size:12px; color:var(--text-muted); margin:8px 0}
.card-top {display:flex; justify-content:space-between; gap:12px; align-items:center; font:12px var(--sans); color:var(--text-muted)}
.badge {padding:4px 9px; border-radius:20px; background:var(--code-bg); color:var(--text-muted)}
.badge.passed {background:var(--thinking-bg); color:var(--green)}
.badge.failed {background:var(--error-bg); color:var(--error)}
.card-action {display:block; margin-top:22px; color:var(--orange); font:13px var(--sans)}
.empty-state {padding:36px; border:1px dashed var(--border-strong); border-radius:12px; color:var(--text-muted)}
[hidden] {display:none!important}
</style>
<script>
const savedTheme = localStorage.getItem('theme');
document.documentElement.dataset.theme = savedTheme || (matchMedia('(prefers-color-scheme: dark)').matches ? 'dark' : 'light');
</script></head><body>
<header class="site"><a class="brand" href="/">Agent Trace <span class="dot" aria-hidden="true"></span></a>
<span class="spacer"></span><nav><a class="navlink" href="/">All runs</a><button id="theme-toggle" class="theme-toggle" type="button" aria-label="Switch to dark theme" aria-pressed="false"><span class="theme-icon moon" aria-hidden="true"></span></button></nav></header>
<main class="directory">''' + ('<a href="/">← All runs</a>' if back else '') +
            f'<h1>{e(title)}</h1><p class="lede">{e(subtitle)}</p>'
            f'<div class="directory-bar"><span id="result-count">{count_label}</span>'
            '<input id="search" type="search" aria-label="Filter list" placeholder="Filter by name, model, or status…"></div>'
            f'<div class="card-grid">{"".join(cards)}</div>'
            f'<p class="empty-state" id="empty"{" hidden" if cards else ""}>{"No sessions recorded." if back else "No runs found in this directory."}</p>'
            '''</main><script>
const themeToggle = document.getElementById('theme-toggle');
  function setTheme(theme, persist = true) {
    document.documentElement.dataset.theme = theme;
    const targetTheme = theme === "dark" ? "light" : "dark";
    themeToggle.innerHTML = `<span class="theme-icon ${targetTheme === "light" ? "sun" : "moon"}" aria-hidden="true"></span>`;
    themeToggle.setAttribute("aria-label", `Switch to ${targetTheme} theme`);
    themeToggle.setAttribute("title", `Switch to ${targetTheme} theme`);
    themeToggle.setAttribute("aria-pressed", String(theme === "dark"));
    if (persist) localStorage.setItem("theme", theme);
  }

  setTheme(document.documentElement.dataset.theme || "light", false);
  themeToggle.addEventListener("click", () => {
    setTheme(document.documentElement.dataset.theme === "dark" ? "light" : "dark");
  });

const cards = [...document.querySelectorAll('.run-card')];
const count = document.getElementById('result-count');
const originalCount = count.textContent;
document.getElementById('search').addEventListener('input', event => {
  const term = event.target.value.trim().toLowerCase();
  let visible = 0;
  cards.forEach(card => {card.hidden = !card.textContent.toLowerCase().includes(term); if (!card.hidden) visible++;});
  count.textContent = term ? `${visible} of ${originalCount}` : originalCount;
  const empty = document.getElementById('empty');
  empty.hidden = visible > 0;
  if (cards.length) empty.textContent = 'No matches. Try another search.';
});
</script></body></html>''')


def card(target: str, title: str, eyebrow: str, status: str, metadata: list[str], action: str, tone: str = '') -> str:
    badge = f'<span class="badge {e(tone)}">{e(status)}</span>' if status else ''
    return (f'<a class="run-card" href="{e(target)}"><div class="card-top"><span>{e(eyebrow)}</span>'
            f'{badge}</div><h2>{e(title)}</h2>'
            + ''.join(f'<p class="card-meta">{e(item)}</p>' for item in metadata)
            + f'<span class="card-action">{e(action)} →</span></a>')
