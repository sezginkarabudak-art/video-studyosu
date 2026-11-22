# -*- coding: utf-8 -*-
"""
Video Studyosu V4 - API'siz görsel kompozisyon + video üretimi
Not: Görseller, Pillow ile oluşturulan özgün grafik kompozisyonlardır; AI image generation değildir.
"""
import os, sys, json, math, random, threading, subprocess, shutil, re, time, urllib.request, zipfile, tempfile
from pathlib import Path
import tkinter as tk
from tkinter import ttk, filedialog, messagebox

APP_NAME = "Karabudak Film Stüdyoları V5.5.1"
APP_VERSION = "5.5.1"
 
PLATFORM_PROFILES = {
    "YouTube yatay video": {"size": (1920,1080), "ratio": "16:9", "fps": 30, "format": "MP4 / H.264 / AAC", "max_seconds": None},
    "YouTube Shorts": {"size": (1080,1920), "ratio": "9:16", "fps": 30, "format": "MP4 / H.264 / AAC", "max_seconds": 180},
    "Instagram Reels": {"size": (1080,1920), "ratio": "9:16", "fps": 30, "format": "MP4 / H.264 / AAC", "max_seconds": 1200},
    "Instagram Hikâye": {"size": (1080,1920), "ratio": "9:16", "fps": 30, "format": "MP4 / H.264 / AAC", "max_seconds": 60},
    "TikTok": {"size": (1080,1920), "ratio": "9:16", "fps": 30, "format": "MP4 / H.264 / AAC", "max_seconds": 3600},
    "Diğer dikey kısa video": {"size": (1080,1920), "ratio": "9:16", "fps": 30, "format": "MP4 / H.264 / AAC", "max_seconds": None},
    "Özel format": {"size": (1920,1080), "ratio": "16:9", "fps": 30, "format": "MP4 / H.264 / AAC", "max_seconds": None},
}

def platform_profile(name):
    return PLATFORM_PROFILES.get(name, PLATFORM_PROFILES["Özel format"])

GITHUB_REPO = "sezginkarabudak-art/video-studyosu"
UPDATE_ASSET = "VideoStudyosu_Update.zip"
HOME = Path.home()
OUT_ROOT = HOME / "Desktop" / "VideoStudyo_Ciktilar"
PROJECT_ROOT = HOME / "Documents" / "VideoStudyo_Projeler"
OUT_ROOT.mkdir(parents=True, exist_ok=True)
PROJECT_ROOT.mkdir(parents=True, exist_ok=True)

def install_imports():
    missing = []
    for mod, pkg in [("PIL", "Pillow"), ("imageio_ffmpeg", "imageio-ffmpeg")]:
        try: __import__(mod)
        except Exception: missing.append(pkg)
    if missing:
        subprocess.check_call([sys.executable, "-m", "pip", "install", *missing])

try:
    from PIL import Image, ImageDraw, ImageFont, ImageFilter, ImageTk
    import imageio_ffmpeg
except Exception:
    install_imports()
    from PIL import Image, ImageDraw, ImageFont, ImageFilter, ImageTk
    import imageio_ffmpeg

def ffmpeg():
    return imageio_ffmpeg.get_ffmpeg_exe()

def safe_name(s):
    s = re.sub(r'[<>:"/\\\\|?*]', "_", (s or "Video").strip())
    return s[:70] or "Video"

def font(size, bold=False):
    candidates = [
        r"C:\Windows\Fonts\arialbd.ttf" if bold else r"C:\Windows\Fonts\arial.ttf",
        r"C:\Windows\Fonts\segoeuib.ttf" if bold else r"C:\Windows\Fonts\segoeui.ttf",
        "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf" if bold else "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"
    ]
    for p in candidates:
        if os.path.exists(p):
            try: return ImageFont.truetype(p, size)
            except: pass
    return ImageFont.load_default()

def split_scenes(script):
    parts = [x.strip() for x in re.split(r"\n\s*\n", script.strip()) if x.strip()]
    if not parts and script.strip(): parts = [script.strip()]
    result = []
    for p in parts:
        while len(p) > 650:
            cut = p.rfind(". ", 0, 600)
            if cut < 180: cut = p.rfind(" ", 0, 600)
            if cut < 1: cut = 600
            result.append(p[:cut+1].strip())
            p = p[cut+1:].strip()
        if p: result.append(p)
    return [{"text": x, "image": "", "audio": "", "visual_request": ""} for x in result]

