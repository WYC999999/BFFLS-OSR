#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""把一个 git 仓库的所有分支打包成一个可浏览的静态网站。

用法（在 GitHub Actions 中或本地）:
  python build_site.py --repo <仓库路径> --repo-url <GitHub地址> --out <输出目录>

功能:
  - 自动发现仓库所有分支
  - Markdown(.md) 渲染为文章页; 代码/文本渲染为带语法高亮的页面
  - 图片/压缩包等二进制文件原样提供下载或预览
  - 每个分支一个子路径: branches/<分支名>/, 根目录生成分支总览首页
"""
import argparse
import html
import os
import shutil
import subprocess
import sys
import tarfile
import tempfile
import urllib.parse
from datetime import datetime
from pathlib import Path, PurePosixPath

try:
    import markdown as _md  # pip install markdown
except ImportError:
    _md = None

# ---------- 配置 ----------
SKIP_DIRS = {"__pycache__", "node_modules", ".git", ".idea", ".vscode", ".venv", "venv", ".gradle"}

IMG_EXT = {".png", ".jpg", ".jpeg", ".gif", ".svg", ".webp", ".bmp", ".ico", ".avif"}
BIN_COPY_EXT = {".pdf", ".zip", ".tar", ".gz", ".tgz", ".7z", ".rar", ".exe", ".dll", ".so",
                ".dylib", ".mp3", ".mp4", ".wav", ".woff", ".woff2", ".ttf", ".otf", ".jar",
                ".mrpack", ".jar", ".apk", ".iso", ".bin"}
WEB_ASSET_EXT = {".css", ".js", ".mjs", ".cjs", ".json"}  # 额外保留原文件, 兼容自带网页的分支
TEXT_EXT = {".md", ".markdown", ".txt", ".py", ".js", ".mjs", ".cjs", ".ts", ".tsx", ".jsx",
            ".json", ".css", ".scss", ".less", ".html", ".htm", ".xml", ".yml", ".yaml",
            ".toml", ".ini", ".cfg", ".conf", ".properties", ".sh", ".bash", ".bat", ".cmd",
            ".ps1", ".c", ".h", ".cpp", ".hpp", ".cc", ".java", ".kt", ".kts", ".swift",
            ".go", ".rs", ".rb", ".php", ".sql", ".lua", ".r", ".m", ".csv", ".tsv",
            ".gitignore", ".gitattributes", ".editorconfig", ".lock", ".log", ".gradle",
            ".env", ".srt", ".ass", ".vtt"}

LANG = {".py": "python", ".js": "javascript", ".mjs": "javascript", ".cjs": "javascript",
        ".ts": "typescript", ".tsx": "typescript", ".jsx": "javascript", ".json": "json",
        ".css": "css", ".scss": "scss", ".less": "less", ".html": "xml", ".htm": "xml",
        ".xml": "xml", ".yml": "yaml", ".yaml": "yaml", ".toml": "ini", ".ini": "ini",
        ".cfg": "ini", ".conf": "ini", ".properties": "properties", ".sh": "bash",
        ".bash": "bash", ".bat": "batch", ".cmd": "batch", ".ps1": "powershell",
        ".c": "c", ".h": "c", ".cpp": "cpp", ".hpp": "cpp", ".cc": "cpp",
        ".java": "java", ".kt": "kotlin", ".kts": "kotlin", ".swift": "swift",
        ".go": "go", ".rs": "rust", ".rb": "ruby", ".php": "php", ".sql": "sql",
        ".lua": "lua", ".r": "r"}

MAX_TEXT_BYTES = 400 * 1024      # 超过则只给下载/跳转链接
MAX_COPY_BYTES = 8 * 1024 * 1024
MAX_PAGES_PER_BRANCH = 4000

SITE_CSS = """
/* ================================================================
   BFFLS-OSR — ak.hypergryph.com inspired design
   Deep dark + glassmorphism + cyan/gold glow + geometric accents
   ================================================================ */
