"""보고서 md(확장 문법) → HTML → A4 PDF. 사용: build_pdf.py 입력.md 출력.pdf [제목]
확장: ::: 클래스 블록 (:::로 닫음), {{그림이름|캡션}} 그림 삽입, ## ! 제목 = 새 쪽
"""
import asyncio, re, sys, base64
from pathlib import Path
from markdown_it import MarkdownIt
from playwright.async_api import async_playwright
ROOT = Path(__file__).resolve().parents[1]  # report/
MATH_FONT = Path.home() / ".local/share/fonts/CambriaMath.ttf"  # 수식 글꼴 (OpenType MATH)
MD = MarkdownIt("commonmark", {"html": True}).enable("table")
CSS = (f"@font-face {{ font-family:'BookMath'; src:url('{MATH_FONT.as_uri()}'); }}\n" if MATH_FONT.exists() else "") + """
@page { size: A4; margin: 19mm 20mm 19mm 20mm; }
* { box-sizing: border-box; }
html { -webkit-print-color-adjust: exact; print-color-adjust: exact; }
body { font-family: 'NanumMyeongjo',serif; font-size: 10.4pt; line-height: 1.82; color: #1a1a1a; margin: 0; word-break: keep-all; overflow-wrap: anywhere; text-align: justify; }
h1 { font-family: 'NanumBarunGothic','NanumGothic',sans-serif; font-size: 17pt; font-weight: 700; line-height: 1.3; margin: 0 0 12pt; padding-bottom: 6pt; border-bottom: .6pt solid #9a9a9a; text-align: left; }
h2 { font-family: 'NanumBarunGothic','NanumGothic',sans-serif; font-size: 13.5pt; font-weight: 700; margin: 22pt 0 8pt; text-align: left; page-break-after: avoid; }
h2.pb { page-break-before: always; margin-top: 0; }
h3 { font-family: 'NanumBarunGothic','NanumGothic',sans-serif; font-size: 11pt; font-weight: 700; margin: 15pt 0 5pt; text-align: left; page-break-after: avoid; }
p { margin: 0 0 8pt; }
ul, ol { margin: 0 0 8pt; padding-left: 15pt; }
li { margin-bottom: 3pt; }
strong { font-family: 'NanumBarunGothic','NanumGothic',sans-serif; font-weight: 700; font-size: .96em; }
code { font-family: 'NanumGothicCoding',monospace; font-size: .86em; }
table { border-collapse: collapse; width: 100%; margin: 6pt 0 11pt; font-family: 'NanumBarunGothic','NanumGothic',sans-serif; font-size: 8.4pt; line-height: 1.42; text-align: left; }
tr { page-break-inside: avoid; }
thead { display: table-header-group; }
th { font-weight: 700; border-top: .9pt solid #333; border-bottom: .6pt solid #333; padding: 3pt 5pt; vertical-align: bottom; }
td { border-bottom: .3pt solid #cfcfcf; padding: 2.8pt 5pt; vertical-align: top; }
.meta { font-family: 'NanumBarunGothic','NanumGothic',sans-serif; color: #6a6a6a; font-size: 8.4pt; margin-bottom: 12pt; text-align: left; }
.ask, .result, .ground, .aside, .think, .sw { padding: 8pt 11pt; margin: 9pt 0 11pt; page-break-inside: avoid; }
.ask p:last-child, .result p:last-child, .ground p:last-child, .aside p:last-child { margin-bottom: 0; }
.ask { background: #e9f4f2; border-left: 2.6pt solid #2b8f85; }
.result { background: #edf2fa; border-left: 2.6pt solid #2f5fa8; }
.ground { background: #f3f3f2; border-left: 2.6pt solid #55554f; font-size: 9.7pt; }
.aside { border-left: 2.6pt dashed #8a8a84; font-size: 9pt; line-height: 1.7; }
.think { font-size: 9.8pt; border-top: .6pt solid #9a9a9a; padding-left: 0; padding-right: 0; }
.sw { background: #fbfaf6; border: .4pt solid #cfccc0; }
.label { font-family: 'NanumBarunGothic','NanumGothic',sans-serif; font-weight: 700; font-size: .95em; }
.ask .label { color: #1f7168; } .result .label { color: #2f5fa8; }
.cover { background: #12355b; color: #fff; padding: 16pt 18pt 14pt; margin: 0 0 12pt; }
.cover p { margin: 0 0 4pt; text-align: left; }
.cover .kicker { font-family: 'NanumBarunGothic','NanumGothic',sans-serif; font-size: 8.6pt; letter-spacing: .5pt; color: #c9d6e6; }
.cover .title { font-family: 'NanumBarunGothic','NanumGothic',sans-serif; font-size: 19pt; font-weight: 700; line-height: 1.3; margin: 4pt 0 6pt; }
.cover .sub { font-family: 'NanumBarunGothic','NanumGothic',sans-serif; font-size: 10pt; color: #e3eaf3; }
.key { background: #eef3f9; border-top: 2pt solid #12355b; padding: 9pt 12pt; margin: 6pt 0 12pt; page-break-inside: avoid; }
.key p:last-child { margin-bottom: 0; }
.key .label, .note .label { color: #12355b; }
.note { background: #f6f5f1; border-left: 2.6pt solid #8a7a4a; padding: 8pt 11pt; margin: 9pt 0 11pt; font-size: 9.6pt; page-break-inside: avoid; }
blockquote { margin: 8pt 0 10pt; padding: 7pt 11pt; background: #edf2fa; border-left: 2.6pt solid #2f5fa8; page-break-inside: avoid; }
blockquote p:last-child { margin-bottom: 0; }
.eq { text-align: center; margin: 6pt 0 9pt; page-break-inside: avoid; }
math { font-family: 'BookMath', math; }
math[display=block] { display: block math; font-size: 112%; }
figure { margin: 9pt 0 5pt; page-break-inside: avoid; text-align: center; }
figure img { max-width: 100%; max-height: 78mm; }
figcaption { font-family: 'NanumBarunGothic','NanumGothic',sans-serif; font-size: 8.2pt; color: #555; margin-top: 3pt; text-align: left; line-height: 1.5; }
/* ── 정보 위계 ── */
body { font-size: 10pt; line-height: 1.72; }
h2 { color: #12355b; font-size: 15pt; border-left: 4pt solid #12355b; padding: 1pt 0 1pt 8pt; margin: 20pt 0 10pt; }
h2.pb { margin-top: 0; }
h3 { color: #12355b; font-size: 12pt; border-bottom: .6pt solid #b9c8dc; padding-bottom: 3pt; margin: 18pt 0 8pt; }
h4 { font-family: 'NanumBarunGothic','NanumGothic',sans-serif; font-size: 10.3pt; font-weight: 700; color: #2b2b2b; margin: 12pt 0 4pt; page-break-after: avoid; }
ul, ol { margin: 0 0 7pt; padding-left: 14pt; }
li { margin-bottom: 2.5pt; }
blockquote { background: #eef3f9; border-left: 3pt solid #12355b; padding: 8pt 12pt; margin: 6pt 0 12pt; font-size: 10pt; }
blockquote strong { color: #12355b; }
th { background: #eef3f9; color: #12355b; border-top: 1pt solid #12355b; }
td strong { color: #12355b; }
figure { margin: 10pt 0 8pt; }
figcaption { color: #4a4a4a; }
em { color: #555; font-size: 9pt; }
"""