def palette_for(text):
    t = text.lower()
    if any(k in t for k in ["korku","cin","hayalet","karanlık","gece","mezar","lanet","ölüm"]):
        return ((7, 10, 23), (54, 42, 67), "horror")
    if any(k in t for k in ["orman","ağaç","dağ","doğa","nehir"]):
        return ((8, 35, 31), (74, 100, 69), "nature")
    if any(k in t for k in ["tarih","osmanlı","saray","sultan","padişah","savaş"]):
        return ((38, 24, 18), (139, 91, 49), "history")
    if any(k in t for k in ["uzay","gezegen","yıldız","galaksi"]):
        return ((5, 9, 38), (55, 39, 105), "space")
    if any(k in t for k in ["komik","gül","eğlence"]):
        return ((39, 22, 10), (180, 111, 37), "comedy")
    return ((13, 25, 42), (56, 83, 105), "cinematic")

def interpret_scene_request(text, request=""):
    """API'siz yerel sahne asistanı: değişiklik isteğini görsel kurallara dönüştürür."""
    r = (request or "").lower()
    notes = []
    style = {"dark": 0, "fog": 0, "rain": 0, "warm": 0, "red": 0, "moon": 0,
             "silhouette": 0, "stars": 0, "bright": 0}
    if any(k in r for k in ["daha karanlık", "karanlık yap", "gece olsun", "ışığı azalt"]):
        style["dark"] += 1; notes.append("karanlık artırıldı")
    if any(k in r for k in ["sis", "pus", "duman"]):
        style["fog"] += 2; notes.append("sis eklendi")
    if any(k in r for k in ["yağmur", "ıslak", "sağanak"]):
        style["rain"] += 1; notes.append("yağmur efekti eklendi")
    if any(k in r for k in ["sıcak", "mum", "ateş", "turuncu", "sarı ışık"]):
        style["warm"] += 1; notes.append("sıcak ışık eklendi")
    if any(k in r for k in ["kırmızı", "kan kırmızısı"]):
        style["red"] += 1; notes.append("kırmızı vurgu eklendi")
    if any(k in r for k in ["ay", "ay ışığı", "dolunay"]):
        style["moon"] += 1; notes.append("ay eklendi")
    if any(k in r for k in ["siluet", "kadın", "adam", "insan", "gölge", "figür"]):
        style["silhouette"] += 1; notes.append("uzak figür/siluet eklendi")
    if any(k in r for k in ["yıldız", "galaksi", "uzay"]):
        style["stars"] += 1; notes.append("yıldızlar artırıldı")
    if any(k in r for k in ["aydınlık", "gündüz", "daha açık", "ışığı artır"]):
        style["bright"] += 1; notes.append("aydınlık artırıldı")
    # Mekânı değiştirme isteği için metin + istek birlikte sınıflandırılır.
    combined = text + " " + request
    c1,c2,kind = palette_for(combined)
    return c1,c2,kind,style,notes