:root {
  --bg:#06080d; --bg-deep:#030408;
  --surface:rgba(16,22,36,.55); --surface-solid:#101624; --surface-hov:rgba(22,30,48,.65);
  --text:#e8ecf4; --text-dim:#8b9bb8; --muted:#546380;
  --border:rgba(70,90,130,.25); --border-light:rgba(70,90,130,.15);
  --accent:#00e5ff; --accent-alt:#4fd1c5;
  --accent-glow:rgba(0,229,255,.12); --accent-glow-strong:rgba(0,229,255,.25);
  --gold:#ffc850; --gold-glow:rgba(255,200,80,.12);
  --purple:#a78bfa; --purple-glow:rgba(167,139,250,.1);
  --radius:12px; --radius-sm:8px; --radius-lg:20px;
  --font-sans:-apple-system,BlinkMacSystemFont,"Segoe UI","PingFang SC",
    "Microsoft YaHei","Noto Sans SC","Helvetica Neue",Arial,sans-serif;
  --font-mono:"JetBrains Mono","SFMono-Regular",Consolas,"Liberation Mono",Menlo,monospace;
  --glow:0 0 20px var(--accent-glow), 0 0 60px rgba(0,229,255,.04);
  --glow-strong:0 0 24px var(--accent-glow-strong), 0 0 80px rgba(0,229,255,.06);
  --glass:linear-gradient(135deg,rgba(255,255,255,.04),rgba(255,255,255,.01));
  --transition:.3s cubic-bezier(.4,0,.2,1);
}
html.light {
  --bg:#f0f2f7; --bg-deep:#e4e8f2;
  --surface:rgba(255,255,255,.82); --surface-solid:#fff; --surface-hov:rgba(245,248,255,.95);
  --text:#141c32; --text-dim:#4e5d7a; --muted:#8896ad;
  --border:rgba(100,120,160,.18); --border-light:rgba(100,120,160,.1);
  --accent:#0066cc; --accent-alt:#0891b2;
  --accent-glow:rgba(0,102,204,.07); --accent-glow-strong:rgba(0,102,204,.14);
  --gold:#cc7700; --gold-glow:rgba(204,119,0,.08);
  --purple:#7c3aed; --purple-glow:rgba(124,58,237,.06);
  --glow:0 1px 8px rgba(0,0,0,.06), 0 0 0 1px var(--border);
  --glow-strong:0 4px 16px rgba(0,0,0,.08), 0 0 0 1px var(--border);
  --glass:linear-gradient(135deg,rgba(255,255,255,.7),rgba(255,255,255,.4));
}

*, *::before, *::after { box-sizing:border-box; margin:0; padding:0; }

body {
  font-family:var(--font-sans); background:var(--bg);
  color:var(--text); line-height:1.75; min-height:100vh;
  transition:background var(--transition), color var(--transition);
  /* subtle bg pattern */
  background-image:
    radial-gradient(ellipse 80% 50% at 50% -20%, rgba(0,229,255,.05), transparent),
    radial-gradient(ellipse 60% 40% at 100% 0%, rgba(167,139,250,.04), transparent),
    radial-gradient(ellipse 50% 30% at 0% 100%, rgba(255,200,80,.03), transparent);
  background-attachment:fixed;
}
html.light body {
  background-image:
    radial-gradient(ellipse 80% 50% at 50% -20%, rgba(0,102,204,.03), transparent),
    radial-gradient(ellipse 60% 40% at 100% 0%, rgba(124,58,237,.03), transparent);
}

/* ===== Scrollbar ===== */
::-webkit-scrollbar { width:6px; }
::-webkit-scrollbar-track { background:transparent; }
::-webkit-scrollbar-thumb { background:var(--border); border-radius:3px; }
::-webkit-scrollbar-thumb:hover { background:var(--muted); }

/* ===== Top navigation bar ===== */
.topbar {
  position:sticky; top:0; z-index:999;
  background:rgba(6,8,13,.75); backdrop-filter:saturate(200%) blur(20px);
  -webkit-backdrop-filter:saturate(200%) blur(20px);
  border-bottom:1px solid var(--border);
  padding:0 28px; height:56px;
  display:flex; align-items:center; gap:16px;
  transition:all var(--transition);
}
html.light .topbar { background:rgba(240,242,247,.8); }

.topbar a {
  color:var(--accent); text-decoration:none; font-size:13px;
  white-space:nowrap; font-weight:500; letter-spacing:.01em;
  transition:color .2s, text-shadow .2s;
}
.topbar a:hover { color:var(--gold); text-shadow:0 0 12px var(--gold-glow); }
.topbar .crumb {
  font-size:13px; color:var(--muted); overflow:hidden;
  text-overflow:ellipsis; white-space:nowrap; flex:1; min-width:0;
}
.topbar .gh { margin-left:auto; white-space:nowrap; }

/* Theme toggle */
.theme-toggle {
  background:var(--glass); border:1px solid var(--border); border-radius:50%;
  width:34px; height:34px; cursor:pointer; display:flex; align-items:center;
  justify-content:center; color:var(--text-dim); font-size:16px;
  transition:all var(--transition); flex-shrink:0;
}
.theme-toggle:hover {
  border-color:var(--accent); color:var(--accent);
  box-shadow:var(--glow); transform:rotate(15deg);
}

/* Search */
.search-wrap { position:relative; max-width:400px; width:100%; }
.search-wrap input {
  width:100%; padding:9px 14px 9px 36px;
  border:1px solid var(--border); border-radius:99px;
  background:var(--surface); color:var(--text);
  font-size:13px; font-family:var(--font-sans); outline:none;
  transition:all .25s;
}
.search-wrap input:focus {
  border-color:var(--accent); box-shadow:var(--glow);
  background:var(--surface-hov);
}
.search-wrap input::placeholder { color:var(--muted); font-size:12.5px; }
.search-wrap .si {
  position:absolute; left:13px; top:50%; transform:translateY(-50%);
  color:var(--muted); pointer-events:none; font-size:14px;
}

/* ===== Layout ===== */
.wrap { max-width:1000px; margin:36px auto; padding:0 28px; }