def _mathml(tex, block):  # LaTeX → MathML (pandoc)
    import pypandoc
    d = "$$" if block else "$"
    h = pypandoc.convert_text(d + tex + d, "html", format="markdown+tex_math_dollars", extra_args=["--mathml"])
    m = re.search(r"<math.*?</math>", h, flags=re.S)
    assert m, tex
    return m.group(0)
def math(s):  # $$…$$ 블록과 $…$ 인라인 수식 → MathML
    s = re.sub(r"\$\$(.+?)\$\$", lambda m: f'<div class="eq">{_mathml(m[1], True)}</div>', s, flags=re.S)
    s = re.sub(r"(?<![\\$])\$([^$\n]+?)\$", lambda m: _mathml(m[1], False), s)
    return s
def blocks(s):
    s = math(s)
    s = re.sub(r"^::: (\w+)\n(.*?)\n:::$", lambda m: f'<div class="{m[1]}">\n\n{m[2]}\n\n</div>', s, flags=re.M | re.S)
    def fig(m):
        p = ROOT / "figures" / f"{m[1]}.png"
        assert p.exists(), p
        b = base64.b64encode(p.read_bytes()).decode()
        return f'<figure><img src="data:image/png;base64,{b}"><figcaption>{m[2]}</figcaption></figure>'
    s = re.sub(r"\{\{([\w]+)\|(.*?)\}\}", fig, s)
    def fig2(m):  # 표준 마크다운 그림 + 이탤릭 캡션
        p = ROOT / m[2]
        assert p.exists(), p
        b = base64.b64encode(p.read_bytes()).decode()
        return f'<figure><img src="data:image/png;base64,{b}"><figcaption>{m[1]}</figcaption></figure>'
    s = re.sub(r"^!\[(.*?)\]\((figures/[\w]+\.png)\)\n\n\*.*?\*$", fig2, s, flags=re.M)
    m0 = re.match(r"# (.+)\n\n## (.+)\n\n\*\*(.+)\*\*\n", s)  # 표지
    if m0:
        s = f'<div class="cover"><p class="kicker">{m0[3]}</p><p class="title">{m0[1]}</p><p class="sub">{m0[2]}</p></div>\n\n' + s[m0.end():]
    s = re.sub(r"^## ([567]\. .*|붙임 1.*)$", lambda m: f'<h2 class="pb">{m[1]}</h2>', s, flags=re.M)  # 결과 장(5 · 6 · 7)과 붙임만 새 쪽  # 장마다 새 쪽
    s = re.sub(r"^## !(.*)$", lambda m: f'<h2 class="pb">{m[1]}</h2>', s, flags=re.M)
    return s
async def main(src, out, title):
    html = f"<!doctype html><html lang='ko'><head><meta charset='utf-8'><title>{title}</title><style>{CSS}</style></head><body>{MD.render(blocks(Path(src).read_text(encoding='utf-8')))}</body></html>"
    Path(out).with_suffix(".html").write_text(html, encoding="utf-8")
    async with async_playwright() as p:
        b = await p.chromium.launch(); pg = await b.new_page()
        await pg.set_content(html, wait_until="networkidle")
        foot = "<div style='font-size:8pt;width:100%;text-align:center;color:#555;font-family:NanumMyeongjo'><span class='pageNumber'></span></div>"
        await pg.pdf(path=out, format="A4", print_background=True, display_header_footer=True, header_template="<span></span>", footer_template=foot, margin=dict(top="19mm", bottom="19mm", left="20mm", right="20mm"))
        await b.close()
if __name__ == "__main__":
    asyncio.run(main(sys.argv[1], sys.argv[2], sys.argv[3] if len(sys.argv) > 3 else "중간 연구 보고"))