def draw_scene_subjects(draw, text, w, h, kind, seed):
    """Sahne metnindeki mekân ve nesne ipuçlarına göre ayrı kompozisyonlar çizer."""
    t=(text or "").lower()
    rng=random.Random(seed + sum(ord(ch) for ch in t[:180]))
    def ln(points, fill=(5,5,8,235), width=5):
        draw.line(points, fill=fill, width=width)
    if any(k in t for k in ["koridor","oda","içeri girdi","kapıyı aç","evin içinde"]):
        van=(int(w*.52),int(h*.40))
        ln([(0,int(h*.08)),van,(w,int(h*.08))],(8,8,12,230),12)
        ln([(0,int(h*.82)),van,(w,int(h*.82))],(8,8,12,230),14)
        draw.rectangle((int(w*.67),int(h*.20),int(w*.87),int(h*.72)),fill=(5,6,10,245),outline=(130,115,95,220),width=5)
        draw.rectangle((int(w*.71),int(h*.25),int(w*.83),int(h*.70)),fill=(1,2,5,255))
        for j in range(6):
            y=int(h*(.58+j*.04)); ln([(0,y),(w,y)],(110,95,75,35),2)
    elif any(k in t for k in ["yol","sokak","cadde","araba","patika","köye doğru"]):
        van=(int(w*.50),int(h*.39))
        draw.polygon([(int(w*.29),h),(int(w*.71),h),van],fill=(18,19,23,245))
        ln([(int(w*.29),h),van,(int(w*.71),h)],(145,140,125,140),3)
        for side in [0,1]:
            x=int(w*(.08 if side==0 else .92))
            for j in range(6):
                y=int(h*(.35+j*.09))
                ln([(x,y),(x+rng.randint(-40,40),y-rng.randint(45,100))],(3,10,9,245),rng.randint(5,13))
    elif any(k in t for k in ["pencere","camdan","perde","siluet"]):
        draw.rectangle((int(w*.22),int(h*.12),int(w*.78),int(h*.78)),fill=(5,8,15,245),outline=(130,130,135,220),width=9)
        ln([(int(w*.5),int(h*.13)),(int(w*.5),int(h*.77))],(145,145,150,190),5)
        ln([(int(w*.23),int(h*.45)),(int(w*.77),int(h*.45))],(145,145,150,190),5)
        draw.ellipse((int(w*.45),int(h*.28),int(w*.56),int(h*.52)),fill=(1,2,5,255))
        draw.polygon([(int(w*.40),int(h*.77)),(int(w*.43),int(h*.49)),(int(w*.57),int(h*.49)),(int(w*.62),int(h*.77))],fill=(1,2,5,255))
    elif any(k in t for k in ["bebek","oyuncak","kukla"]):
        cx,cy=int(w*.5),int(h*.67); rr=int(min(w,h)*.09)
        draw.ellipse((cx-rr,cy-2*rr,cx+rr,cy),fill=(190,165,135,245),outline=(25,20,20,255),width=4)
        draw.ellipse((cx-rr*.48,cy-rr,cx-rr*.20,cy-rr*.72),fill=(5,5,8,255))
        draw.ellipse((cx+rr*.20,cy-rr,cx+rr*.48,cy-rr*.72),fill=(5,5,8,255))
        draw.polygon([(cx-rr,cy-rr*.1),(cx+rr,cy-rr*.1),(cx+rr*1.4,cy+rr*2),(cx-rr*1.4,cy+rr*2)],fill=(45,35,38,245))
    elif any(k in t for k in ["orman","ağaç","çalılık"]):
        for j in range(20):
            x=rng.randint(-20,w+20); top=rng.randint(int(h*.1),int(h*.5)); base=rng.randint(int(h*.68),h)
            draw.polygon([(x,top),(x-rng.randint(25,70),base),(x+rng.randint(25,70),base)],fill=(3,20,15,240))
    elif any(k in t for k in ["mezar","mezarlık","tabut"]):
        for j in range(7):
            x=int(w*(.06+j*.13)); y=int(h*(.63+rng.random()*.1)); ww=int(w*.07); hh=int(h*.18)
            draw.rounded_rectangle((x,y,x+ww,y+hh),radius=12,fill=(55,58,62,245),outline=(160,160,155,180),width=3)
    elif any(k in t for k in ["saray","padişah","sultan","osmanlı"]):
        draw.rectangle((int(w*.25),int(h*.35),int(w*.75),int(h*.82)),fill=(65,43,30,245),outline=(190,145,80,220),width=5)
        for x in [int(w*.34),int(w*.50),int(w*.66)]:
            draw.ellipse((x-int(w*.045),int(h*.18),x+int(w*.045),int(h*.4)),fill=(90,55,35,245),outline=(205,165,95,210),width=4)
    elif any(k in t for k in ["deniz","sahil","gemi","tekne","dalga"]):
        draw.rectangle((0,int(h*.53),w,h),fill=(8,35,55,235))
        for j in range(12):
            y=int(h*(.58+j*.025)); ln([(rng.randint(0,w//3),y),(rng.randint(w//2,w),y)],(130,180,195,100),2)
    elif any(k in t for k in ["koş","kaç","geldi","gördü","bekliy","yaklaştı","adam","kadın","çocuk","insan"]):
        cx,cy=int(w*.52),int(h*.68); rr=int(min(w,h)*.045)
        draw.ellipse((cx-rr,cy-3*rr,cx+rr,cy-rr),fill=(2,4,8,250))
        draw.polygon([(cx-rr,cy-rr),(cx+rr,cy-rr),(cx+2*rr,cy+2*rr),(cx-2*rr,cy+2*rr)],fill=(2,4,8,250))
        ln([(cx-rr,cy+rr),(cx-3*rr,cy+3*rr)],(2,4,8,255),max(5,rr//2))
        ln([(cx+rr,cy+rr),(cx+3*rr,cy+3*rr)],(2,4,8,255),max(5,rr//2))


def make_original_visual(text, path, size=(1280,720), seed=0, request="", draw_text=True):
    """API'siz, Pillow tabanlı özgün atmosferik grafik kompozisyonu."""
    w,h=size
    random.seed(seed + sum(ord(c) for c in (text + request)[:120]))
    c1,c2,kind,style,notes = interpret_scene_request(text, request)
    if style["red"]:
        c2=(105,28,36)
    if style["warm"]:
        c2=(145,91,48)
    if style["bright"]:
        c1=tuple(min(90,x+25) for x in c1)
        c2=tuple(min(210,x+35) for x in c2)
    if style["dark"]:
        c1=tuple(max(0,int(x*.55)) for x in c1)
        c2=tuple(max(0,int(x*.65)) for x in c2)
    # Hizli dikey gradient: piksel-piksel Python dongusu yerine Pillow cizimi.
    im = Image.new("RGB", (w,h))
    d0 = ImageDraw.Draw(im)
    for y in range(h):
        v = y / max(1,h-1)
        color = tuple(max(0,min(255,int(c1[i]*(1-v)+c2[i]*v))) for i in range(3))
        d0.line((0,y,w,y), fill=color)
    # Sinematik merkez isigi ve kenar karartmasi.
    glow = Image.new("RGBA",(w,h),(0,0,0,0))
    gd = ImageDraw.Draw(glow)
    gd.ellipse((int(w*.18),int(h*.02),int(w*.90),int(h*.92)), fill=(235,220,190,28))
    glow = glow.filter(ImageFilter.GaussianBlur(max(24,int(min(w,h)*.10))))
    im = Image.alpha_composite(im.convert("RGBA"),glow).convert("RGB")
    d = ImageDraw.Draw(im, "RGBA")
    # Atmospheric particles / stars
    for _ in range(170):
        x,y = random.randrange(w), random.randrange(h)
        r = random.choice([1,1,2,3])
        alpha = random.randint(20,100)
        d.ellipse((x-r,y-r,x+r,y+r), fill=(220,220,210,alpha))
    # Horizon and silhouettes
    horizon = int(h*.73)
    d.rectangle((0,horizon,w,h), fill=(3,5,9,115))
    if kind in ("horror","history"):
        # distant building / mansion silhouette
        bx, by = int(w*.60), int(h*.37)
        d.rectangle((bx,by,bx+int(w*.28),horizon), fill=(5,7,12,210))
        d.polygon([(bx-25,by),(bx+int(w*.14),by-int(h*.17)),(bx+int(w*.30),by)], fill=(4,5,10,230))
        for wx in range(bx+35,bx+int(w*.27),55):
            d.rectangle((wx,by+55,wx+22,by+100), fill=(220,155,75,150))
        # foreground tree branches
        for side in [0,w]:
            x0=side
            for j in range(7):
                yy=int(h*.38+j*35)
                x1 = x0 + (1 if side==0 else -1)*random.randint(80,230)
                d.line((x0,yy,x1,yy-random.randint(50,150)), fill=(2,5,7,220), width=random.randint(5,13))
    elif kind == "nature":
        for i in range(16):
            x=random.randint(-30,w+30); base=horizon+random.randint(0,70)
            top=random.randint(int(h*.18),int(h*.52))
            d.polygon([(x,base),(x-random.randint(25,65),base),(x,top),(x+random.randint(25,65),base)], fill=(3,18,17,210))
    elif kind == "space":
        for _ in range(60):
            x,y=random.randrange(w),random.randrange(horizon)
            d.ellipse((x,y,x+random.randint(2,5),y+random.randint(2,5)), fill=(240,235,255,180))
        d.ellipse((int(w*.68),int(h*.12),int(w*.84),int(h*.40)), fill=(170,155,210,150))
    else:
        # subtle cinematic architecture blocks
        d.rectangle((int(w*.68),int(h*.35),int(w*.94),horizon), fill=(5,9,14,90))
        d.rectangle((int(w*.72),int(h*.43),int(w*.77),int(h*.61)), fill=(230,185,110,70))
    # Fog bands
    fog = Image.new("RGBA",(w,h),(0,0,0,0)); fd=ImageDraw.Draw(fog)
    fog_count = 12 if style["fog"] else 7
    for i in range(fog_count):
        y=int(h*.48+i*24)
        alpha = random.randint(18,42) if style["fog"] else random.randint(10,28)
        fd.ellipse((-100,y-35,w+100,y+45), fill=(190,200,205,alpha))
    fog=fog.filter(ImageFilter.GaussianBlur(28))
    im=Image.alpha_composite(im.convert("RGBA"),fog).convert("RGB")
    overlay=Image.new("RGBA",(w,h),(0,0,0,0)); od=ImageDraw.Draw(overlay)
    if style["moon"]:
        mx,my=int(w*.19),int(h*.20); mr=int(min(w,h)*.075)
        od.ellipse((mx-mr,my-mr,mx+mr,my+mr),fill=(238,232,205,220))
    if style["silhouette"]:
        sx,sy=int(w*.48),int(h*.70)
        od.ellipse((sx-24,sy-145,sx+24,sy-97),fill=(3,4,8,235))
        od.polygon([(sx-24,sy-100),(sx+24,sy-100),(sx+48,sy+20),(sx-48,sy+20)],fill=(3,4,8,235))
    if style["rain"]:
        for _ in range(260):
            x=random.randrange(w); y=random.randrange(h)
            od.line((x,y,x-12,y+32),fill=(180,205,220,90),width=2)
    if style["red"]:
        od.rectangle((0,0,w,h),fill=(100,0,10,18))
    im=Image.alpha_composite(im.convert("RGBA"),overlay).convert("RGB")
    # Her sahneye metin tabanli ayri on plan kompozisyonu ekle.
    draw_scene_subjects(ImageDraw.Draw(im, "RGBA"), text + " " + request, w, h, kind, seed)
    # Optional original Turkish scene label; disabled during video rendering
    # because the selected subtitle language is composited separately.
    if draw_text:
        d=ImageDraw.Draw(im,"RGBA")
        d.rectangle((0,int(h*.82),w,h), fill=(0,0,0,105))
        excerpt=text.strip().replace("\\n"," ")
        if len(excerpt)>105: excerpt=excerpt[:102]+"..."
        f=font(max(22,int(w/48)),True)
        d.text((int(w*.055),int(h*.855)),excerpt,fill=(245,242,232,235),font=f)
    im.save(path, quality=94)

def fit_image(src, size):
    w,h=size
    im=Image.open(src).convert("RGB")
    scale=max(w/im.width,h/im.height)
    nw,nh=int(im.width*scale),int(im.height*scale)
    im=im.resize((nw,nh),Image.Resampling.LANCZOS)
    x=(nw-w)//2; y=(nh-h)//2
    return im.crop((x,y,x+w,y+h))

def make_motion_preview_frame(source, frame_no, frame_count=72):
    """Creates a lightweight animated cinematic preview from the scene still."""
    base=source.convert("RGB")
    w,h=base.size
    phase=(frame_no % frame_count)/max(1,frame_count)
    zoom=1.0+0.035*(0.5-0.5*math.cos(phase*2*math.pi))
    cw,ch=max(1,int(w/zoom)),max(1,int(h/zoom))
    dx=int((w-cw)*(0.5+0.18*math.sin(phase*2*math.pi)))
    dy=int((h-ch)*(0.5+0.12*math.cos(phase*2*math.pi)))
    frame=base.crop((dx,dy,dx+cw,dy+ch)).resize((w,h),Image.Resampling.LANCZOS).convert("RGBA")
    atmosphere=Image.new("RGBA",(w,h),(0,0,0,0))
    ad=ImageDraw.Draw(atmosphere)
    for band in range(4):
        y=int(h*(0.48+band*0.12+0.025*math.sin(phase*2*math.pi+band)))
        ad.ellipse((-int(w*.18),y-int(h*.045),int(w*1.18),y+int(h*.045)),fill=(185,205,215,18))
    for j in range(34):
        x=int(((j*0.61803398875+phase*0.10)%1.0)*w)
        y=int(((j*0.38196601125+phase*0.035)%1.0)*h)
        r=1+(j%3==0)
        ad.ellipse((x-r,y-r,x+r,y+r),fill=(225,230,235,65+(j%4)*18))
    atmosphere=atmosphere.filter(ImageFilter.GaussianBlur(max(2,int(min(w,h)*0.006))))
    return Image.alpha_composite(frame,atmosphere).convert("RGB")


def run_ffmpeg(args):
    cmd=[ffmpeg(), "-y", *args]
    p=subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
    if p.returncode:
        detail = (p.stderr or p.stdout or "").strip()
        if not detail:
            detail = "FFmpeg beklenmeyen bir hata koduyla kapandı."
        raise RuntimeError("FFmpeg işlemi başarısız oldu.\\n\\n" + detail[-3500:])


SUBTITLE_LANGUAGES = {
    "Türkçe": "tr",
    "İngilizce": "en",
    "Korece": "ko",
    "İtalyanca": "it",
    "Almanca": "de",
    "Fransızca": "fr",
    "İspanyolca": "es",
    "Japonca": "ja",
    "Arapça": "ar",
    "Rusça": "ru",
    "Çince": "zh-CN",
}

def translate_caption(text, target_code):
    if target_code == "tr":
        return text
    try:
        from deep_translator import GoogleTranslator
    except Exception:
        subprocess.check_call([sys.executable, "-m", "pip", "install", "deep-translator"])
        from deep_translator import GoogleTranslator
    try:
        translated = GoogleTranslator(source="auto", target=target_code).translate(text)
        return translated or text
    except Exception:
        # Ceviri servisi erisilemezse video uretimini durdurma.
        return text

def add_subtitle_to_image(image_path, subtitle, target_path):
    im = Image.open(image_path).convert("RGBA")
    w, h = im.size
    overlay = Image.new("RGBA", (w, h), (0, 0, 0, 0))
    d = ImageDraw.Draw(overlay)
    f = font(max(22, int(w / 32)), True)
    max_width = int(w * 0.88)
    words = (subtitle or "").split()
    lines, line = [], ""
    for word in words:
        test = (line + " " + word).strip()
        if d.textbbox((0,0), test, font=f)[2] <= max_width:
            line = test
        else:
            if line: lines.append(line)
            line = word
    if line: lines.append(line)
    lines = lines[:4]
    line_h = max(32, int(h * 0.055))
    pad = max(14, int(w * 0.018))
    box_h = len(lines) * line_h + pad * 2
    y0 = h - box_h - int(h * 0.045)
    d.rounded_rectangle((int(w*.04), y0, int(w*.96), h-int(h*.025)),
                        radius=18, fill=(0,0,0,185))
    y = y0 + pad
    for line in lines:
        bb=d.textbbox((0,0),line,font=f,stroke_width=2)
        x=(w-(bb[2]-bb[0]))//2
        d.text((x,y),line,font=f,fill=(255,255,255,255),
               stroke_width=2,stroke_fill=(0,0,0,255))
        y += line_h
    Image.alpha_composite(im, overlay).convert("RGB").save(target_path, quality=95)

def add_character_reference(image_path, character, output_path, slot=0, total=1):
    """Composites a transparent full-body character into the scene.
    Opaque portrait photos retain the legacy circular reference-card behavior.
    """
    im=Image.open(image_path).convert("RGBA")
    ref=character.get("image","")
    if not ref or not Path(ref).exists():
        im.convert("RGB").save(output_path,quality=94); return output_path

    portrait=Image.open(ref).convert("RGBA")
    w,h=im.size
    total=max(1,int(total))
    has_transparency=(portrait.getchannel("A").getextrema()[0] < 255)

    if has_transparency:
        # Transparent PNG/WebP assets are treated as actual scene characters,
        # not as small profile badges. Keep the complete silhouette visible.
        alpha=portrait.getchannel("A")
        bbox=alpha.getbbox()
        if bbox:
            portrait=portrait.crop(bbox)
        target_h=int(h*0.78)
        scale=min(target_h/max(1,portrait.height), (w*0.34)/max(1,portrait.width))
        nw=max(1,int(portrait.width*scale)); nh=max(1,int(portrait.height*scale))
        portrait=portrait.resize((nw,nh),Image.Resampling.LANCZOS)
        # Alternate sides for multiple characters and keep them inside frame.
        margin=max(12,int(w*.035))
        if total==1:
            x=w-nw-margin
        elif slot % 2 == 0:
            x=margin+(slot//2)*int(nw*.62)
        else:
            x=w-nw-margin-(slot//2)*int(nw*.62)
        x=max(0,min(w-nw,x)); y=max(0,h-nh)
        # Soft grounding shadow under the character for a less pasted-on look.
        shadow=Image.new("RGBA",(nw,nh),(0,0,0,0))
        shadow_alpha=portrait.getchannel("A").filter(ImageFilter.GaussianBlur(max(3,int(min(nw,nh)*.035))))
        shadow_alpha=shadow_alpha.point(lambda value:int(value*.48))
        shadow.putalpha(shadow_alpha)
        shadow_layer=Image.new("RGBA",im.size,(0,0,0,0))
        shadow_layer.alpha_composite(shadow,(x+max(2,int(nw*.025)),y+max(3,int(nh*.012))))
        im=Image.alpha_composite(im,shadow_layer)
        layer=Image.new("RGBA",im.size,(0,0,0,0))
        layer.alpha_composite(portrait,(x,y))
        im=Image.alpha_composite(im,layer)
    else:
        # Opaque headshots cannot be cleanly separated from their background
        # without a segmentation model; preserve them as labeled reference cards.
        box=max(70,int(min(w,h)*0.22/(total**0.28)))
        side=min(portrait.size)
        x0=(portrait.width-side)//2; y0=(portrait.height-side)//2
        portrait=portrait.crop((x0,y0,x0+side,y0+side)).resize((box,box),Image.Resampling.LANCZOS)
        mask=Image.new("L",(box,box),0); md=ImageDraw.Draw(mask)
        md.ellipse((2,2,box-2,box-2),fill=255)
        portrait.putalpha(mask)
        pad=max(12,int(w*.018)); px=pad+slot*(box+pad); py=h-box-pad
        overlay=Image.new("RGBA",im.size,(0,0,0,0)); od=ImageDraw.Draw(overlay)
        od.ellipse((px-5,py-5,px+box+5,py+box+5),fill=(0,0,0,180),outline=(245,240,225,220),width=4)
        overlay.alpha_composite(portrait,(px,py))
        label=(character.get("name") or "Karakter")[:24]
        f=font(max(16,int(w/70)),True)
        bb=od.textbbox((0,0),label,font=f); tw=bb[2]-bb[0]
        od.rounded_rectangle((px,py+box+8,px+tw+24,py+box+48),radius=10,fill=(0,0,0,170))
        od.text((px+12,py+box+12),label,font=f,fill=(255,255,255,245))
        im=Image.alpha_composite(im,overlay)

    im.convert("RGB").save(output_path,quality=94)
    return output_path
def main():
    log_dir = Path(os.environ.get("LOCALAPPDATA", str(Path.home()))) / "VideoStudyosu"
    log_dir.mkdir(parents=True, exist_ok=True)
    log_path = log_dir / "startup.log"
    try:
        with open(log_path, "a", encoding="utf-8") as log:
            log.write(f"\\n--- START {time.strftime('%Y-%m-%d %H:%M:%S')} | version {APP_VERSION} ---\\n")
        root = tk.Tk()
        app = VideoStudio(root)
        # Otomatik arka plan guncellemesi gecici olarak kapatildi.
        # Guncelleme yalnizca kullanicinin MENÜ > Guncelleme secimiyle baslatilir.
        root.mainloop()
    except Exception:
        import traceback
        error = traceback.format_exc()
        try:
            with open(log_path, "a", encoding="utf-8") as log:
                log.write(error + "\\n")
        except Exception:
            pass
        try:
            fallback = tk.Tk()
            fallback.withdraw()
            messagebox.showerror("Video Studyosu acilamadi", "Program acilirken hata olustu. Hata kaydi: " + str(log_path) + "\\n\\n" + error[-1800:])
            fallback.destroy()
        except Exception:
            pass

if __name__=="__main__":
    main()
