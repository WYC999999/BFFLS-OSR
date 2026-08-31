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
/* ===== Arknights-inspired Dark Theme (default) + Light Mode Toggle ===== */
:root {
  --bg:#0c1017; --bg-deep:#080b10;
  --surface:#151c25; --surface-hov:#1a2332;
  --text:#e0e6ed; --text-dim:#8b99ab; --muted:#5d6d82;
  --border:#252f3d; --border-light:#1e2736;
  --accent:#4fc3f7; --accent-glow:rgba(79,195,247,.15);
  --accent-warm:#f0a030; --accent-warm-glow:rgba(240,160,48,.12);
  --radius:10px; --radius-sm:6px;
  --shadow:0 2px 12px rgba(0,0,0,.35), 0 0 0 1px var(--border);
  --shadow-hover:0 8px 28px rgba(0,0,0,.45), 0 0 20px var(--accent-glow);
  --font-sans:-apple-system,BlinkMacSystemFont,"Segoe UI","PingFang SC","Microsoft YaHei","Noto Sans SC",sans-serif;
  --font-mono:"SFMono-Regular",Consolas,"Liberation Mono",Menlo,monospace;
}
html.light {
  --bg:#f4f6fa; --bg-deep:#eef1f6;
  --surface:#ffffff; --surface-hov:#f8fafc;
  --text:#1a2030; --text-dim:#4a5568; --muted:#8896a8;
  --border:#dde3ec; --border-light:#e2e8f2;
  --accent:#2563eb; --accent-glow:rgba(37,99,235,.08);
  --accent-warm:#ea580c; --accent-warm-glow:rgba(234,88,12,.08);
  --shadow:0 1px 4px rgba(16,24,40,.08), 0 0 0 1px var(--border);
  --shadow-hover:0 6px 20px rgba(16,24,40,.12), 0 0 16px var(--accent-glow);
}

* { box-sizing:border-box; margin:0; padding:0; }

body {
  font-family:var(--font-sans); background:var(--bg); color:var(--text);
  line-height:1.72; padding-bottom:60px; transition:background .3s,color .3s;
}

/* ===== Top bar ===== */
.topbar {
  position:sticky; top:0; z-index:99;
  background:rgba(12,16,23,.85); backdrop-filter:saturate(180%) blur(16px);
  -webkit-backdrop-filter:saturate(180%) blur(16px);
  border-bottom:1px solid var(--border); padding:10px 24px;
  display:flex; align-items:center; gap:14px;
  transition:background .3s,border-color .3s;
}
html.light .topbar { background:rgba(244,246,250,.88); }

.topbar a { color:var(--accent); text-decoration:none; font-size:13.5px; white-space:nowrap;
  transition:color .15s; }
.topbar a:hover { color:var(--accent-warm); }
.topbar .crumb { font-size:13.5px; color:var(--muted); overflow:hidden;
  text-overflow:ellipsis; white-space:nowrap; flex:1; min-width:0; }
.topbar .gh { margin-left:auto; white-space:nowrap; }

.theme-toggle {
  background:none; border:1.5px solid var(--border); border-radius:50%;
  width:34px; height:34px; cursor:pointer; display:flex; align-items:center;
  justify-content:center; color:var(--text-dim); font-size:17px;
  transition:all .25s; flex-shrink:0;
}
.theme-toggle:hover { border-color:var(--accent); color:var(--accent);
  box-shadow:0 0 12px var(--accent-glow); }

.search-wrap { position:relative; max-width:420px; width:100%; }
.search-wrap input {
  width:100%; padding:9px 14px 9px 36px; border:1.5px solid var(--border);
  border-radius:var(--radius-sm); background:var(--surface); color:var(--text);
  font-size:13.5px; font-family:var(--font-sans); outline:none;
  transition:border-color .2s,box-shadow .2s,background .2s;
}
.search-wrap input:focus { border-color:var(--accent); box-shadow:0 0 0 3px var(--accent-glow); }
.search-wrap input::placeholder { color:var(--muted); }
.search-wrap .si { position:absolute; left:11px; top:50%;
  transform:translateY(-50%); color:var(--muted); pointer-events:none; font-size:14px; }

