from PIL import Image, ImageDraw
import os

size = 256
img = Image.new('RGBA', (size, size), (0,0,0,0))
d = ImageDraw.Draw(img)
# background circle
accent = (31, 111, 235, 255)  # #1f6feb
white = (255, 255, 255, 255)
# outer
d.ellipse((8,8,size-8,size-8), fill=accent)
# timer slot
d.rectangle((size*0.47, size*0.28, size*0.53, size*0.60), fill=white)
# subtle inner ring effect
for r in range(0,6):
    d.ellipse((16+r,16+r,size-16-r,size-16-r), outline=(255,255,255,20), width=1)

out_path = os.path.join(os.path.dirname(__file__), 'pomodro.ico')
img.save(out_path, format='ICO', sizes=[(16,16),(32,32),(48,48),(64,64),(128,128),(256,256)])
print('Icon written to', out_path)
