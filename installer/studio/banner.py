"""Render the installer banner and its original architectural line art."""
from pathlib import Path
import math
from PIL import Image, ImageDraw, ImageFont

WIDTH, HEIGHT = 960, 308
S = 2
FONTS = Path('/usr/share/fonts/truetype/dejavu')
def font(size, bold=False, mono=False):
    name = 'DejaVuSansMono' if mono else 'DejaVuSans'
    return ImageFont.truetype(str(FONTS / (name + ('-Bold' if bold else '') + '.ttf')), size*S)

def create(progress=1.0, logo=None):
    im = Image.new('RGB', (WIDTH*S, HEIGHT*S))
    d = ImageDraw.Draw(im)
    for y in range(HEIGHT*S):
        t=y/(HEIGHT*S)
        d.line((0,y,WIDTH*S,y),fill=(int(11+3*t),int(25+11*t),int(41+14*t)))
    def line(p, color, width=1):
        d.line([(round(x*S),round(y*S)) for x,y in p], fill=color, width=max(1,round(width*S)))
    def text(x,y,s,size,color,bold=False,mono=False):
        d.text((x*S,y*S),s,font=font(size,bold,mono),fill=color)
    def dot(x,y,r,c):
        d.ellipse(((x-r)*S,(y-r)*S,(x+r)*S,(y+r)*S),fill=c)
    for x in range(0,WIDTH,24):line([(x,0),(x,HEIGHT)],'#172e45',.5)
    for y in range(0,HEIGHT,24):line([(0,y),(WIDTH,y)],'#172e45',.5)
    def p(x,y,z=0):return (694+29*x-21*y,184+10*x+10*y-21*z)
    for i in range(-6,7):
        line([p(i,-6),p(i,6)],'#254760',.6)
        line([p(-6,i),p(6,i)],'#254760',.6)
    for a,b,c,e in [(-3.5,-2.5,3.5,2.5),(-4,-3,4,3)]:
        line([p(a,b),p(c,b),p(c,e),p(a,e),p(a,b)],'#46728b',.8)
    def stroke(points,color,w=1):
        line([p(*pt) for pt in points],color,w)
    for k in range(7):
        a,b,c,e=(-3,-2,3,2) if k<=4 else (-2,-1.5,2,1.5)
        outline=[(a,b,k),(c,b,k),(c,e,k),(a,e,k),(a,b,k)]
        stroke(outline,'#294961',.65)
        stage=max(0,min(1,progress*7-k))
        if stage<=0:continue
        if k:
            for x in (a,0,c):
                for y in (b,e):
                    stroke([(x,y,k-1),(x,y,k-1+stage)],'#4e9cbd',.85)
            for x in (a,c):
                for j in range(1,5):
                    y=b+(e-b)*j/5
                    stroke([(x,y,k-1),(x,y,k-1+stage)],'#367088',.55)
            for y in (b,e):
                for j in range(1,8):
                    x=a+(c-a)*j/8
                    stroke([(x,y,k-1),(x,y,k-1+stage)],'#397c97',.55)
        for i in range(4):
            a0,b0=outline[i:i+2]
            t=max(0,min(1,stage*4-i))
            if t:stroke([a0,tuple(a0[j]+(b0[j]-a0[j])*t for j in range(3))],'#66e4df' if stage<1 else '#70bcda',1.3)
        if stage>=1:
            for x,y,z in outline[:-1]:
                u,v=p(x,y,z);dot(u,v,1.55,'#9df9e9')
    # Survey markers and a construction axis, deliberately quiet behind the copy.
    for x,y in ((471,62),(904,59),(876,251),(471,250)):
        line([(x-5,y),(x+5,y)],'#5a819a',.7);line([(x,y-5),(x,y+5)],'#5a819a',.7)
    line([(466,279),(908,279)],'#36576f',.65)
    text(468,286,'AXONOMETRIC  /  STRUCTURAL STUDY',9,'#a1bacd',mono=True)
    text(850,286,'FIG. 01',9,'#a1bacd',mono=True)
    # Quiet the grid beneath type.
    overlay=Image.new('RGBA',im.size)
    od=ImageDraw.Draw(overlay)
    for x in range(470*S):
        a=round(180*(1-(x/(470*S))**3))
        od.line((x,0,x,HEIGHT*S),fill=(10,22,36,a))
    im=Image.alpha_composite(im.convert('RGBA'),overlay)
    d=ImageDraw.Draw(im)
    line([(36,34),(62,34)],'#69e5d7',2)
    text(73,27,'D E S K T O P   S E T U P',12,'#8be7de',True,True)
    if logo:
        asset=Image.open(logo).convert('RGBA')
        asset.thumbnail((70*S,70*S),Image.Resampling.LANCZOS)
        im.alpha_composite(asset,(35*S,75*S))
        text(115,71,"PY.cad",60,"#0bd7d9",True)
    else:
        text(32,65,'PY.cad',63,'#f0f8ff',True)
    text(37,160,'Precision drafting',27,'#f0f8ff',True)
    text(38,200,'Set up your CAD workspace.',16,'#a9c2d5')
    line([(37,245),(397,245)],'#375971',.8)
    text(38,257,'DRAWING  /  MODELING  /  DOCUMENTATION',10,'#83a8bf',mono=True)
    return im.convert('RGB').resize((WIDTH,HEIGHT),Image.Resampling.LANCZOS)

if __name__=='__main__':
    import argparse
    parser=argparse.ArgumentParser()
    parser.add_argument('destination',type=Path)
    parser.add_argument('--logo',type=Path,help='Path to the PY.cad icon PNG')
    parser.add_argument('--installer',action='store_true',help='Generate the native setup assets')
    args=parser.parse_args()
    args.destination.mkdir(parents=True,exist_ok=True)
    if args.installer:
        frames=[create(n/24,args.logo).resize((752,241),Image.Resampling.LANCZOS) for n in range(25)]
        frames[-1].save(args.destination/'banner.png',optimize=True)
        frames[0].save(args.destination/'construction.gif',save_all=True,append_images=frames[1:],duration=65,optimize=True)
    else:
        for n in range(25):
            create(n/24,args.logo).save(args.destination/f'frame-{n:02d}.png',optimize=True)