.wrap { max-width:960px; margin:28px auto; padding:0 24px; }
h1 { font-size:27px; letter-spacing:-.02em; margin-bottom:6px;
  background:linear-gradient(135deg,var(--accent),var(--accent-warm));
  -webkit-background-clip:text; -webkit-text-fill-color:transparent; background-clip:text; }
.sub { color:var(--muted); font-size:14px; margin-bottom:24px; }

.grid { display:grid; grid-template-columns:repeat(auto-fill,minmax(260px,1fr)); gap:16px; }
.card {
  background:var(--surface); border:1px solid var(--border); border-radius:var(--radius);
  box-shadow:var(--shadow); padding:20px; display:block; color:inherit; text-decoration:none;
  transition:transform .25s,box-shadow .25s,border-color .25s;
  position:relative; overflow:hidden;
}
.card::before {
  content:''; position:absolute; top:0;left:0;right:0;height:2.5px;
  background:linear-gradient(90deg,var(--accent),var(--accent-warm)); opacity:0;
  transition:opacity .25s;
}
.card:hover { transform:translateY(-4px); box-shadow:var(--shadow-hover); border-color:var(--accent); }
.card:hover::before { opacity:1; }
.card .c-icon { font-size:26px; margin-bottom:8px; display:block; }
.card h3 { font-size:15.5px; color:var(--text); margin-bottom:6px; word-break:break-all;
  transition:color .15s; }
.card:hover h3 { color:var(--accent); }
.card p { font-size:12.5px; color:var(--muted); margin:0; line-height:1.55; }
.card .tags { display:flex; gap:6px; flex-wrap:wrap; margin-top:10px; }
.card .tag-pill {
  display:inline-block; font-size:11px; padding:2px 8px; border-radius:99px;
  background:var(--accent-glow); color:var(--accent); border:1px solid transparent;
  font-weight:500; letter-spacing:.02em;
}
html.light .card .tag-pill { background:rgba(37,99,235,.08); color:var(--accent); }

table { width:100%; border-collapse:collapse; background:var(--surface);
  border:1px solid var(--border); border-radius:var(--radius); overflow:hidden;
  box-shadow:var(--shadow); }
th,td { text-align:left; padding:10px 16px; border-bottom:1px solid var(--border-light); font-size:13.5px; }
th { background:var(--bg-deep); color:var(--text-dim); font-weight:600;
  text-transform:uppercase; font-size:11.5px; letter-spacing:.05em; }
tr:last-child td { border-bottom:none; }
tr:hover td { background:var(--surface-hov); }
td a { color:var(--accent); text-decoration:none; word-break:break-all; transition:color .15s; }
td a:hover { color:var(--accent-warm); text-decoration:underline; }
.tag { display:inline-block; font-size:12px; color:var(--muted); }
.dir { font-weight:600; color:var(--accent) !important; }

