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
:root { --bg:#f7f8fa; --card:#fff; --text:#22262e; --muted:#6b7280; --border:#e5e7eb;
  --accent:#3b82f6; --accent-dark:#2563eb; --radius:10px;
  --shadow:0 1px 3px rgba(16,24,40,.08); }
* { box-sizing:border-box; margin:0; padding:0; }
body { font-family:-apple-system,BlinkMacSystemFont,"Segoe UI","PingFang SC","Microsoft YaHei",sans-serif;
  background:var(--bg); color:var(--text); line-height:1.7; padding-bottom:60px; }
.topbar { position:sticky; top:0; z-index:9; background:rgba(255,255,255,.9); backdrop-filter:blur(8px);
  border-bottom:1px solid var(--border); padding:10px 20px; display:flex; align-items:center; gap:12px; }
.topbar a { color:var(--accent); text-decoration:none; font-size:14px; white-space:nowrap; }
.topbar .crumb { font-size:14px; color:var(--muted); overflow:hidden; text-overflow:ellipsis; white-space:nowrap; }
.topbar .gh { margin-left:auto; }
.wrap { max-width:920px; margin:24px auto; padding:0 20px; }
h1 { font-size:26px; margin-bottom:6px; }
.sub { color:var(--muted); font-size:14px; margin-bottom:20px; }
.grid { display:grid; grid-template-columns:repeat(auto-fill,minmax(260px,1fr)); gap:14px; }
.card { background:var(--card); border:1px solid var(--border); border-radius:var(--radius);
  box-shadow:var(--shadow); padding:18px; display:block; color:inherit; text-decoration:none;
  transition:transform .15s, box-shadow .15s; }
.card:hover { transform:translateY(-2px); box-shadow:0 8px 20px rgba(16,24,40,.12); }
.card h3 { font-size:16px; color:var(--accent-dark); margin-bottom:6px; word-break:break-all; }
.card p { font-size:13px; color:var(--muted); margin:0; }
table { width:100%; border-collapse:collapse; background:var(--card); border:1px solid var(--border);
  border-radius:var(--radius); overflow:hidden; box-shadow:var(--shadow); }
th, td { text-align:left; padding:9px 14px; border-bottom:1px solid var(--border); font-size:14px; }
th { background:#f9fafb; color:var(--muted); font-weight:600; }
tr:last-child td { border-bottom:none; }
td a { color:var(--accent); text-decoration:none; word-break:break-all; }
td a:hover { color:var(--accent-dark); text-decoration:underline; }
.tag { display:inline-block; font-size:12px; color:var(--muted); }
pre { background:#161b22; color:#e6edf3; padding:16px; border-radius:8px; overflow-x:auto;
  font-size:13.5px; line-height:1.6; }
code { font-family:"SFMono-Regular",Consolas,Menlo,monospace; }
p code, li code, td code { background:#f0f2f5; color:#c7254e; padding:1px 5px; border-radius:4px; font-size:.9em; }
.md-body { background:var(--card); border:1px solid var(--border); border-radius:var(--radius);
  box-shadow:var(--shadow); padding:24px 28px; margin-bottom:18px; }
.md-body h1,.md-body h2 { border-bottom:1px solid var(--border); padding-bottom:6px; margin:18px 0 10px; }
.md-body h1 { font-size:22px; } .md-body h2 { font-size:19px; }
.md-body img { max-width:100%; }
.filehead { background:var(--card); border:1px solid var(--border); border-radius:var(--radius);
  box-shadow:var(--shadow); padding:12px 18px; margin-bottom:14px; font-size:13px; color:var(--muted);
  display:flex; gap:14px; flex-wrap:wrap; align-items:center; }
.filehead a { color:var(--accent); text-decoration:none; }
.note { color:var(--muted); font-size:13px; margin-top:14px; }
.footer { text-align:center; color:var(--muted); font-size:12.5px; margin-top:36px; }
.dir { font-weight:600; }
"""

HLJS = ('<link rel="stylesheet" href="https://cdnjs.cloudflare.com/ajax/libs/highlight.js/11.9.0/styles/github.min.css">\n'
        '<script src="https://cdnjs.cloudflare.com/ajax/libs/highlight.js/11.9.0/highlight.min.js"></script>\n'
        '<script>window.addEventListener("load",function(){try{hljs.highlightAll()}catch(e){}});</script>')

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


def wrap_page(title: str, body: str, depth: int, extra_head: str = "") -> str:
    pre = "../" * depth
    return ("<!DOCTYPE html>\n<html lang=\"zh-CN\">\n<head>\n<meta charset=\"UTF-8\">\n"
            "<meta name=\"viewport\" content=\"width=device-width, initial-scale=1.0\">\n"
            "<title>%s</title>\n<style>%s</style>\n%s\n</head>\n<body>\n"
            '<div class="topbar"><a href="%sindex.html">&larr; 分支总览</a>'
            '<span class="crumb">%s</span></div>\n'
            '<div class="wrap">\n%s\n</div>\n</body>\n</html>\n'
            % (ES(title), SITE_CSS, extra_head, pre, ES(title), body))


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
    return wrap_page("%s / %s" % (branch, dir_rel or ""), body, depth)


def overview_page(title: str, repo_url: str, infos: list) -> str:
    cards = []
    for it in infos:
        extra = " · 自带首页" if it["has_index"] else ""
        cards.append('<a class="card" href="%s"><h3>%s</h3>'
                     '<p>📅 %s · 📄 %d 个文件%s</p></a>'
                     % (ES(it["href"]), ES(it["name"]), ES(it["date"] or "—"),
                        it["files"], extra))
    gh_link = '<a class="gh" href="%s">GitHub 仓库</a>' % ES(repo_url) if repo_url else ""
    body = ('<h1>%s</h1><p class="sub">全部分支一览 · 共 %d 个分支 · 生成于 %s (UTC)%s</p>'
            '<div class="grid">%s</div>'
            '<p class="footer">本站由 GitHub Actions 自动构建：分支更新后自动重建。</p>'
            % (ES(title), len(infos), datetime.utcnow().strftime("%Y-%m-%d %H:%M"), gh_link,
               "".join(cards)))
    return wrap_page(title + " · 分支总览", body, 0)


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
