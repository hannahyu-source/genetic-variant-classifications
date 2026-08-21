"""
docs/analysis_report.md -> PDF 최종 보고서 생성
Markdown -> 스타일 적용된 HTML -> Chrome headless로 PDF 인쇄
"""
import subprocess
from pathlib import Path

import markdown

ROOT = Path(__file__).resolve().parents[2]
MD_PATH = ROOT / "docs" / "analysis_report.md"
HTML_PATH = ROOT / "docs" / "_report_build.html"
PDF_PATH = ROOT / "docs" / "analysis_report.pdf"

CHROME_CANDIDATES = [
    r"C:\Program Files\Google\Chrome\Application\chrome.exe",
    r"C:\Program Files (x86)\Google\Chrome\Application\chrome.exe",
    r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe",
]

CSS = """
@page { size: A4; margin: 20mm 18mm; }
body { font-family: 'Malgun Gothic', 'Segoe UI', sans-serif; color: #1a1a1a; line-height: 1.65; font-size: 10.5pt; }
.cover { text-align: center; padding-top: 34%; page-break-after: always; }
.cover h1 { font-size: 25pt; margin-bottom: 10pt; line-height: 1.4; }
.cover .subtitle { font-size: 13pt; color: #555; margin-bottom: 50pt; }
.cover .meta { font-size: 10.5pt; color: #888; }
h1 { font-size: 17pt; border-bottom: 2px solid #333; padding-bottom: 5pt; margin-top: 26pt; }
h2 { font-size: 13.5pt; color: #2c3e50; margin-top: 22pt; border-left: 4px solid #4C72B0; padding-left: 8pt; }
h3 { font-size: 11.5pt; color: #34495e; margin-top: 16pt; }
p { margin: 6pt 0; }
ul, ol { margin: 6pt 0; padding-left: 22pt; }
li { margin: 3pt 0; }
table { border-collapse: collapse; width: 100%; margin: 10pt 0; font-size: 9pt; }
th, td { border: 1px solid #ccc; padding: 4pt 7pt; text-align: left; }
th { background: #eef1f6; }
img { max-width: 92%; display: block; margin: 10pt auto; border: 1px solid #ddd; }
code { background: #f3f3f3; padding: 1pt 4pt; border-radius: 3pt; font-size: 9pt; }
blockquote { border-left: 3px solid #aaa; padding-left: 10pt; color: #555; font-size: 9.5pt; margin: 8pt 0; }
strong { color: #111; }
hr { border: none; border-top: 1px solid #ccc; margin: 18pt 0; }
"""


def main():
    md_text = MD_PATH.read_text(encoding="utf-8")
    body_html = markdown.markdown(md_text, extensions=["tables"])

    html = f"""<!DOCTYPE html>
<html lang="ko">
<head>
<meta charset="utf-8">
<title>ClinVar CADD_PHRED 회귀 예측 - 최종 분석 리포트</title>
<style>{CSS}</style>
</head>
<body>
<div class="cover">
  <h1>ClinVar 변이 병원성 점수(CADD_PHRED)<br>회귀 예측 분석 최종 보고서</h1>
  <div class="subtitle">유전 변이 특성 기반 회귀 · 분류 모델링 및 해석</div>
  <div class="meta">Genetic Variant Classifications Project</div>
</div>
{body_html}
</body>
</html>
"""
    HTML_PATH.write_text(html, encoding="utf-8")
    print(f"HTML 생성: {HTML_PATH}")

    chrome = next((p for p in CHROME_CANDIDATES if Path(p).exists()), None)
    if chrome is None:
        raise SystemExit("Chrome/Edge 실행파일을 찾지 못했습니다.")

    subprocess.run(
        [
            chrome, "--headless", "--disable-gpu",
            f"--print-to-pdf={PDF_PATH}",
            "--no-pdf-header-footer",
            HTML_PATH.as_uri(),
        ],
        check=True,
    )
    print(f"PDF 생성 완료: {PDF_PATH}")


if __name__ == "__main__":
    main()