h1 {
  font-size:30px; font-weight:800; letter-spacing:-.03em; margin-bottom:8px;
  background:linear-gradient(135deg,var(--accent) 0%, var(--accent-alt) 50%, var(--gold) 100%);
  -webkit-background-clip:text; -webkit-text-fill-color:transparent;
  background-clip:text; line-height:1.3;
}
.sub { color:var(--muted); font-size:14px; margin-bottom:28px; letter-spacing:.01em; }

/* ===== Hero / Logo section (overview only) ===== */
.hero-logo {
  text-align:center; padding:40px 0 20px; position:relative;
}
.hero-logo img {
  max-width:200px; max-height:200px; border-radius:50%;
  box-shadow:var(--glow-strong), 0 0 0 1px var(--border);
  animation:float 6s ease-in-out infinite;
  transition:box-shadow var(--transition), transform var(--transition);
}
.hero-logo img:hover { transform:scale(1.05); box-shadow:0 0 40px var(--accent-glow-strong), 0 0 80px rgba(0,229,255,.1); }
@keyframes float {
  0%,100%{transform:translateY(0)} 50%{transform:translateY(-8px)}
}
.hero-line {
  width:80px; height:3px; margin:20px auto 0; border-radius:2px;
  background:linear-gradient(90deg,var(--accent),var(--gold));
  opacity:.7;
}

/* ===== Branch cards — glassmorphism style ===== */
.grid {
  display:grid; grid-template-columns:repeat(auto-fill,minmax(270px,1fr)); gap:20px;
}
.card {
  background:var(--surface); backdrop-filter:blur(12px);
  -webkit-backdrop-filter:blur(12px);
  border:1px solid var(--border); border-radius:var(--radius-lg);
  padding:24px; display:block; color:inherit; text-decoration:none;
  transition:all .35s cubic-bezier(.4,0,.2,1);
  position:relative; overflow:hidden;
}
/* geometric accent corner */
.card::before {
  content:''; position:absolute; top:0; left:0; right:0; height:2px;
  background:linear-gradient(90deg, transparent 0%, var(--accent) 40%, var(--gold) 100%);
  opacity:0; transition:opacity .35s;
}
/* subtle inner glow on hover */
.card::after {
  content:''; position:absolute; inset:0; border-radius:var(--radius-lg);
  pointer-events:none; opacity:0;
  background:radial-gradient(circle at 50% 0%, var(--accent-glow), transparent 70%);
  transition:opacity .35s;
}
.card:hover {
  transform:translateY(-6px);
  border-color:rgba(0,229,255,.3);
  box-shadow:var(--glow-strong), inset 0 1px 0 rgba(255,255,255,.04);
}
.card:hover::before { opacity:1; }
.card:hover::after { opacity:1; }
.card h3 {
  font-size:16px; font-weight:700; color:var(--text); margin-bottom:8px;
  word-break:break-all; transition:color .2s;
}
.card:hover h3 { color:var(--accent); }
.card p {
  font-size:12.5px; color:var(--muted); margin:0; line-height:1.6;
}
.card .tags { display:flex; gap:6px; flex-wrap:wrap; margin-top:12px; }
.card .tag-pill {
  display:inline-block; font-size:11px; padding:3px 10px; border-radius:99px;
  background:var(--accent-glow); color:var(--accent);
  border:1px solid rgba(0,229,255,.15);
  font-weight:600; letter-spacing:.03em;
  transition:all .2s;
}
.card .tag-pill:hover { background:var(--accent-glow-strong); border-color:var(--accent); }
html.light .card .tag-pill { background:rgba(0,102,204,.08); color:var(--accent); border-color:rgba(0,102,204,.15); }

/* ===== Tables ===== */
table {
  width:100%; border-collapse:collapse; background:var(--surface);
  backdrop-filter:blur(8px); -webkit-backdrop-filter:blur(8px);
  border:1px solid var(--border); border-radius:var(--radius); overflow:hidden;
  box-shadow:var(--glow);
}
th, td {
  text-align:left; padding:11px 18px;
  border-bottom:1px solid var(--border-light); font-size:13.5px;
}
th {
  background:rgba(0,0,0,.2); color:var(--text-dim); font-weight:700;
  text-transform:uppercase; font-size:11px; letter-spacing:.06em;
}
html.light th { background:rgba(0,0,0,.03); }
tr:last-child td { border-bottom:none; }
tr:hover td { background:var(--surface-hov); }
td a { color:var(--accent); text-decoration:none; word-break:break-all;
  transition:color .15s, text-shadow .15s; }
td a:hover { color:var(--gold); text-shadow:0 0 8px var(--gold-glow); }
.tag { display:inline-block; font-size:12px; color:var(--muted); }
.dir { font-weight:700; color:var(--accent) !important; }