pre {
  background:var(--bg-deep); color:#c9d1d9; padding:18px 20px; border-radius:var(--radius);
  overflow-x:auto; font-size:13.2px; line-height:1.65;
  border:1px solid var(--border); position:relative;
}
code { font-family:var(--font-mono); }
p code,li code,td code {
  background:var(--surface-hov); color:#f0a030; padding:2px 6px;
  border-radius:4px; font-size:.88em; font-family:var(--font-mono);
}
html.light p code,html.light li code,html.light td code { color:#cf4a00; }

.md-body {
  background:var(--surface); border:1px solid var(--border); border-radius:var(--radius);
  box-shadow:var(--shadow); padding:26px 32px; margin-bottom:20px;
  transition:background .3s,border-color .3s;
}
.md-body h1,.md-body h2 { border-bottom:1px solid var(--border-light); padding-bottom:8px;
  margin:22px 0 12px; }
.md-body h1 { font-size:22px; } .md-body h2 { font-size:18.5px; }
.md-body h3 { font-size:16px; margin:16px 0 8px; }
.md-body img { max-width:100%; border-radius:var(--radius-sm); }
.md-body ul,.md-body ol { padding-left:22px; margin:10px 0; }
.md-body li { margin:4px 0; }
.md-body blockquote { border-left:3px solid var(--accent); padding:10px 18px;
  margin:14px 0; background:var(--accent-glow); border-radius:0 var(--radius-sm) var(--radius-sm) 0;
  color:var(--text-dim); }
.md-body table { margin:14px 0; }
.md-body a { color:var(--accent); } .md-body a:hover { color:var(--accent-warm); }

.filehead {
  background:var(--surface); border:1px solid var(--border); border-radius:var(--radius);
  box-shadow:var(--shadow); padding:12px 20px; margin-bottom:16px; font-size:13px;
  color:var(--muted); display:flex; gap:14px; flex-wrap:wrap; align-items:center;
}
.filehead b { color:var(--text); }
.filehead a { color:var(--accent); text-decoration:none; transition:color .15s; }
.filehead a:hover { color:var(--accent-warm); }

.note { color:var(--muted); font-size:13px; margin-top:16px; }
.footer { text-align:center; color:var(--muted); font-size:12px; margin-top:44px;
  padding-top:20px; border-top:1px solid var(--border-light); }
.no-results { text-align:center; color:var(--muted); padding:32px 0; font-size:14px; }

@media(max-width:720px) {
  .topbar { padding:8px 14px; gap:10px; flex-wrap:wrap; }
  .wrap { padding:0 16px; margin:20px auto; }
  .grid { grid-template-columns:1fr; }
  h1 { font-size:22px; }
  .search-wrap { max-width:100%; }
}
"""

HLJS = ('<link rel="stylesheet" href="https://cdnjs.cloudflare.com/ajax/libs/highlight.js/11.9.0/styles/github-dark.min.css">\n'
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
        icon = "U0001f3e0"; tags.append("主分支")
    elif any(k in n for k in ("dev", "develop", "development")):
        icon = "U0001f527"; tags.append("开发")
    elif "feature" in n or "feat" in n:
        icon = "✨"; tags.append("功能")
    elif any(k in n for k in ("fix", "bug", "hotfix", "patch")):
        icon = "U0001f6a7"; tags.append("修复")
    elif "release" in n or "rc" in n or "v" in n:
        icon = "U0001f389"; tags.append("发布")
    elif "doc" in n or "wiki" in n:
        icon = "U0001f4d6"; tags.append("文档")
    elif "test" in n or "ci" in n:
        icon = "U0001f680"; tags.append("测试")
    if "osr" in n: tags.append("OSR")
    if "bffls" in n: tags.append("BFFLS")
    return icon, tags


def branch_meta(name: str) -> tuple:
    """根据分支名返回 (icon_emoji, [tag_labels])"""
    n = name.lower()
    icon = "U0001f3e0"  # 🏠 默认
    tags = []
    if any(k in n for k in ("main", "master", "trunk")):
        icon = "U0001f3e0"; tags.append("主分支")
    elif any(k in n for k in ("dev", "develop", "development")):
        icon = "U0001f527"; tags.append("开发")
    elif "feature" in n or "feat" in n:
        icon = "✨"; tags.append("功能")
    elif any(k in n for k in ("fix", "bug", "hotfix", "patch")):
        icon = "U0001f6a7"; tags.append("修复")
    elif "release" in n or "rc" in n or "v" in n:
        icon = "U0001f389"; tags.append("发布")
    elif "doc" in n or "wiki" in n:
        icon = "U0001f4d6"; tags.append("文档")
    elif "test" in n or "ci" in n:
        icon = "U0001f680"; tags.append("测试")
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


def overview_page(title: str, repo_url: str, infos: list) -> str:
    cards = []
    for it in infos:
        icon, tags = branch_meta(it["name"])
        tag_html = ""
        if tags:
            tag_html = '<div class="tags">' + "".join(
                '<span class="tag-pill">%s</span>' % ES(t) for t in tags) + '</div>'
        extra = " · 自带首页" if it["has_index"] else ""
        cards.append('<a class="card" href="%s"><span class="c-icon">%s</span><h3>%s</h3>'
                     '<p>📅 %s · 📄 %d 个文件%s</p>%s</a>'
                     % (ES(it["href"]), icon, ES(it["name"]),
                        ES(it["date"] or "—"), it["files"], extra, tag_html))
    gh_link = '<a class="gh" href="%s">GitHub 仓库</a>' % ES(repo_url) if repo_url else ""
    body = ('<h1>%s</h1><p class="sub">全部分支一览 · 共 %d 个分支 · 生成于 %s (UTC)</p>'
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

    _write(out / "index.html", overview_page(a.title, a.repo_url, infos))
    print("完成: %s (共 %d 个分支)" % (out, len(infos)))


if __name__ == "__main__":
    main()
