from PIL import Image, ImageDraw
from pathlib import Path
p = Path('audit/quality_update_2026-11-05/render')
thumbs = []
for path in sorted(p.glob('page-*.png')):
    thumbs.append(Image.open(path).resize((306,432)))
for start in range(0,len(thumbs),8):
    sheet=Image.new('RGB',(1224,904),'#bbb')
    draw=ImageDraw.Draw(sheet)
    for j,im in enumerate(thumbs[start:start+8]):
        x=(j%4)*306
        y=(j//4)*452
        sheet.paste(im,(x,y+20))
        draw.text((x+5,y+3),str(start+j+1),fill='black')
    sheet.save(p/f'sheet-{start//8+1}.png')