/* ===== Code blocks ===== */
pre {
  background:var(--bg-deep); color:#e2e8f0; padding:20px 24px;
  border-radius:var(--radius); overflow-x:auto;
  font-size:13px; line-height:1.7;
  border:1px solid var(--border); position:relative;
  box-shadow:inset 0 1px 0 rgba(255,255,255,.03);
}
code { font-family:var(--font-mono); }
p code, li code, td code {
  background:var(--surface-hov); color:var(--gold);
  padding:2px 7px; border-radius:5px; font-size:.88em; font-family:var(--font-mono);
  border:1px solid var(--border-light);
}
html.light p code, html.light li code, html.light td code { color:#b86c00; }

/* ===== Markdown body ===== */
.md-body {
  background:var(--surface); backdrop-filter:blur(10px);
  -webkit-backdrop-filter:blur(10px);
  border:1px solid var(--border); border-radius:var(--radius-lg);
  box-shadow:var(--glow); padding:28px 36px; margin-bottom:24px;
  transition:all var(--transition);
}
.md-body h1, .md-body h2 {
  border-bottom:1px solid var(--border-light); padding-bottom:10px;
  margin:24px 0 14px; font-weight:700;
}
.md-body h1 { font-size:23px; } .md-body h2 { font-size:19px; } .md-body h3 { font-size:16.5px; margin:18px 0 8px; }
.md-body img { max-width:100%; border-radius:var(--radius-sm); box-shadow:var(--glow); }
.md-body ul, .md-body ol { padding-left:24px; margin:12px 0; }
.md-body li { margin:5px 0; }
.md-body blockquote {
  border-left:3px solid var(--accent); padding:12px 20px; margin:16px 0;
  background:var(--accent-glow); border-radius:0 var(--radius-sm) var(--radius-sm) 0;
  color:var(--text-dim); font-style:italic;
}
.md-body table { margin:16px 0; }
.md-body a { color:var(--accent); transition:color .15s; }
.md-body a:hover { color:var(--gold); }

/* ===== File header ===== */
.filehead {
  background:var(--surface); border:1px solid var(--border); border-radius:var(--radius);
  box-shadow:var(--glow); padding:14px 22px; margin-bottom:18px; font-size:13px;
  color:var(--muted); display:flex; gap:16px; flex-wrap:wrap; align-items:center;
}
.filehead b { color:var(--text); }
.filehead a { color:var(--accent); text-decoration:none; transition:color .15s; }
.filehead a:hover { color:var(--gold); }

/* ===== Footer ===== */
.note { color:var(--muted); font-size:13px; margin-top:18px; }
.footer {
  text-align:center; color:var(--muted); font-size:12px; margin-top:52px;
  padding-top:24px; border-top:1px solid var(--border-light);
  letter-spacing:.02em;
}
.no-results { text-align:center; color:var(--muted); padding:40px 0; font-size:14px; }

/* ===== Responsive ===== */
@media(max-width:768px) {
  .topbar { padding:0 16px; height:50px; gap:12px; flex-wrap:wrap; }
  .wrap { padding:0 18px; margin:24px auto; }
  .grid { grid-template-columns:1fr; gap:14px; }
  h1 { font-size:24px; }
  .hero-logo img { max-width:140px; max-height:140px; }
  .search-wrap { max-width:100%; }
  .card { padding:18px; }
}
"""

HLJS = ('<link rel="stylesheet" href="https://cdnjs.cloudflare.com/ajax/libs/highlight.js/11.9.0/styles/atom-one-dark.min.css">\n'
        '<script src="https://cdnjs.cloudflare.com/ajax/libs/highlight.js/11.9.0/highlight.min.js"></script>\n'
        '<script>document.addEventListener("DOMContentLoaded",function(){try{hljs.highlightAll()}catch(e){}})</script>')

ES = html.escape


def hsize(n: int) -> str:
    x = float(n)
    for unit in ("B", "KB", "MB", "GB"):
        if x < 1024 or unit == "GB":
            return "%d %s" % (n, unit) if unit == "B" else "%.1f %s" % (x, unit)
        x /= 1024
    return "%d B" % n


def q(s: str) -> str:
    return urllib.parse.quote(s, safe="/")


def branch_meta(name: str) -> tuple:
    """根据分支名返回 (icon_emoji, [tag_labels])"""
    n = name.lower()
    icon = "U0001f3e0"  # 🏠 默认
    tags = []
    if any(k in n for k in ("main", "master", "trunk")):
        icon = "🏠"; tags.append("主分支")
    elif any(k in n for k in ("dev", "develop", "development")):
        icon = "🔧"; tags.append("开发")
    elif "feature" in n or "feat" in n:
        icon = "✨"; tags.append("功能")
    elif any(k in n for k in ("fix", "bug", "hotfix", "patch")):
        icon = "🚧"; tags.append("修复")
    elif "release" in n or "rc" in n or "v" in n:
        icon = "🎉"; tags.append("发布")
    elif "doc" in n or "wiki" in n:
        icon = "📖"; tags.append("文档")
    elif "test" in n or "ci" in n:
        icon = "🚀"; tags.append("测试")
    if "osr" in n: tags.append("OSR")
    if "bffls" in n: tags.append("BFFLS")
    return icon, tags


def branch_meta(name: str) -> tuple:
    """根据分支名返回 (icon_emoji, [tag_labels])"""
    n = name.lower()
    icon = "U0001f3e0"  # 🏠 默认
    tags = []
    if any(k in n for k in ("main", "master", "trunk")):
        icon = "🏠"; tags.append("主分支")
    elif any(k in n for k in ("dev", "develop", "development")):
        icon = "🔧"; tags.append("开发")
    elif "feature" in n or "feat" in n:
        icon = "✨"; tags.append("功能")
    elif any(k in n for k in ("fix", "bug", "hotfix", "patch")):
        icon = "🚧"; tags.append("修复")
    elif "release" in n or "rc" in n or "v" in n:
        icon = "🎉"; tags.append("发布")
    elif "doc" in n or "wiki" in n:
        icon = "📖"; tags.append("文档")
    elif "test" in n or "ci" in n:
        icon = "🚀"; tags.append("测试")
    # 根据名称中的关键词追加额外标签
    if "osr" in n: tags.append("OSR")
    if "bffls" in n: tags.append("BFFLS")
    return icon, tags


def wrap_page(title: str, body: str, depth: int, extra_head: str = "",
             search_id: str = "", is_overview: bool = False) -> str:
    pre = "../" * depth
    # 搜索栏 HTML
    sh = ""
    if search_id:
        sh = ('<div class="search-wrap" style="margin-bottom:20px">'
              '<span class="si">&#128269;</span>'
              '<input type="search" id="%s" placeholder="搜索%s…" '
              'data-target="%s" autocomplete="off"></div>\n'
              % (ES(search_id),
                 "分支" if is_overview else "文件",
                 ".card" if is_overview else "table tr"))
    # 切换按钮
    tb = ('<button class="theme-toggle" id="tbtn" title="切换主题" aria-label="切换亮/暗模式">'
          '&#9790;</button>')
    # 内联 JS
    js = ('<script>'
          '(function(){var b=document.documentElement,t=document.getElementById("tbtn");'
          'if(t)t.addEventListener("click",function(){b.classList.toggle("light")});'
          'var si=document.getElementById("%s");if(si){'
          'var tgt=si.getAttribute("data-target");'
          'var tm;si.addEventListener("input",function(){clearTimeout(tm);tm=setTimeout(function(){'
          'var q=si.value.trim().toLowerCase();var els=document.querySelectorAll(tgt);'
          'var vis=0;els.forEach(function(el){var t=(el.textContent||el.innerText||"").toLowerCase();'
          'var show=q===""||t.indexOf(q)!==-1;el.style.display=show?"":"none";if(show)vis++});'
          'var nr=document.getElementById("nores");if(nr)nr.style.display=q!==""&&vis===0?"":"none"'
          '},120)});}'
          '})();</script>' % ES(search_id))
    return ("<!DOCTYPE html>\n<html lang=\"zh-CN\">\n<head>\n<meta charset=\"UTF-8\">\n"
            "<meta name=\"viewport\" content=\"width=device-width, initial-scale=1.0\">\n"
            "<title>%s</title>\n<style>%s</style>\n%s\n</head>\n<body>\n"
            '<div class="topbar"><a href="%sindex.html">&larr; 分支总览</a>'
            '%s<span class="crumb">%s</span>%s</div>\n'
            '<div class="wrap">%s%s<div class="no-results" id="nores" style="display:none">'
            '没有匹配的结果</div></div>\n%s\n</body>\n</html>\n'
            % (ES(title), SITE_CSS, extra_head, pre,
               sh if not is_overview else "",
               tb, ES(title),
               sh if is_overview else "",
               body, js))


# ---------- git 调用(全部经临时文件, 兼容受限环境) ----------
def git_lines(repo: Path, args: list) -> list:
    with tempfile.TemporaryFile() as fo, tempfile.TemporaryFile() as fe:
        r = subprocess.run(["git", "-C", str(repo)] + args, stdout=fo, stderr=fe)
        if r.returncode != 0:
            fe.seek(0)
            raise RuntimeError("git %s failed: %s" % (" ".join(args), fe.read().decode("utf-8", "replace").strip()))
        fo.seek(0)
        return [ln.strip() for ln in fo.read().decode("utf-8", "replace").splitlines() if ln.strip()]


def list_branches(repo: Path) -> list:
    names = git_lines(repo, ["branch", "-r", "--format=%(refname:short)"])
    names = [n for n in names if not n.endswith("/HEAD")]
    if not names:
        names = git_lines(repo, ["for-each-ref", "refs/heads", "--format=%(refname:short)"])
    return names


def branch_date(repo: Path, ref: str) -> str:
    try:
        lines = git_lines(repo, ["log", "-1", "--format=%cs", ref])
        return lines[0] if lines else ""
    except RuntimeError:
        return ""


def extract_ref(repo: Path, ref: str, workdir: Path):
    tar_path = workdir.parent / "_archive.tar"   # tar 放在 workdir 外, 避免被当作仓库文件
    git_lines(repo, ["archive", "--format=tar", "-o", str(tar_path), ref])
    with tarfile.open(tar_path) as tf:
        try:
            tf.extractall(workdir, filter="data")
        except TypeError:
            tf.extractall(workdir)
    tar_path.unlink(missing_ok=True)


# ---------- 页面生成 ----------
def md_to_html(text: str) -> str:
    if _md is not None:
        return _md.markdown(text, extensions=["fenced_code", "tables", "sane_lists"])
    return "<pre><code>%s</code></pre>" % ES(text)


def file_stub(title: str, message: str, gh_url: str, depth: int) -> str:
    link = '<a href="%s">在 GitHub 中打开源文件</a>' % ES(gh_url) if gh_url else "（未配置仓库地址）"
    body = ('<div class="filehead"><span>%s</span>%s</div>'
            '<div class="md-body"><p>%s</p></div>' % (ES(title), link, ES(message)))
    return wrap_page(title, body, depth)


def code_page(branch: str, rel_posix: str, text: str, lang: str, size: int, repo_url: str, depth: int) -> str:
    gh = "%s/blob/%s/%s" % (repo_url.rstrip("/"), q(branch), q(rel_posix)) if repo_url else ""
    gh_link = '<a href="%s">GitHub 源文件</a>' % ES(gh) if gh else ""
    cls = ' class="language-%s"' % lang if lang else ""
    body = ('<div class="filehead"><span class="tag">分支 <b>%s</b></span>'
            '<span class="tag">%s</span><span class="tag">%s</span>%s</div>'
            '<pre><code%s>%s</code></pre>'
            % (ES(branch), ES(rel_posix), hsize(size), gh_link, cls, ES(text)))
    return wrap_page(rel_posix, body, depth, extra_head=HLJS)


def md_page(branch: str, rel_posix: str, text: str, size: int, repo_url: str, depth: int) -> str:
    gh = "%s/blob/%s/%s" % (repo_url.rstrip("/"), q(branch), q(rel_posix)) if repo_url else ""
    gh_link = '<a href="%s">GitHub 源文件</a>' % gh if gh else ""
    body = ('<div class="filehead"><span class="tag">分支 <b>%s</b></span>'
            '<span class="tag">%s</span><span class="tag">%s</span>%s</div>'
            '<div class="md-body">%s</div>'
            % (ES(branch), ES(rel_posix), hsize(size), gh_link, md_to_html(text)))
    return wrap_page(rel_posix, body, depth)


def listing_page(branch: str, dir_rel: str, entries: list, readme_html: str,
                 repo_url: str, depth: int, branch_prefix: str) -> str:
    gh = "%s/tree/%s/%s" % (repo_url.rstrip("/"), q(branch), q(dir_rel)) if repo_url and dir_rel else repo_url
    gh_link = '<a class="gh" href="%s">在 GitHub 查看</a>' % ES(gh) if gh else ""
    crumb = '<a href="%sindex.html">%s</a>' % (branch_prefix, ES(branch)) if dir_rel else ("总览" if False else ES(branch))
    rows = []
    for (name, kind, href, size) in entries:
        view = '<a href="%s">%s</a>' % (ES(href), ES(name))
        if kind == "dir":
            view = '<a class="dir" href="%s">📁 %s/</a>' % (ES(href), ES(name))
            sz = "—"
        else:
            sz = hsize(size)
        rows.append("<tr><td>%s</td><td>%s</td></tr>" % (view, sz))
    body = ('<h1>%s</h1><p class="sub">目录列表 · 分支 <b>%s</b>%s</p>%s'
            '<table><tr><th>名称</th><th>大小</th></tr>%s</table>'
            % (ES(dir_rel or branch), ES(branch), (" · " + gh_link) if gh else "",
               ('<div class="md-body">%s</div>' % readme_html) if readme_html else "",
               "".join(rows)))
    return wrap_page("%s / %s" % (branch, dir_rel or ""), body, depth,
                    search_id="file-search")


def overview_page(title: str, repo_url: str, infos: list, logo_html: str = "") -> str:
    cards = []
    for it in infos:
        _, tags = branch_meta(it["name"])
        tag_html = ""
        if tags:
            tag_html = '<div class="tags">' + "".join(
                '<span class="tag-pill">%s</span>' % ES(t) for t in tags) + '</div>'
        extra = " · 自带首页" if it["has_index"] else ""
        cards.append('<a class="card" href="%s"><h3>%s</h3>'
                     '<p>📅 %s · 📄 %d 个文件%s</p>%s</a>'
                     % (ES(it["href"]), ES(it["name"]),
                        ES(it["date"] or "—"), it["files"], extra, tag_html))
    gh_link = '<a class="gh" href="%s">GitHub 仓库</a>' % ES(repo_url) if repo_url else ""
    body = (logo_html +
            '<h1>%s</h1><p class="sub">全部分支一览 · 共 %d 个分支 · 生成于 %s (UTC)</p>'
            '<div class="grid">%s</div>'
            '<p class="footer">本站由 GitHub Actions 自动构建：分支更新后自动重建。%s</p>'
            % (ES(title), len(infos), datetime.utcnow().strftime("%Y-%m-%d %H:%M"),
               "".join(cards), gh_link))
    return wrap_page(title + " · 分支总览", body, 0,
                    search_id="branch-search", is_overview=True)


# ---------- 单个分支构建 ----------
def build_branch(work: Path, outdir: Path, branch: str, repo_url: str):
    outdir.mkdir(parents=True, exist_ok=True)
    pages = 0
    skipped = 0
    dirs_map = {}  # rel_posix(str) -> {"entries": [], "has_index": bool}

    def reg_dir(rel: PurePosixPath):
        key = rel.as_posix() if str(rel) != "." else ""
        if key not in dirs_map:
            dirs_map[key] = {"entries": [], "has_index": False}
        return key

    for root, dirnames, filenames in os.walk(work):
        dirnames[:] = sorted(d for d in dirnames if d not in SKIP_DIRS)
        rel = PurePosixPath(Path(root).relative_to(work).as_posix())
        if str(rel) == ".":
            rel = PurePosixPath("")
        base_key = reg_dir(rel)
        for d in dirnames:
            reg_dir(rel / d)
            dirs_map[base_key]["entries"].append((d, "dir", None, 0))

        for fn in sorted(filenames):
            src = Path(root) / fn
            try:
                size = src.stat().st_size
            except OSError:
                continue
            ext = src.suffix.lower()
            rel_file = (rel / fn) if str(rel) else PurePosixPath(fn)
            rel_posix = rel_file.as_posix()
            is_index = fn.lower() in ("index.html", "index.htm")
            dest = outdir / rel_file

            # 默认: 链接指向生成的阅读页 xxx.html
            href = q(rel_posix) + ".html"

            if is_index:
                # 分支自带首页: 原样保留, 目录链接直接指向它
                dest.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(src, dest)
                dirs_map[base_key]["has_index"] = True
                href = q(str(rel)) + "/" if str(rel) else q(fn)
                dirs_map[base_key]["entries"].append((fn, "file", href, size))
                continue

            if ext in IMG_EXT or ext in BIN_COPY_EXT or ext in WEB_ASSET_EXT:
                if size <= MAX_COPY_BYTES:
                    dest.parent.mkdir(parents=True, exist_ok=True)
                    shutil.copy2(src, dest)
                    if ext in IMG_EXT:
                        href = q(rel_posix)          # 浏览器直接预览
                    elif ext in WEB_ASSET_EXT and pages < MAX_PAGES_PER_BRANCH:
                        # css/js/json: 保留原文件供自带网页引用, 同时生成阅读页
                        text = (raw := _read_bytes(src)) and raw.decode("utf-8", "replace") or ""
                        _write(outdir / (rel_posix + ".html"),
                               code_page(branch, rel_posix, text, LANG.get(ext, ""), size, repo_url,
                                         2 + (len(rel_file.parent.parts) if str(rel) else 0)))
                        pages += 1
                else:
                    href = q(rel_posix) + ".html"
                    gh = "%s/blob/%s/%s" % (repo_url.rstrip("/"), q(branch), q(rel_posix)) if repo_url else ""
                    page = file_stub(rel_posix, "该文件过大（%s），未在网页中展示。" % hsize(size), gh,
                                     2 + len(rel_file.parent.parts) - (0 if str(rel) else 0))
                    (outdir / (rel_posix + ".html")).parent.mkdir(parents=True, exist_ok=True)
                    _write(outdir / (rel_posix + ".html"), page)
                    pages += 1
                if ext not in IMG_EXT:
                    pass
                dirs_map[base_key]["entries"].append((fn, "file", href, size))
                continue

            # 其余: 尝试按文本处理
            raw = _read_bytes(src)
            if raw is None:
                dirs_map[base_key]["entries"].append((fn, "file", href, size))
                continue
            is_text = b"\x00" not in raw[:8192]
            depth = 2 + (len(rel_file.parent.parts) if str(rel) else 0)
            gh = "%s/blob/%s/%s" % (repo_url.rstrip("/"), q(branch), q(rel_posix)) if repo_url else ""

            if not is_text:
                if size <= MAX_COPY_BYTES:
                    dest.parent.mkdir(parents=True, exist_ok=True)
                    shutil.copy2(src, dest)
                    href = q(rel_posix)
                else:
                    page = file_stub(rel_posix, "二进制文件过大（%s），未在网页中展示。" % hsize(size), gh, depth)
                    _write(outdir / (rel_posix + ".html"), page)
                    pages += 1
                    href = q(rel_posix) + ".html"
            elif ext in (".md", ".markdown"):
                if size <= MAX_TEXT_BYTES and pages < MAX_PAGES_PER_BRANCH:
                    _write(outdir / (rel_posix + ".html"),
                           md_page(branch, rel_posix, raw.decode("utf-8", "replace"), size, repo_url, depth))
                    pages += 1
                else:
                    page = file_stub(rel_posix, "文档过大（%s），未在网页中展示。" % hsize(size), gh, depth)
                    _write(outdir / (rel_posix + ".html"), page)
                    pages += 1
            else:
                if size <= MAX_TEXT_BYTES and pages < MAX_PAGES_PER_BRANCH:
                    text = raw.decode("utf-8", "replace")
                    _write(outdir / (rel_posix + ".html"),
                           code_page(branch, rel_posix, text, LANG.get(ext, ""), size, repo_url, depth))
                    pages += 1
                else:
                    page = file_stub(rel_posix, "文件过大（%s），未在网页中展示。" % hsize(size), gh, depth)
                    _write(outdir / (rel_posix + ".html"), page)
                    pages += 1
            if pages >= MAX_PAGES_PER_BRANCH and size > MAX_TEXT_BYTES:
                skipped += 1
            dirs_map[base_key]["entries"].append((fn, "file", href, size))

    # 目录列表页
    for key in sorted(dirs_map.keys()):
        info = dirs_map[key]
        rel = PurePosixPath(key)
        listing_path = outdir / rel / "index.html" if key else outdir / "index.html"
        if info["has_index"] and listing_path.exists():
            continue  # 分支自带首页, 不覆盖
        entries = []
        for (name, kind, href, size) in info["entries"]:
            if kind == "dir":
                child_key = (key + "/" + name) if key else name
                child = dirs_map.get(child_key, {"has_index": False})
                entries.append((name, "dir", q(name) + "/", 0))
            else:
                entries.append((name, "file", href, size))
        entries.sort(key=lambda e: (e[1] != "dir", e[0].lower()))
        # README 渲染
        readme_html = ""
        rd = None
        for (name, kind, href, size) in info["entries"]:
            if kind == "file" and name.lower() in ("readme.md", "readme.markdown"):
                rd = (outdir / rel / name) if key else (outdir / name)
                break
        if rd is not None and rd.exists() and rd.stat().st_size <= MAX_TEXT_BYTES:
            readme_html = md_to_html(rd.read_bytes().decode("utf-8", "replace"))
        depth = 2 + len(rel.parts) if key else 2
        branch_prefix = "../" * (len(rel.parts) if key else 0)
        page = listing_page(branch, key, entries, readme_html, repo_url, depth, branch_prefix)
        _write(listing_path, page)

    return {"pages": pages, "skipped": skipped,
            "has_root_index": dirs_map.get("", {}).get("has_index", False)}


def _read_bytes(p: Path):
    try:
        return p.read_bytes()
    except OSError:
        return None


def _write(p: Path, text: str):
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(text, encoding="utf-8")


# ---------- 主流程 ----------
def main():
    ap = argparse.ArgumentParser(description="把 git 仓库所有分支打包为静态网站")
    ap.add_argument("--repo", default=".", help="仓库路径")
    ap.add_argument("--repo-url", dest="repo_url", default="", help="GitHub 仓库地址(用于源文件链接)")
    ap.add_argument("--out", default="_site", help="输出目录")
    ap.add_argument("--title", default="BFFLS-OSR", help="站点标题")
    a = ap.parse_args()

    repo = Path(a.repo).resolve()
    out = Path(a.out).resolve()
    if out.exists():
        shutil.rmtree(out)
    out.mkdir(parents=True)

    refs = list_branches(repo)
    if not refs:
        sys.exit("错误: 未发现任何分支")
    print("发现 %d 个分支" % len(refs))

    infos = []
    used = {}
    for ref in refs:
        name = ref[7:] if ref.startswith("origin/") else ref
        safe = "".join(ch if (ch.isalnum() or ch in "._-") else "_" for ch in name) or "branch"
        if safe in used:
            used[safe] += 1
            safe = "%s_%d" % (safe, used[safe])
        else:
            used[safe] = 0

        with tempfile.TemporaryDirectory() as td:
            work = Path(td) / "w"
            work.mkdir()
            try:
                extract_ref(repo, ref, work)
            except RuntimeError as e:
                print("跳过分支 %s: %s" % (name, e))
                continue
            outdir = out / "branches" / safe
            stat = build_branch(work, outdir, name, a.repo_url)
            print("  %-30s -> %d 页" % (name, stat["pages"]))
            infos.append({"name": name, "href": q("branches/" + safe) + "/",
                          "date": branch_date(repo, ref), "files": stat["pages"],
                          "has_index": stat["has_root_index"]})

    # 检测 Logo 图片
    logo_html = ""
    for lf in ("logo.png","logo.jpg","logo.jpeg","logo.svg","logo.webp"):
        lp = repo / lf
        if lp.exists() and lp.stat().st_size < 2*1024*1024:
            import shutil as _shutil
            _shutil.copy2(lp, out / lf)
            logo_html = ('<div class="hero-logo">'
                       '<img src="%s" alt="Logo" loading="lazy"></div>'
                       '<div class="hero-line"></div>' % ES(lf))
            break

    _write(out / "index.html", overview_page(a.title, a.repo_url, infos, logo_html))
    print("完成: %s (共 %d 个分支)" % (out, len(infos)))


if __name__ == "__main__":
    main()
