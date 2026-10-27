"""Render and check the two current reports using the bundled document runtime."""
import hashlib
import json
import re
from pathlib import Path
from zipfile import ZipFile
from PIL import Image, ImageDraw
from pypdf import PdfReader
from pdf2image import convert_from_path

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT/'audit/gemini_revision_render'
POPPLER = Path.home()/'.cache/codex-runtimes/codex-primary-runtime/dependencies/native/poppler/Library/bin'
results = {}
for name in ('DOCUMENTAZIONE_PROGETTO', 'PROJECT_DOCUMENTATION_EN'):
    path = ROOT/f'{name}.docx'
    with ZipFile(path) as package:
        xmls = '\n'.join(package.read(p).decode('utf-8') for p in package.namelist() if p.endswith('.xml'))
        assert not re.search(r'ollama|llama3|llm_chatbot_local|dashboard_local', xmls, re.I)
        assert '<wp:anchor' not in xmls
        assert '<a:srcRect' not in xmls
    pages = convert_from_path(OUT/f'{name}.pdf', dpi=110, poppler_path=str(POPPLER))
    folder = OUT/name
    folder.mkdir(exist_ok=True)
    for i, page in enumerate(pages, 1):
        page.save(folder/f'page-{i}.png')
    # Contact sheets make page sequence and large whitespace easy to audit.
    for start in range(0, len(pages), 6):
        sheet = Image.new('RGB', (960, 1380), 'white')
        draw = ImageDraw.Draw(sheet)
        for i in range(start, min(start+6, len(pages))):
            preview = pages[i].copy()
            preview.thumbnail((460, 425))
            x, y = ((i-start)%2)*480, ((i-start)//2)*460
            sheet.paste(preview, (x,y+22))
            draw.text((x+10,y+4), f'Page {i+1}', fill='black')
        sheet.save(folder/f'contact-{start//6+1}.png')
    pdf = PdfReader(OUT/f'{name}.pdf')
    results[name] = {
        'sha256': hashlib.sha256(path.read_bytes()).hexdigest(),
        'pages': len(pages),
        'comparison_section_pages': [i for i,p in enumerate(pdf.pages,1) if 'Compare configurations' in p.extract_text()],
        'gemini_section_pages': [i for i,p in enumerate(pdf.pages,1) if 'API Key Gemini' in p.extract_text()],
        'floating_images': False,
        'word_crop': False,
    }
assert (ROOT/'DOCUMENTAZIONE_PROGETTO.docx').read_bytes() == (ROOT/'DOCUMENTAZIONE_PROGETTO_CON_GUIDA.docx').read_bytes()
(OUT/'quality_check.json').write_text(json.dumps(results, indent=2), encoding='utf-8')
print(json.dumps(results, indent=2))
