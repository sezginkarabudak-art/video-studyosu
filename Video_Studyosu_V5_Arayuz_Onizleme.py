# -*- coding: utf-8 -*-
"""
Video Studyosu V4 - API'siz görsel kompozisyon + video üretimi
Not: Görseller, Pillow ile oluşturulan özgün grafik kompozisyonlardır; AI image generation değildir.
"""
import os, sys, json, math, random, hashlib, threading, subprocess, shutil, re, time, urllib.request, urllib.parse, urllib.error, zipfile, tempfile, io, concurrent.futures, copy
from pathlib import Path
import tkinter as tk
from tkinter import ttk, filedialog, messagebox
from video_effects import get_video_effect_filter, VIDEO_EFFECT_PRESETS

APP_NAME = "Karabudak Film Stüdyoları V5.7.2"
APP_VERSION = "5.7.2"
 
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

def remove_image_background(source_path, output_path):
    """Optional local AI cutout using the open-source rembg package."""
    try:
        from rembg import remove
    except ImportError:
        subprocess.check_call([sys.executable, "-m", "pip", "install", "rembg[cpu]"])
        from rembg import remove
    with open(source_path, "rb") as src:
        result = remove(src.read())
    with open(output_path, "wb") as dst:
        dst.write(result)
    # Verify that the result really contains transparency before using it.
    with Image.open(output_path) as check:
        check.verify()
    return output_path


def build_character_consistency_prompt(scene, characters):
    """Build stable identity and wardrobe-lock cues from the saved character bible."""
    ids=scene.get("character_ids")
    if not isinstance(ids,list):
        old=scene.get("character_id")
        ids=[old] if isinstance(old,int) else []
    details=[]
    for idx in ids:
        if not isinstance(idx,int) or idx<0 or idx>=len(characters):
            continue
        item=characters[idx]
        name=(item.get("name") or "Character").strip()
        desc=(item.get("description") or "").strip()
        wardrobe=(item.get("wardrobe") or "").strip()
        parts=[f"Recurring character {name}: {desc}" if desc else
               f"Recurring character {name}, matching the supplied character reference exactly."]
        if wardrobe:
            parts.append(f"LOCKED COSTUME for {name}: {wardrobe}. Keep these exact clothes, colors, accessories and footwear in every scene. Do not redesign or randomly change the outfit.")
        parts.append(f"Preserve {name}'s facial features, hairstyle, apparent age, skin tone and body proportions across all shots. Only change costume when the scene text explicitly describes a costume change.")
        details.append(" ".join(parts))
    return " ".join(details)


def build_scene_continuity_prompt(scene, scene_index, scenes):
    """Carry forward adjacent scene context without overriding explicit new scene details."""
    if scene_index <= 0 or scene_index >= len(scenes):
        return ""
    previous=scenes[scene_index-1]
    previous_text=(previous.get("text") or "").strip()
    previous_request=(previous.get("visual_request") or "").strip()
    if not previous_text and not previous_request:
        return ""
    context=" ".join(x for x in (previous_text,previous_request) if x)
    return ("CONTINUITY FROM THE IMMEDIATELY PRECEDING SHOT: maintain the same "
            "characters, visual design, lighting direction, location layout and "
            "props where the story implies the same moment. Previous shot context: "
            +context+". Do not copy a previous location or costume when this scene "
            "explicitly establishes a change.")


def remap_character_scene_links(scenes, deleted_index):
    """Remove one character and keep legacy and multi-character scene indices aligned."""
    for scene in scenes:
        ids=scene.get("character_ids")
        if isinstance(ids,list):
            adjusted=[]
            for cid in ids:
                if not isinstance(cid,int) or cid==deleted_index:
                    continue
                adjusted.append(cid-1 if cid>deleted_index else cid)
            if adjusted:
                scene["character_ids"]=adjusted
                scene["character_id"]=adjusted[0]
            else:
                scene.pop("character_ids",None)
                scene.pop("character_id",None)
        else:
            cid=scene.get("character_id")
            if isinstance(cid,int):
                if cid==deleted_index: scene.pop("character_id",None)
                elif cid>deleted_index: scene["character_id"]=cid-1


def collect_character_reference_images(scene, characters):
    """Return existing unique reference image paths for the characters assigned to a scene."""
    ids=scene.get("character_ids")
    if not isinstance(ids,list):
        old_id=scene.get("character_id")
        ids=[old_id] if isinstance(old_id,int) else []
    images=[]
    for char_id in ids:
        if isinstance(char_id,int) and 0<=char_id<len(characters):
            character=characters[char_id]
            paths=[character.get("image","")]+list(character.get("reference_images",[]))
            for path in paths:
                if path and Path(path).is_file() and path not in images:
                    images.append(path)
    return images


def comfyui_upload_reference_image(base_url, image_path):
    """Upload a character reference to ComfyUI input storage and return its server-side name."""
    path=Path(image_path)
    if not path.is_file():
        raise FileNotFoundError("Karakter referans görseli bulunamadı: "+str(path))
    boundary="----VideoStudyosu"+str(random.randint(100000000,999999999))
    filename=path.name.replace('"',"_")
    body=(
        f"--{boundary}\r\n"
        f'Content-Disposition: form-data; name="image"; filename="{filename}"\r\n'
        f"Content-Type: application/octet-stream\r\n\r\n"
    ).encode("utf-8")+path.read_bytes()+f"\r\n--{boundary}--\r\n".encode("utf-8")
    req=urllib.request.Request(
        (base_url or "http://127.0.0.1:8188").rstrip("/")+"/upload/image",
        data=body,
        headers={"Content-Type":"multipart/form-data; boundary="+boundary},
        method="POST"
    )
    with urllib.request.urlopen(req,timeout=60) as response:
        result=json.loads(response.read().decode("utf-8"))
    name=result.get("name")
    if not name:
        raise RuntimeError("ComfyUI referans görselini yükledi ancak dosya adı dönmedi.")
    return name


def rank_visual_checkpoint(checkpoints):
    """Prefer realistic SDXL checkpoints over arbitrary first-in-list models."""
    def score(name):
        value=str(name).lower()
        points=0
        if "sdxl" in value or "xl" in value: points += 30
        if any(token in value for token in ("realvis", "juggernaut", "realistic", "cinematic", "epicrealism", "absolute reality")): points += 45
        if any(token in value for token in ("pony", "anime", "illustration", "cartoon", "toon", "waifu", "furry")): points -= 100
        if any(token in value for token in ("turbo", "lightning", "lcm")): points -= 8
        return points
    return sorted(checkpoints, key=lambda item: (score(item), str(item).lower()), reverse=True)[0]


def visual_generation_dimensions(width, height, is_sdxl=True):
    """Choose training-friendly dimensions for the requested aspect ratio."""
    ratio=float(width)/max(1,float(height))
    if is_sdxl:
        if ratio < 0.80: return 768, 1344
        if ratio > 1.25: return 1344, 768
        return 1024, 1024
    if ratio < 0.80: return 512, 768
    if ratio > 1.25: return 768, 512
    return 640, 640


def find_comfyui_installation():
    """Find the private Video Studyosu-managed engine or a compatible local ComfyUI."""
    managed=HOME/"AppData"/"Local"/"VideoStudyosu"/"AIEngine"
    candidates=[managed/"ComfyUI",managed]
    env_path=os.environ.get("VIDEO_STUDYOSU_COMFYUI")
    if env_path: candidates.append(Path(env_path).expanduser())
    candidates.extend([HOME/"ComfyUI",HOME/"comfyui",HOME/"Desktop"/"ComfyUI",HOME/"Documents"/"ComfyUI"])
    for root in candidates:
        if (root/"main.py").is_file():
            return root
        nested=list(root.glob("**/ComfyUI/main.py")) if root.is_dir() and root==managed else []
        if nested: return nested[0].parent
    return None


def _download_file(url, destination, progress=None, label="Dosya", workers=8):
    """Fast resumable downloader: parallel HTTP ranges with persistent chunks and safe fallback."""
    destination=Path(destination)
    destination.parent.mkdir(parents=True,exist_ok=True)
    if destination.is_file() and destination.stat().st_size>0:
        return destination
    headers={"User-Agent":"VideoStudyosu/5.6.9"}
    received_lock=threading.Lock()
    received_total=0
    started=time.monotonic()
    last_report=[0.0]
    def report(delta,total):
        nonlocal received_total
        with received_lock:
            received_total+=delta
            now=time.monotonic()
            if progress and (now-last_report[0]>=0.7 or (total and received_total>=total)):
                elapsed=max(now-started,0.1)
                speed=received_total/elapsed/1024**2
                pct=(received_total/total*100) if total else 0
                remaining=max(total-received_total,0)/max(received_total/elapsed,1) if total else 0
                progress(f"{label}: {received_total/1024**3:.2f}/{total/1024**3:.2f} GB · %{pct:.0f} · {speed:.1f} MB/sn · kalan {remaining/60:.1f} dk" if total else f"{label}: {received_total/1024**2:.1f} MB · {speed:.1f} MB/sn")
                last_report[0]=now
    # Ask the origin whether byte ranges are supported and learn the exact file size.
    total=0
    range_supported=False
    try:
        req=urllib.request.Request(url,headers={**headers,"Range":"bytes=0-0"})
        with urllib.request.urlopen(req,timeout=45) as response:
            content_range=response.headers.get("Content-Range","")
            match=re.search(r"/(\d+)$",content_range)
            if response.status==206 and match:
                total=int(match.group(1)); range_supported=True
            elif response.status==200:
                total=int(response.headers.get("Content-Length") or 0)
    except Exception:
        pass

    # Parallel ranged mode. Each chunk is persisted separately so interrupted
    # downloads resume only the missing bytes on the next launch.
    if range_supported and total>0:
        count=max(1,min(int(workers),max(1,math.ceil(total/(8*1024**2)))))
        chunk_size=math.ceil(total/count)
        parts_dir=destination.with_name(destination.name+".parts")
        parts_dir.mkdir(parents=True,exist_ok=True)
        # Discard chunks from a different-sized remote object.
        meta=parts_dir/"size.txt"
        if meta.exists() and meta.read_text(encoding="ascii",errors="ignore").strip()!=str(total):
            shutil.rmtree(parts_dir,ignore_errors=True); parts_dir.mkdir(parents=True,exist_ok=True)
        meta.write_text(str(total),encoding="ascii")
        jobs=[]
        for index in range(count):
            start=index*chunk_size
            end=min(total-1,start+chunk_size-1)
            part=parts_dir/f"{index:03d}.part"
            expected=end-start+1
            if part.exists() and part.stat().st_size>expected: part.unlink()
            if part.exists() and part.stat().st_size==expected:
                received_total+=expected
                continue
            jobs.append((index,start,end,part,expected))
        if progress:
            progress(f"{label}: çoklu bağlantı ile indirme başlıyor ({count} bağlantı)")
        def fetch_part(job):
            index,start,end,part,expected=job
            for attempt in range(4):
                current=part.stat().st_size if part.exists() else 0
                if current>=expected: return
                req_headers={**headers,"Range":f"bytes={start+current}-{end}"}
                try:
                    req=urllib.request.Request(url,headers=req_headers)
                    with urllib.request.urlopen(req,timeout=120) as response:
                        if response.status!=206:
                            raise RuntimeError("Sunucu parçalı indirmeyi desteklemiyor.")
                        mode="ab" if current else "wb"
                        with open(part,mode) as out:
                            while True:
                                data=response.read(1024*1024)
                                if not data: break
                                out.write(data); report(len(data),total)
                    if part.stat().st_size!=expected:
                        raise IOError("İndirilen parça boyutu beklenenden farklı.")
                    return
                except Exception:
                    if attempt==3: raise
                    time.sleep(1.5*(attempt+1))
        try:
            with concurrent.futures.ThreadPoolExecutor(max_workers=count) as pool:
                list(pool.map(fetch_part,jobs))
            temp=destination.with_suffix(destination.suffix+".assembling")
            with open(temp,"wb") as out:
                for index in range(count):
                    with open(parts_dir/f"{index:03d}.part","rb") as part:
                        shutil.copyfileobj(part,out,8*1024*1024)
            if temp.stat().st_size!=total:
                temp.unlink(missing_ok=True)
                raise IOError("Birleştirilen indirme dosyasının boyutu doğrulanamadı.")
            temp.replace(destination)
            shutil.rmtree(parts_dir,ignore_errors=True)
            destination.with_suffix(destination.suffix+".part").unlink(missing_ok=True)
            if progress: progress(f"{label}: indirme tamamlandı · {destination.stat().st_size/1024**3:.2f} GB")
            return destination
        except Exception as exc:
            # If the server advertised ranges but later rejects them, do not
            # assemble corrupt bytes. Continue using a single resumable stream.
            if progress: progress(f"{label}: çoklu bağlantı kullanılamadı, devam edilebilir tek bağlantıya geçiliyor ({exc})")

    # Single-stream fallback with HTTP Range resume.
    partial=destination.with_suffix(destination.suffix+".part")
    for attempt in range(4):
        offset=partial.stat().st_size if partial.exists() else 0
        request_headers=dict(headers)
        if offset: request_headers["Range"]=f"bytes={offset}-"
        req=urllib.request.Request(url,headers=request_headers)
        try:
            with urllib.request.urlopen(req,timeout=120) as response:
                if offset and response.status!=206:
                    partial.unlink(missing_ok=True)
                    raise IOError("Sunucu kaldığı yerden devamı kabul etmedi; temiz indirme yeniden başlatılacak.")
                if not offset and response.status not in (200,206):
                    raise IOError(f"Beklenmeyen HTTP durumu: {response.status}")
                content_len=int(response.headers.get("Content-Length") or 0)
                total_bytes=offset+content_len
                mode="ab" if offset else "wb"
                with open(partial,mode) as out:
                    while True:
                        data=response.read(4*1024*1024)
                        if not data: break
                        out.write(data); report(len(data),total_bytes)
            if total_bytes and partial.stat().st_size!=total_bytes:
                raise IOError("İndirme eksik kaldı.")
            partial.replace(destination)
            return destination
        except Exception:
            if attempt==3: raise
            time.sleep(2*(attempt+1))
    raise RuntimeError("Dosya indirilemedi: "+str(url))



def install_visual_engine(progress=None):
    """Install official ComfyUI portable runtime and a verified photorealistic SDXL checkpoint."""
    if os.name!="nt":
        raise RuntimeError("Otomatik görsel motoru kurulumu şu anda Windows içindir.")
    root=HOME/"AppData"/"Local"/"VideoStudyosu"/"AIEngine"
    comfy=root/"ComfyUI"
    drive=Path(root.anchor)
    free=shutil.disk_usage(drive).free
    if free < 18*1024**3:
        raise RuntimeError("Görsel motorunun ilk kurulumu için en az 18 GB boş disk alanı gerekiyor. Kurulum başlamadı.")
    root.mkdir(parents=True,exist_ok=True)
    archive=root/"ComfyUI_windows_portable_nvidia.7z"
    extractor=root/"7za.exe"
    if not extractor.is_file():
        if progress: progress("Görsel motoru kuruluyor: tam 7-Zip arşiv açıcı indiriliyor")
        _download_file("https://www.7-zip.org/a/7za.exe",extractor,progress,"7-Zip kurulum aracı")
    if not archive.is_file() or archive.stat().st_size<100_000_000:
        if progress: progress("Resmî ComfyUI çalışma ortamı indiriliyor")
        _download_file("https://github.com/comfyanonymous/ComfyUI/releases/latest/download/ComfyUI_windows_portable_nvidia.7z",archive,progress,"ComfyUI")
    creationflags=getattr(subprocess,"CREATE_NO_WINDOW",0) if os.name=="nt" else 0
    startupinfo=None
    if os.name=="nt":
        startupinfo=subprocess.STARTUPINFO()
        startupinfo.dwFlags|=subprocess.STARTF_USESHOWWINDOW
        startupinfo.wShowWindow=0
    if progress: progress("ComfyUI arşivi doğrulanıyor")
    test=subprocess.run([str(extractor),"t",str(archive)],capture_output=True,text=True,encoding="utf-8",errors="replace",timeout=900,creationflags=creationflags,startupinfo=startupinfo)
    if test.returncode:
        detail=(test.stdout or "")+"\\n"+(test.stderr or "")
        raise RuntimeError("ComfyUI arşiv doğrulaması başarısız. İndirme bozuk veya eksik olabilir: "+detail[-1800:])
    # Extract into a clean staging folder. A failed extraction must never be
    # mistaken for a complete install on the next startup.
    staging=root/"_ComfyUI_extracting"
    if staging.exists(): shutil.rmtree(staging,ignore_errors=True)
    staging.mkdir(parents=True,exist_ok=True)
    if progress: progress("ComfyUI dosyaları açılıyor (komut penceresi gösterilmez)")
    result=subprocess.run([str(extractor),"x",str(archive),"-o"+str(staging),"-y"],capture_output=True,text=True,encoding="utf-8",errors="replace",timeout=2400,creationflags=creationflags,startupinfo=startupinfo)
    if result.returncode:
        detail=(result.stdout or "")+"\\n"+(result.stderr or "")
        shutil.rmtree(staging,ignore_errors=True)
        raise RuntimeError("ComfyUI paketi açılamadı (7-Zip çıkış kodu "+str(result.returncode)+"): "+detail[-2200:])
    candidates=[p.parent for p in staging.glob("**/main.py") if p.parent.name.lower()=="comfyui"]
    found=None
    for candidate in candidates:
        portable_root=candidate.parent
        if (portable_root/"python_embeded"/"python.exe").is_file():
            found=candidate
            break
    if found is None:
        shutil.rmtree(staging,ignore_errors=True)
        raise RuntimeError("Arşiv açıldı ancak beklenen ComfyUI\\main.py ve python_embeded\\python.exe birlikte bulunamadı. Kurulum dosyaları eksik.")
    final_root=found.parent
    target_root=root/"ComfyUI_windows_portable"
    if target_root.exists(): shutil.rmtree(target_root,ignore_errors=True)
    shutil.move(str(final_root),str(target_root))
    shutil.rmtree(staging,ignore_errors=True)
    found=target_root/"ComfyUI"
    py_candidates=[target_root/"python_embeded"/"python.exe"]
    py=next((p for p in py_candidates if p.is_file()),None)
    if py is None:
        raise RuntimeError("ComfyUI Python çalışma ortamı pakette bulunamadı.")
    model=found/"models"/"checkpoints"/"RealVisXL_V5.0_fp16.safetensors"
    if not model.is_file() or model.stat().st_size<6_000_000_000:
        if progress: progress("Fotogerçekçi RealVisXL modeli indiriliyor (yaklaşık 6,94 GB)")
        _download_file(
            "https://huggingface.co/SG161222/RealVisXL_V5.0/resolve/main/RealVisXL_V5.0_fp16.safetensors",
            model,progress,"RealVisXL modeli"
        )
    digest=hashlib.sha256()
    with open(model,"rb") as stream:
        for chunk in iter(lambda:stream.read(8*1024*1024),b""): digest.update(chunk)
    if digest.hexdigest().lower()!="6a35a7855770ae9820a3c931d4964c3817b6d9e3c6f9c4dabb5b3a94e5643b80":
        model.unlink(missing_ok=True)
        raise RuntimeError("İndirilen görsel modelinin SHA256 doğrulaması başarısız. Güvenlik için dosya silindi.")
    if progress: progress("Gerçekçi görsel modeli doğrulandı; motor hazır")
    return found


def ensure_visual_models_and_reference_support(install, progress=None):
    """Install the realistic SDXL checkpoint and IPAdapter Plus reference stack automatically."""
    install=Path(install)
    models=install/"models"
    checkpoint=models/"checkpoints"/"RealVisXL_V5.0_fp16.safetensors"
    checkpoint.parent.mkdir(parents=True,exist_ok=True)
    if not checkpoint.is_file() or checkpoint.stat().st_size<6_000_000_000:
        if progress: progress("Fotogerçekçi RealVisXL modeli indiriliyor (6,94 GB)")
        _download_file("https://huggingface.co/SG161222/RealVisXL_V5.0/resolve/main/RealVisXL_V5.0_fp16.safetensors",checkpoint,progress,"RealVisXL")
    digest=hashlib.sha256()
    with open(checkpoint,"rb") as stream:
        for chunk in iter(lambda:stream.read(8*1024*1024),b""): digest.update(chunk)
    if digest.hexdigest().lower()!="6a35a7855770ae9820a3c931d4964c3817b6d9e3c6f9c4dabb5b3a94e5643b80":
        checkpoint.unlink(missing_ok=True)
        raise RuntimeError("RealVisXL model SHA256 doğrulaması başarısız; dosya güvenlik için silindi.")
    nodes=install/"custom_nodes"
    nodes.mkdir(parents=True,exist_ok=True)
    node=nodes/"ComfyUI_IPAdapter_plus"
    if not (node/"__init__.py").is_file():
        if progress: progress("Karakter referans sistemi kuruluyor")
        data=urllib.request.urlopen("https://codeload.github.com/cubiq/ComfyUI_IPAdapter_plus/zip/refs/heads/main",timeout=60).read()
        with zipfile.ZipFile(io.BytesIO(data)) as archive:
            archive.extractall(nodes)
        extracted=nodes/"ComfyUI_IPAdapter_plus-main"
        if extracted.exists(): extracted.rename(node)
    clip=models/"clip_vision"/"CLIP-ViT-H-14-laion2B-s32B-b79K.safetensors"
    adapter=models/"ipadapter"/"ip-adapter-plus_sdxl_vit-h.safetensors"
    if not clip.is_file() or clip.stat().st_size<100_000_000:
        if progress: progress("Karakter tanıma modeli indiriliyor")
        _download_file("https://huggingface.co/h94/IP-Adapter/resolve/main/models/image_encoder/model.safetensors",clip,progress,"CLIP Vision")
    if not adapter.is_file() or adapter.stat().st_size<100_000_000:
        if progress: progress("Karakter referans ağırlıkları indiriliyor")
        _download_file("https://huggingface.co/h94/IP-Adapter/resolve/main/sdxl_models/ip-adapter-plus_sdxl_vit-h.safetensors",adapter,progress,"IPAdapter Plus")
    return checkpoint


def ensure_comfyui_running(base_url="http://127.0.0.1:8188", startup_timeout=240, progress=None):
    """Install if absent, start the local engine and wait for its API."""
    base_url=(base_url or "http://127.0.0.1:8188").strip().rstrip("/")
    try:
        with urllib.request.urlopen(base_url+"/system_stats",timeout=2):
            # The engine is already running. Avoid replacing files underneath a live process.
            return True
    except Exception: pass
    install=find_comfyui_installation()
    if install is None:
        install=install_visual_engine(progress)
    ensure_visual_models_and_reference_support(install,progress)
    py_candidates=[install.parent/"python_embeded"/"python.exe",install/"python_embeded"/"python.exe"]
    py=next((p for p in py_candidates if p.is_file()),None)
    if py is None: raise RuntimeError("Görsel motorunun Python çalışma ortamı bulunamadı.")
    if progress: progress("Yerel görsel motoru başlatılıyor")
    launch_args=[str(py),str(install/"main.py"),"--listen","127.0.0.1","--port","8188"]
    if not shutil.which("nvidia-smi"): launch_args.append("--cpu")
    creationflags=getattr(subprocess,"CREATE_NO_WINDOW",0) if os.name=="nt" else 0
    subprocess.Popen(launch_args,cwd=str(install),stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL,
                     stdin=subprocess.DEVNULL,creationflags=creationflags,start_new_session=(os.name!="nt"))
    deadline=time.time()+int(startup_timeout); last_error=None
    while time.time()<deadline:
        time.sleep(3)
        try:
            with urllib.request.urlopen(base_url+"/system_stats",timeout=4): return True
        except Exception as exc: last_error=exc
    raise RuntimeError("Görsel motoru başlatıldı ancak API zamanında hazır olmadı: "+str(last_error))


def create_default_comfyui_workflow(base_url, width=1024, height=1024):
    """Build a quality-oriented workflow and enable IPAdapter when its nodes are installed."""
    base_url=(base_url or "http://127.0.0.1:8188").strip().rstrip("/")
    request=urllib.request.Request(base_url+"/models/checkpoints",headers={"User-Agent":"VideoStudyosu"})
    try:
        with urllib.request.urlopen(request,timeout=10) as response:
            checkpoints=json.loads(response.read().decode("utf-8"))
    except Exception as exc:
        raise RuntimeError("ComfyUI'ye ulaşılamadı. Önce yerel ComfyUI'yi başlat. Ayrıntı: "+str(exc))
    if not isinstance(checkpoints,list) or not checkpoints:
        raise RuntimeError("ComfyUI bağlı ancak yüklü checkpoint modeli bulunamadı. Gerçekçi SDXL checkpoint modelini ComfyUI/models/checkpoints klasörüne kur.")
    checkpoint=rank_visual_checkpoint(checkpoints)
    is_sdxl=("xl" in str(checkpoint).lower() or "sdxl" in str(checkpoint).lower())
    gen_width,gen_height=visual_generation_dimensions(width,height,is_sdxl=is_sdxl)
    ipadapter_ready=False
    try:
        with urllib.request.urlopen(base_url+"/object_info/IPAdapterUnifiedLoader",timeout=8) as response:
            unified_info=json.loads(response.read().decode("utf-8"))
        with urllib.request.urlopen(base_url+"/object_info/IPAdapter",timeout=8) as response:
            advanced_info=json.loads(response.read().decode("utf-8"))
        ipadapter_ready=bool(unified_info and advanced_info)
    except Exception:
        ipadapter_ready=False
    positive=("photorealistic cinematic movie still, live-action feature film frame, real human actors, "
              "physically plausible environment, natural skin texture, realistic eyes and hands, "
              "professional cinematography, detailed production design, realistic lighting, "
              "subtle film grain, high dynamic range, coherent perspective, precise subject placement")
    negative=("cartoon, illustration, drawing, sketch, stick figure, anime, comic, vector art, "
              "flat graphic, geometric placeholder, 2d animation, painting, 3d toy, plastic skin, "
              "uncanny face, deformed anatomy, malformed hands, extra fingers, duplicate people, "
              "blurry, low resolution, oversaturated, text, subtitles, watermark, collage, border")
    workflow={
        "1":{"class_type":"CheckpointLoaderSimple","inputs":{"ckpt_name":checkpoint}},
        "2":{"class_type":"CLIPTextEncode","inputs":{"text":positive,"clip":["1",1]}},
        "3":{"class_type":"CLIPTextEncode","inputs":{"text":negative,"clip":["1",1]}},
        "4":{"class_type":"EmptyLatentImage","inputs":{"width":gen_width,"height":gen_height,"batch_size":1}},
        "5":{"class_type":"KSampler","inputs":{"seed":int(time.time())%(2**32),"steps":32 if is_sdxl else 28,"cfg":6.0,"sampler_name":"dpmpp_2m","scheduler":"karras","denoise":1.0,"model":["1",0],"positive":["2",0],"negative":["3",0],"latent_image":["4",0]}},
        "6":{"class_type":"VAEDecode","inputs":{"samples":["5",0],"vae":["1",2]}},
        "7":{"class_type":"SaveImage","inputs":{"filename_prefix":"VideoStudyosu/Scene","images":["6",0]}}
    }
    if ipadapter_ready:
        workflow["8"]={"class_type":"IPAdapterUnifiedLoader","inputs":{"model":["1",0],"preset":"PLUS (high strength)"}}
        workflow["9"]={"class_type":"IPAdapter","inputs":{
            "model":["8",0],"ipadapter":["8",1],"image":["10",0],"weight":0.85,
            "start_at":0.0,"end_at":0.85,"weight_type":"standard"}}
        workflow["5"]["inputs"]["model"]=["9",0]
    target=Path(tempfile.gettempdir())/"video_studyosu_auto_workflow.json"
    target.write_text(json.dumps(workflow,ensure_ascii=False,indent=2),encoding="utf-8")
    return str(target),checkpoint


def expand_ipadapter_workflow_for_references(workflow, reference_count):
    """Build a chained IPAdapter path with one image input per character reference."""
    if reference_count <= 0:
        return []
    adapters = {
        str(node_id): node for node_id, node in workflow.items()
        if isinstance(node, dict) and "IPAdapter" in str(node.get("class_type", ""))
        and isinstance(node.get("inputs"), dict) and "image" in node["inputs"]
    }
    if not adapters:
        raise ValueError("Bu ComfyUI iş akışında IPAdapter görüntü uygulama düğümü bulunamadı. Karakter referansı için IPAdapter Plus kurulu olmalı.")
    samplers = [
        node for node in workflow.values()
        if isinstance(node, dict) and node.get("class_type") in ("KSampler", "KSamplerAdvanced")
        and isinstance(node.get("inputs"), dict)
    ]
    terminal_ids = []
    for sampler in samplers:
        model = sampler["inputs"].get("model")
        if isinstance(model, (list, tuple)) and model and str(model[0]) in adapters:
            terminal_ids.append(str(model[0]))
    if not terminal_ids:
        raise ValueError("IPAdapter düğümü KSampler model girişine bağlı değil; karakter referans zinciri kurulamadı.")
    terminal_id = terminal_ids[0]
    chain = []
    cursor = terminal_id
    while cursor in adapters and cursor not in chain:
        chain.append(cursor)
        model = adapters[cursor]["inputs"].get("model")
        cursor = str(model[0]) if isinstance(model, (list, tuple)) and model else ""
    chain.reverse()
    if not chain:
        raise ValueError("IPAdapter karakter referans zinciri çözümlenemedi.")
    numeric_ids = [int(key) for key in workflow if str(key).isdigit()]
    next_id = max(numeric_ids or [0]) + 1
    while len(chain) < reference_count:
        previous_id = chain[-1]
        cloned = copy.deepcopy(adapters[previous_id])
        cloned["inputs"]["model"] = [previous_id, 0]
        new_id = str(next_id)
        next_id += 1
        workflow[new_id] = cloned
        adapters[new_id] = cloned
        chain.append(new_id)
    final_id = chain[reference_count - 1]
    for sampler in samplers:
        model = sampler["inputs"].get("model")
        if isinstance(model, (list, tuple)) and model and str(model[0]) in adapters:
            sampler["inputs"]["model"] = [final_id, 0]
    return [(node_id, adapters[node_id]["inputs"]) for node_id in chain[:reference_count]]


def comfyui_generate_image(base_url, workflow_path, prompt_text, output_dir, width=1024, height=1024, timeout=1200, reference_images=None, seed=0):
    """Submit a ComfyUI API workflow, preserve its model-safe latent size, and save the result."""
    base_url=(base_url or "http://127.0.0.1:8188").strip().rstrip("/")
    with open(workflow_path,"r",encoding="utf-8") as handle:
        workflow=json.load(handle)
    if not isinstance(workflow,dict) or not workflow:
        raise ValueError("ComfyUI API iş akışı boş veya geçersiz.")
    # Update common built-in text and seed nodes without assuming fixed node IDs.
    text_nodes=[]
    negative_nodes=[]
    reference_images=[str(p) for p in (reference_images or []) if p and Path(p).is_file()]
    for node_id,node in workflow.items():
        if not isinstance(node,dict): continue
        kind=node.get("class_type","")
        inputs=node.get("inputs",{})
        if kind in ("CLIPTextEncode","CLIPTextEncodeSDXL") and isinstance(inputs,dict):
            text_value=inputs.get("text")
            if isinstance(text_value,str):
                text_nodes.append((node_id,inputs,text_value))
        if kind in ("KSampler","KSamplerAdvanced") and isinstance(inputs,dict):
            if "seed" in inputs: inputs["seed"]=int(seed or 0) % (2**32)
            negative=inputs.get("negative")
            if isinstance(negative,(list,tuple)) and negative: negative_nodes.append(str(negative[0]))
        # Keep the latent dimensions selected by create_default_comfyui_workflow.
        # Those SDXL-safe dimensions are derived from the requested aspect ratio;
        # replacing them with the UI canvas size can trigger avoidable VRAM errors.
    # Attach uploaded references to actual IPAdapter image inputs, not merely to unused LoadImage nodes.
    if reference_images:
        # Extend the adapter chain automatically for every saved character angle.
        ipadapter_nodes=expand_ipadapter_workflow_for_references(workflow,len(reference_images))
        uploaded_refs=[comfyui_upload_reference_image(base_url,reference) for reference in reference_images]
        next_id=max([int(k) for k in workflow if str(k).isdigit()] or [0])+1
        for (adapter_id,adapter_inputs),image_name in zip(ipadapter_nodes,uploaded_refs):
            load_id=str(next_id); next_id+=1
            workflow[load_id]={
                "class_type":"LoadImage",
                "inputs":{"image":image_name}
            }
            adapter_inputs["image"]=[load_id,0]
    if not text_nodes:
        raise ValueError("İş akışında CLIPTextEncode metin düğümü bulunamadı. API formatında SD/SDXL iş akışı seç.")
    # Prefer the encoder connected to KSampler.positive; fall back to first encoder.
    positive_ids=[]
    for node in workflow.values():
        if not isinstance(node,dict) or node.get("class_type") not in ("KSampler","KSamplerAdvanced"):
            continue
        positive=node.get("inputs",{}).get("positive")
        if isinstance(positive,(list,tuple)) and positive:
            positive_ids.append(str(positive[0]))
    positive_node=next((item for item in text_nodes if item[0] in positive_ids),text_nodes[0])
    positive_node[1]["text"]=prompt_text
    negative_node=next((item for item in text_nodes if item[0] in negative_nodes),None)
    if negative_node:
        negative_node[1]["text"]=(negative_node[1].get("text","")+" blurry, low quality, deformed anatomy, extra fingers, duplicate person, inconsistent face, inconsistent clothing").strip(", ")
    client_id="video-studyosu-"+str(random.randint(100000,999999999))
    payload=json.dumps({"prompt":workflow,"client_id":client_id}).encode("utf-8")
    request=urllib.request.Request(base_url+"/prompt",data=payload,headers={"Content-Type":"application/json"},method="POST")
    with urllib.request.urlopen(request,timeout=30) as response:
        submitted=json.loads(response.read().decode("utf-8"))
    prompt_id=submitted.get("prompt_id")
    if not prompt_id:
        raise RuntimeError("ComfyUI işi kabul etmedi: "+json.dumps(submitted,ensure_ascii=False)[:1200])
    deadline=time.time()+int(timeout)
    history=None
    while time.time()<deadline:
        time.sleep(2)
        try:
            with urllib.request.urlopen(base_url+"/history/"+prompt_id,timeout=20) as response:
                data=json.loads(response.read().decode("utf-8"))
            history=data.get(prompt_id) or data
            if history and history.get("outputs"):
                break
            if history and history.get("status",{}).get("status_str")=="error":
                raise RuntimeError("ComfyUI görsel üretimi hata verdi: "+str(history["status"])[:1200])
        except urllib.error.HTTPError:
            continue
    else:
        raise TimeoutError("ComfyUI görsel üretimi zaman aşımına uğradı.")
    outputs=history.get("outputs",{})
    image_info=None
    for node_output in outputs.values():
        for image_item in node_output.get("images",[]):
            if image_item.get("filename"):
                image_info=image_item
                break
        if image_info: break
    if not image_info:
        raise RuntimeError("İş tamamlandı ancak SaveImage çıktısı bulunamadı. İş akışında SaveImage düğümü olmalı.")
    query=urllib.parse.urlencode({"filename":image_info["filename"],"subfolder":image_info.get("subfolder",""),"type":image_info.get("type","output")})
    with urllib.request.urlopen(base_url+"/view?"+query,timeout=60) as response:
        image_bytes=response.read()
    output_dir=Path(output_dir); output_dir.mkdir(parents=True,exist_ok=True)
    target=output_dir/("comfy_"+prompt_id[:8]+".png")
    target.write_bytes(image_bytes)
    with Image.open(target) as verify:
        verify.verify()
    return str(target)

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
    scene = (text or "").lower()
    combined = scene + " " + r
    notes = []
    style = {"dark": 0, "fog": 0, "rain": 0, "warm": 0, "red": 0, "moon": 0,
             "silhouette": 0, "stars": 0, "bright": 0, "snow": 0,
             "lightning": 0, "fire": 0, "sunset": 0}
    if any(k in combined for k in ["kar yağıyor", "kar yağışı", "karlı", "kar fırtınası", "tipi", "snow"]):
        style["snow"] = 1; notes.append("kar yağışı")
    if any(k in combined for k in ["şimşek", "yıldırım", "fırtına", "storm"]):
        style["lightning"] = 1; notes.append("şimşek efekti")
    if any(k in combined for k in ["alev", "yangın", "yanıyor", "kamp ateşi", "fire"]):
        style["fire"] = 1; notes.append("ateş ışığı")
    if any(k in combined for k in ["gün batımı", "gün doğumu", "şafak", "sunset", "sunrise"]):
        style["sunset"] = 1; notes.append("gün doğumu/batımı renkleri")
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
    c1,c2,kind = palette_for(combined)
    if style["sunset"]:
        c1,c2=(42,30,65),(205,91,53)
    if style["fire"]:
        c2=(190,70,24)
    return c1,c2,kind,style,notes

def draw_scene_subjects(draw, text, w, h, kind, seed):
    """Sahne metnindeki mekân ve nesne ipuçlarına göre ayrı kompozisyonlar çizer."""
    t=(text or "").lower()
    rng=random.Random(seed + sum(ord(ch) for ch in t[:180]))
    def ln(points, fill=(5,5,8,235), width=5):
        draw.line(points, fill=fill, width=width)
    if any(k in t for k in ["mutfak","tezgah","ocak","tencere","yemek hazırl"]):
        # Kitchen: counter, cabinets, tiled backsplash and cooker.
        draw.rectangle((0,int(h*.18),w,int(h*.62)),fill=(72,61,52,170))
        for x in [int(w*.12),int(w*.39),int(w*.66)]:
            draw.rectangle((x,int(h*.22),x+int(w*.20),int(h*.48)),fill=(35,39,43,245),outline=(175,155,125,210),width=4)
            draw.ellipse((x+int(w*.08),int(h*.29),x+int(w*.12),int(h*.34)),fill=(205,185,145,220))
        draw.rectangle((0,int(h*.62),w,int(h*.75)),fill=(95,77,60,245))
        draw.rectangle((int(w*.12),int(h*.75),int(w*.88),int(h*.80)),fill=(35,30,28,245))
        for x in [int(w*.30),int(w*.50),int(w*.70)]:
            draw.ellipse((x-int(w*.035),int(h*.72),x+int(w*.035),int(h*.76)),outline=(210,195,165,220),width=5)
    elif any(k in t for k in ["hastane","ameliyat","doktor","hemşire","acil servis"]):
        draw.rectangle((int(w*.08),int(h*.16),int(w*.92),int(h*.78)),fill=(180,195,195,95),outline=(215,225,220,190),width=5)
        draw.rectangle((int(w*.18),int(h*.30),int(w*.82),int(h*.66)),fill=(205,215,210,235),outline=(65,85,90,220),width=5)
        draw.rectangle((int(w*.24),int(h*.22),int(w*.76),int(h*.34)),fill=(230,235,225,240))
        draw.line((int(w*.50),int(h*.23),int(w*.50),int(h*.32)),fill=(170,35,40,240),width=8)
        draw.line((int(w*.46),int(h*.275),int(w*.54),int(h*.275)),fill=(170,35,40,240),width=8)
    elif any(k in t for k in ["okul","sınıf","öğretmen","öğrenci","tahta"]):
        draw.rectangle((int(w*.12),int(h*.16),int(w*.88),int(h*.53)),fill=(20,62,53,245),outline=(155,125,85,230),width=8)
        draw.line((int(w*.18),int(h*.31),int(w*.48),int(h*.31)),fill=(225,225,205,200),width=4)
        draw.line((int(w*.18),int(h*.39),int(w*.63),int(h*.39)),fill=(225,225,205,180),width=4)
        for x in [int(w*.22),int(w*.48),int(w*.72)]:
            draw.rectangle((x,int(h*.65),x+int(w*.13),int(h*.72)),fill=(105,70,43,245))
            draw.line((x+int(w*.02),int(h*.72),x,int(h*.88)),fill=(35,27,22,245),width=7)
            draw.line((x+int(w*.11),int(h*.72),x+int(w*.13),int(h*.88)),fill=(35,27,22,245),width=7)
    elif any(k in t for k in ["ofis","büro","toplantı","masa başı","bilgisayar"]):
        draw.rectangle((int(w*.12),int(h*.18),int(w*.88),int(h*.64)),fill=(35,48,58,210),outline=(120,140,150,180),width=5)
        draw.rectangle((int(w*.22),int(h*.35),int(w*.48),int(h*.62)),fill=(12,18,25,250),outline=(160,170,175,220),width=5)
        draw.rectangle((int(w*.17),int(h*.64),int(w*.83),int(h*.71)),fill=(95,65,43,245))
        draw.rectangle((int(w*.57),int(h*.38),int(w*.78),int(h*.63)),fill=(15,22,30,245),outline=(170,180,185,190),width=4)
    elif any(k in t for k in ["koridor","oda","içeri girdi","kapıyı aç","evin içinde"]):
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
        # Layered figure: cast shadow, body, head, clothing highlights and ground contact.
        cx,cy=int(w*.52),int(h*.72); rr=int(min(w,h)*.052)
        draw.ellipse((cx-int(rr*1.8),cy+int(rr*1.8),cx+int(rr*1.8),cy+int(rr*2.5)),fill=(0,0,0,105))
        coat=(17,22,29,250) if kind=="horror" else (34,42,48,245)
        draw.ellipse((cx-rr,cy-4*rr,cx+rr,cy-2*rr),fill=(8,10,14,255))
        draw.rounded_rectangle((cx-int(rr*1.35),cy-2*rr,cx+int(rr*1.35),cy+int(rr*1.6)),radius=max(5,rr//2),fill=coat,outline=(120,125,125,100),width=max(1,rr//10))
        # Neck and collar catch a little scene light.
        draw.rectangle((cx-int(rr*.35),cy-2*rr,cx+int(rr*.35),cy-int(rr*1.55)),fill=(105,83,69,230))
        draw.polygon([(cx-int(rr*.7),cy-2*rr),(cx,cy-int(rr*1.25)),(cx+int(rr*.7),cy-2*rr)],fill=(165,155,140,175))
        # Arms and legs are separate shapes to give the silhouette a readable pose.
        ln([(cx-int(rr*1.1),cy-int(rr*1.2)),(cx-int(rr*2.0),cy+int(rr*.6))],coat,max(5,int(rr*.55)))
        ln([(cx+int(rr*1.1),cy-int(rr*1.2)),(cx+int(rr*1.9),cy+int(rr*.35))],coat,max(5,int(rr*.55)))
        ln([(cx-int(rr*.65),cy+int(rr*1.4)),(cx-int(rr*1.05),cy+int(rr*3.0))],(9,12,17,255),max(6,int(rr*.62)))
        ln([(cx+int(rr*.65),cy+int(rr*1.4)),(cx+int(rr*1.25),cy+int(rr*2.9))],(9,12,17,255),max(6,int(rr*.62)))
        draw.ellipse((cx-int(rr*.18),cy-int(rr*3.2),cx+int(rr*.18),cy-int(rr*2.95)),fill=(205,185,155,180))
def make_original_visual(text, path, size=(1280,720), seed=0, request="", draw_text=True):
    """API'siz, Pillow tabanlı özgün atmosferik grafik kompozisyonu."""
    w,h=size
    rng = random.Random(seed + sum(ord(c) for c in (text + request)[:120]))
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
        x,y = rng.randrange(w), rng.randrange(h)
        r = rng.choice([1,1,2,3])
        alpha = rng.randint(20,100)
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
                x1 = x0 + (1 if side==0 else -1)*rng.randint(80,230)
                d.line((x0,yy,x1,yy-rng.randint(50,150)), fill=(2,5,7,220), width=rng.randint(5,13))
    elif kind == "nature":
        for i in range(16):
            x=rng.randint(-30,w+30); base=horizon+rng.randint(0,70)
            top=rng.randint(int(h*.18),int(h*.52))
            d.polygon([(x,base),(x-rng.randint(25,65),base),(x,top),(x+rng.randint(25,65),base)], fill=(3,18,17,210))
    elif kind == "space":
        for _ in range(60):
            x,y=rng.randrange(w),rng.randrange(horizon)
            d.ellipse((x,y,x+rng.randint(2,5),y+rng.randint(2,5)), fill=(240,235,255,180))
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
        alpha = rng.randint(18,42) if style["fog"] else rng.randint(10,28)
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
            x=rng.randrange(w); y=rng.randrange(h)
            od.line((x,y,x-12,y+32),fill=(180,205,220,90),width=2)
    if style["red"]:
        od.rectangle((0,0,w,h),fill=(100,0,10,18))
    if style["snow"]:
        for _ in range(max(90, int(w*h/9000))):
            x=rng.randrange(w); y=rng.randrange(h); r=rng.choice([1,1,2,3])
            od.ellipse((x-r,y-r,x+r,y+r),fill=(238,244,250,rng.randint(100,220)))
    if style["lightning"]:
        bolt=[(int(w*.72),0),(int(w*.63),int(h*.19)),(int(w*.70),int(h*.19)),
              (int(w*.57),int(h*.43)),(int(w*.68),int(h*.27)),(int(w*.62),int(h*.27))]
        od.line(bolt,fill=(225,232,255,220),width=max(3,int(min(w,h)*.009)),joint="curve")
        od.line(bolt,fill=(185,205,255,100),width=max(9,int(min(w,h)*.025)),joint="curve")
    if style["fire"]:
        glow_fire=Image.new("RGBA",(w,h),(0,0,0,0)); fire_draw=ImageDraw.Draw(glow_fire)
        fire_draw.ellipse((int(w*.58),int(h*.48),int(w*1.08),int(h*1.08)),fill=(255,105,20,105))
        glow_fire=glow_fire.filter(ImageFilter.GaussianBlur(max(20,int(min(w,h)*.09))))
        overlay=Image.alpha_composite(overlay,glow_fire)
    im=Image.alpha_composite(im.convert("RGBA"),overlay).convert("RGB")
    # Her sahneye metin tabanli ayri on plan kompozisyonu ekle.
    draw_scene_subjects(ImageDraw.Draw(im, "RGBA"), text + " " + request, w, h, kind, seed)
    # Soft cinematic vignette: keep the focal area readable while adding depth.
    vignette=Image.new("RGBA",(w,h),(0,0,0,0))
    vd=ImageDraw.Draw(vignette)
    max_layers=18
    for layer in range(max_layers):
        inset=int(min(w,h)*0.012*layer)
        alpha=int(2+layer*1.15)
        vd.rectangle((inset,inset,w-inset,h-inset),outline=(0,0,0,alpha),width=max(2,int(min(w,h)*0.012)))
    vignette=vignette.filter(ImageFilter.GaussianBlur(max(8,int(min(w,h)*0.035))))
    im=Image.alpha_composite(im.convert("RGBA"),vignette).convert("RGB")
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


def apply_camera_framing(source_path, output_path, request="", target_size=None):
    """Apply a lightweight camera framing preset without altering the source image."""
    text=(request or "").lower()
    mode=None
    if any(k in text for k in ["yakın plan","yakın çekim","close-up","close up","portre çekim"]):
        mode="close"
    elif any(k in text for k in ["geniş açı","genel plan","uzak plan","wide shot","wide-angle"]):
        mode="wide"
    elif any(k in text for k in ["tepeden çekim","üst açı","kuş bakışı","top-down","overhead"]):
        mode="top"
    elif any(k in text for k in ["alttan çekim","alt açı","low angle"]):
        mode="low"
    if not mode:
        if target_size:
            fit_image(source_path,target_size).save(output_path,quality=94)
            return output_path
        shutil.copy2(source_path,output_path)
        return output_path
    im=Image.open(source_path).convert("RGB")
    w,h=im.size
    if mode=="wide":
        # Wider framing: preserve the complete original frame inside a soft fill.
        if target_size:
            fit_image(source_path,target_size).save(output_path,quality=94)
        else:
            im.save(output_path,quality=94)
        return output_path
    zoom=1.28 if mode=="close" else 1.10
    cw,ch=max(1,int(w/zoom)),max(1,int(h/zoom))
    left=(w-cw)//2
    if mode=="top":
        top=0
    elif mode=="low":
        top=h-ch
    else:
        top=(h-ch)//2
    cropped=im.crop((left,top,left+cw,top+ch))
    if target_size:
        cropped=fit_image_from_object(cropped,target_size)
    cropped.save(output_path,quality=94)
    return output_path

def fit_image_from_object(im, size):
    """Fit a Pillow image into a target frame with a blurred background."""
    w,h=size
    if im.size==(w,h):
        return im.convert("RGB")
    cover=max(w/im.width,h/im.height)
    bg=im.resize((max(w,int(im.width*cover)),max(h,int(im.height*cover))),Image.Resampling.LANCZOS)
    bx=(bg.width-w)//2; by=(bg.height-h)//2
    bg=bg.crop((bx,by,bx+w,by+h)).filter(ImageFilter.GaussianBlur(max(10,int(min(w,h)*.025))))
    bg=Image.blend(bg,Image.new("RGB",(w,h),(0,0,0)),.25)
    scale=min(w/im.width,h/im.height)
    fg=im.resize((max(1,int(im.width*scale)),max(1,int(im.height*scale))),Image.Resampling.LANCZOS)
    bg.paste(fg,((w-fg.width)//2,(h-fg.height)//2))
    return bg

def fit_image(src, size):
    """Fits an image without cutting off the subject; uses a soft blurred fill behind it."""
    w,h=size
    im=Image.open(src).convert("RGB")
    if im.size==(w,h):
        return im
    # Full-frame blurred background fills the target ratio.
    cover=max(w/im.width,h/im.height)
    bw,bh=max(w,int(im.width*cover)),max(h,int(im.height*cover))
    bg=im.resize((bw,bh),Image.Resampling.LANCZOS)
    bx=(bw-w)//2; by=(bh-h)//2
    bg=bg.crop((bx,by,bx+w,by+h))
    bg=bg.filter(ImageFilter.GaussianBlur(max(10,int(min(w,h)*0.025))))
    shade=Image.new("RGB",(w,h),(0,0,0))
    bg=Image.blend(bg,shade,0.28)
    # Keep the entire original image visible in the foreground.
    contain=min(w/im.width,h/im.height)
    fw,fh=max(1,int(im.width*contain)),max(1,int(im.height*contain))
    fg=im.resize((fw,fh),Image.Resampling.LANCZOS)
    x=(w-fw)//2; y=(h-fh)//2
    bg.paste(fg,(x,y))
    return bg

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



def camera_motion_filter(request, size, fps=30):
    """Return a gentle Ken Burns move selected from the scene's camera direction request."""
    text=(request or "").lower()
    w,h=size
    zoom="min(zoom+0.00045,1.08)"
    x="(iw-iw/zoom)/2"
    y="(ih-ih/zoom)/2"
    span=str(max(1,fps*8))
    if any(k in text for k in ["sola kay","sola pan","kamera sola","pan left"]):
        x="(iw-iw/zoom)*(0.85-0.70*on/"+span+")"
    elif any(k in text for k in ["sağa kay","sağa pan","kamera sağa","pan right"]):
        x="(iw-iw/zoom)*(0.15+0.70*on/"+span+")"
    elif any(k in text for k in ["yukarı kay","yukarı pan","kamera yukarı","pan up"]):
        y="(ih-ih/zoom)*(0.85-0.70*on/"+span+")"
    elif any(k in text for k in ["aşağı kay","aşağı pan","kamera aşağı","pan down"]):
        y="(ih-ih/zoom)*(0.15+0.70*on/"+span+")"
    elif any(k in text for k in ["geri çekil","zoom out","uzaklaşan kamera"]):
        zoom="max(1.0,1.08-on*0.00045)"
    elif any(k in text for k in ["yaklaş","kameraya yaklaş","zoom in","ileri dolly"]):
        zoom="min(zoom+0.00065,1.12)"
    return (
        f"scale={w*2}:{h*2},"
        f"zoompan=z='{zoom}':x='{x}':y='{y}':d=1:s={w}x{h}:fps={fps},"
        "eq=contrast=1.06:saturation=0.94,vignette=angle=PI/5,"
        "noise=alls=2:allf=t+u,format=yuv420p"
    )


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
class VideoStudio:
    def __init__(self, root):
        self.root=root
        self.root.title(APP_NAME)
        self.root.geometry("1120x780")
        self.root.minsize(950,650)
        self.project={"name":"Yeni Video","script":"","scenes":[],"music":"","ratio":"16:9","captions":True,
                      "voice":"tr-TR-AhmetNeural","rate":0,"voice_volume":100,"music_volume":12,"characters":[]}
        self.current=None
        self.busy=False
        self.build_ui()
        self.refresh_library()
        self.root.protocol("WM_DELETE_WINDOW", self.close)
        self.root.after(1200,self.refresh_voice_catalog)

    def build_ui(self):
        style=ttk.Style()
        try: style.theme_use("clam")
        except: pass
        bg="#101216"; panel="#191c21"; fg="#f4f1ee"; muted="#b9b7b5"; line="#34383e"
        self.root.configure(bg=bg)
        style.configure(".",background=bg,foreground=fg,fieldbackground=panel,bordercolor=line,lightcolor=line,darkcolor=line,focuscolor="#e52d22")
        style.configure("TFrame",background=bg)
        style.configure("TLabel",background=bg,foreground=fg)
        style.configure("TLabelframe",background=panel,foreground=fg,bordercolor=line)
        style.configure("TLabelframe.Label",background=panel,foreground=fg)
        style.configure("TButton",background="#292326",foreground=fg,bordercolor="#6b3732",padding=(10,7),focuscolor="#e52d22")
        style.map("TButton",background=[("active","#5b1714"),("pressed","#8c201a")],foreground=[("disabled","#888888")])
        style.configure("TEntry",fieldbackground="#17191d",foreground=fg,insertcolor=fg)
        style.configure("TCombobox",fieldbackground="#17191d",background="#292326",foreground=fg,arrowcolor=fg)
        style.map("TCombobox",fieldbackground=[("readonly","#17191d")],foreground=[("readonly",fg)])
        style.configure("Treeview",background="#17191d",fieldbackground="#17191d",foreground=fg)
        style.map("Treeview",background=[("selected","#6d201b")],foreground=[("selected","#ffffff")])
        style.configure("TProgressbar",background="#e52d22",troughcolor="#292c31")
        top=tk.Frame(self.root,bg="#171a1f",height=48,highlightthickness=1,highlightbackground="#34383e")
        top.pack(fill="x"); top.pack_propagate(False)
        tk.Label(top,text="🎬",font=("Segoe UI",19),bg="#171a1f",fg="#f1ddd0").pack(side="left",padx=(16,8))
        tk.Label(top,text="Karabudak Film Stüdyoları",font=("Segoe UI",16,"bold"),bg="#171a1f",fg="#f7f3f0").pack(side="left")
        tk.Label(top,text="v"+APP_VERSION,font=("Segoe UI",12),bg="#171a1f",fg="#c9c5c1").pack(side="left",padx=16)
        shell=tk.Frame(self.root,bg=bg); shell.pack(fill="both",expand=True)
        side=tk.Frame(shell,bg="#15181d",width=252,highlightthickness=1,highlightbackground="#30343a")
        side.pack(side="left",fill="y"); side.pack_propagate(False)
        tk.Button(side,text="☰",font=("Segoe UI",22),bg="#15181d",fg="#eeeeee",activebackground="#30343a",activeforeground="white",relief="flat",bd=0,command=self.toggle_menu).pack(anchor="w",padx=16,pady=(8,14))
        try: style.layout("Hidden.TNotebook.Tab", [])
        except Exception: pass
        style.configure("Hidden.TNotebook",background=bg,borderwidth=0)
        nb=ttk.Notebook(shell,style="Hidden.TNotebook"); nb.pack(side="left",fill="both",expand=True)
        self.menu_popup=None
        self.editor=ttk.Frame(nb,padding=10); nb.add(self.editor,text="Video düzenleme / sahneler")
        self.library=ttk.Frame(nb,padding=10); nb.add(self.library,text="Video kütüphanem")
        self.characters_tab=ttk.Frame(nb,padding=10); nb.add(self.characters_tab,text="Karakter stüdyosu")
        self.writer_tab=ttk.Frame(nb,padding=10); nb.add(self.writer_tab,text="Senarist")
        self.update_tab=ttk.Frame(nb,padding=24); nb.add(self.update_tab,text="Güncelleme")
        self.home_tab=tk.Frame(nb,bg="#101216"); nb.insert(0,self.home_tab,text="Ana Sayfa")
        self.old_edit_tab=ttk.Frame(nb,padding=18); nb.add(self.old_edit_tab,text="Eski Videoyu Düzenle")
        nav=[("⌂","Ana Sayfa",0),("🎬","Video Oluştur",1),("♟","Karakter Stüdyosu",3),("▤","Senaryo Yazarı",4),("▣","Sahne Düzenleyici",1),("▱","Video Projeleri / Arşiv",2),("▶","Video Kütüphanesi",2),("✂","Eski Videoyu Düzenle",6),("⟳","Güncelleme",5)]
        self.nav_buttons=[]
        for icon,label,index in nav:
            b=tk.Button(side,text=f"  {icon}    {label}",anchor="w",font=("Segoe UI",12),bg="#15181d",fg="#f2f0ee",activebackground="#6e1714",activeforeground="white",relief="flat",bd=0,padx=10,pady=11,command=lambda i=index:self._select_tab(i))
            b.pack(fill="x",padx=10,pady=1); self.nav_buttons.append(b)
        self.build_home_tab(); self.build_editor(); self.build_library(); self.build_characters(); self.build_writer(); self.build_update_tab(); self.build_old_edit_tab()
        self._apply_dark_widgets(self.root)
        nb.select(self.home_tab)
        self.main_notebook=nb

    def _apply_dark_widgets(self, parent):
        for child in parent.winfo_children():
            try:
                if isinstance(child, (tk.Text, tk.Listbox)):
                    child.configure(bg="#171717",fg="#f2f2f2",insertbackground="#ffffff",
                                    selectbackground="#555555",selectforeground="#ffffff",
                                    highlightbackground="#444444",highlightcolor="#ffffff",
                                    relief="flat",bd=1)
                elif isinstance(child, tk.Canvas):
                    child.configure(bg="#ffffff",highlightthickness=0)
            except Exception:
                pass
            self._apply_dark_widgets(child)

    def build_home_tab(self):
        """Sinematik stüdyo ana ekranı: yüksek çözünürlüklü fon ve hızlı erişim kartları."""
        self.home_tab.configure(bg="#0b0d11")
        hero=tk.Canvas(self.home_tab,bg="#0b0d11",height=600,highlightthickness=0)
        hero.pack(fill="both",expand=True)

        def make_backdrop(w,h):
            W,H=max(1000,w)*2,max(600,h)*2
            im=Image.new("RGB",(W,H))
            pix=im.load()
            top=(8,11,17); bottom=(42,25,22)
            for y in range(H):
                t=y/max(1,H-1); c=tuple(int(top[i]*(1-t)+bottom[i]*t) for i in range(3))
                for x in range(W): pix[x,y]=c
            glow=Image.new("RGBA",(W,H),(0,0,0,0)); gd=ImageDraw.Draw(glow)
            gd.polygon([(W*.48,0),(W*.88,0),(W*.72,H*.76),(W*.38,H*.76)],fill=(230,155,94,38))
            glow=glow.filter(ImageFilter.GaussianBlur(85))
            im=Image.alpha_composite(im.convert("RGBA"),glow)
            d=ImageDraw.Draw(im,"RGBA")
            d.rectangle((0,H*.70,W,H),fill=(5,7,10,245))
            d.line((0,H*.70,W,H*.70),fill=(174,119,81,100),width=4)
            # Film makaraları
            for cx,cy,r in [(W*.12,H*.72,H*.18),(W*.29,H*.75,H*.12)]:
                cx,cy,r=int(cx),int(cy),int(r)
                d.ellipse((cx-r,cy-r,cx+r,cy+r),fill=(12,15,20,255),outline=(190,139,93,255),width=10)
                d.ellipse((cx-r*.70,cy-r*.70,cx+r*.70,cy+r*.70),outline=(107,76,56,255),width=8)
                d.ellipse((cx-r*.22,cy-r*.22,cx+r*.22,cy+r*.22),fill=(4,6,9,255),outline=(205,157,111,255),width=6)
                for a in range(0,360,60):
                    import math
                    xx=cx+int(r*.47*math.cos(math.radians(a))); yy=cy+int(r*.47*math.sin(math.radians(a)))
                    rr=int(r*.12); d.ellipse((xx-rr,yy-rr,xx+rr,yy+rr),fill=(4,6,9,255),outline=(134,97,68,255),width=4)
            # Türk bayrağı
            fx,fy,fw,fh=int(W*.80),int(H*.24),int(W*.17),int(H*.23)
            d.rounded_rectangle((fx,fy,fx+fw,fy+fh),radius=10,fill=(145,19,25,255),outline=(221,180,151,130),width=3)
            mx,my,mr=fx+int(fw*.40),fy+int(fh*.50),int(fh*.29)
            d.ellipse((mx-mr,my-mr,mx+mr,my+mr),fill=(255,248,235,255))
            d.ellipse((mx-mr*.52,my-mr*.82,mx+mr*1.08,my+mr*.82),fill=(145,19,25,255))
            pts=[]
            for k in range(10):
                a=-math.pi/2+k*math.pi/5; rr=mr*(.38 if k%2==0 else .16)
                pts.append((mx+int(fw*.21)+rr*math.cos(a),my+rr*math.sin(a)))
            d.polygon(pts,fill=(255,248,235,255))
            # Kamera gövdesi, lens ve tripod
            cx,cy=int(W*.65),int(H*.51)
            d.rounded_rectangle((cx-W*.105,cy-H*.10,cx+W*.13,cy+H*.08),radius=28,fill=(14,19,25,255),outline=(184,133,88,255),width=9)
            d.polygon([(cx+W*.12,cy-H*.08),(cx+W*.22,cy-H*.14),(cx+W*.22,cy+H*.12),(cx+W*.12,cy+H*.06)],fill=(12,16,22,255),outline=(184,133,88,255))
            d.ellipse((cx-H*.12,cy-H*.22,cx+H*.12,cy+H*.02),fill=(5,8,13,255),outline=(212,162,111,255),width=9)
            d.ellipse((cx-H*.08,cy-H*.18,cx+H*.08,cy-H*.02),fill=(19,39,52,255),outline=(107,153,169,255),width=6)
            d.ellipse((cx-H*.04,cy-H*.14,cx+H*.04,cy-H*.06),fill=(2,5,9,255),outline=(194,151,105,255),width=5)
            d.line((cx-W*.02,cy+H*.08,cx-W*.10,H*.91),fill=(130,91,61,255),width=14)
            d.line((cx+W*.05,cy+H*.08,cx+W*.12,H*.91),fill=(130,91,61,255),width=14)
            d.line((cx+W*.01,cy+H*.08,cx+W*.015,H*.91),fill=(130,91,61,255),width=12)
            # Klaket
            kx,ky,kw,kh=int(W*.42),int(H*.67),int(W*.13),int(H*.13)
            d.rounded_rectangle((kx,ky,kx+kw,ky+kh),radius=9,fill=(17,20,25,255),outline=(197,147,102,255),width=5)
            d.rectangle((kx,ky,kx+kw,ky+kh*.23),fill=(208,198,183,255))
            for xx in range(kx,kx+kw,30):
                d.polygon([(xx,ky),(xx+15,ky),(xx+29,ky+kh*.23),(xx+14,ky+kh*.23)],fill=(30,32,35,255))
            d.text((kx+12,ky+kh*.43),"KARABUDAK",font=font(max(13,int(H*.018)),True),fill=(245,225,204,255))
            im=im.convert("RGB").resize((w,h),Image.Resampling.LANCZOS)
            return ImageTk.PhotoImage(im)

        def paint(event=None):
            hero.delete("all")
            w=max(hero.winfo_width(),900); h=max(hero.winfo_height(),560)
            self._home_backdrop=make_backdrop(w,h)
            hero.create_image(0,0,anchor="nw",image=self._home_backdrop)
            hero.create_rectangle(24,24,w*.47,h*.40,fill="#080a0e",outline="#704b38",width=1,stipple="gray50")
            hero.create_text(48,h*.105,anchor="w",text="KARABUDAK",font=("Georgia",34,"bold"),fill="#f0dfce")
            hero.create_text(50,h*.18,anchor="w",text="FİLM STÜDYOLARI",font=("Georgia",20,"bold"),fill="#d7a17c")
            hero.create_rectangle(50,h*.225,w*.34,h*.225+3,fill="#c52b25",outline="")
            hero.create_text(50,h*.29,anchor="w",text="Fikrinden filme, kendi hikâyeni üret.",font=("Segoe UI",12),fill="#e8ded5")
            hero.create_text(50,h*.35,anchor="w",text="YAZ  •  TASARLA  •  KURGULA  •  YAYINLA",font=("Segoe UI",9,"bold"),fill="#c8a68e")
            labels=[("🎬","YENİ VİDEO","Oluştur",1),("♟","KARAKTER","Stüdyosu",3),("▤","SENARYO","Yazarı",4),("▣","SAHNE","Düzenleyici",1),("▱","VİDEO","Arşivi",2)]
            gap=12; left=22; cardw=(w-left*2-gap*4)/5; top=h-142
            for i,(ico,a,b,idx) in enumerate(labels):
                x=left+i*(cardw+gap); active=i==0; tag=f"home_card_{i}"
                rect=hero.create_rectangle(x,top,x+cardw,top+112,fill="#351819" if active else "#17191e",outline="#d83a30" if active else "#675047",width=2,tags=(tag,))
                hero.create_text(x+cardw/2,top+30,text=ico,font=("Segoe UI Symbol",27),fill="#f2d9c7",tags=(tag,))
                hero.create_text(x+cardw/2,top+66,text=a,font=("Segoe UI",11,"bold"),fill="#fff8f1",tags=(tag,))
                hero.create_text(x+cardw/2,top+88,text=b,font=("Segoe UI",10),fill="#d5c6bb",tags=(tag,))
                hero.tag_bind(tag,"<Button-1>",lambda e,j=idx:self._select_tab(j))
            hero.create_rectangle(0,h-23,w,h,fill="#111419",outline="#3c3432")
            hero.create_text(20,h-11,anchor="w",text="●  STÜDYO HAZIR     |     Karabudak Film Stüdyoları  v"+APP_VERSION,font=("Segoe UI",9),fill="#e6ded8")
        hero.bind("<Configure>",paint)
        self.home_hero=hero

    def toggle_menu(self):
        if self.menu_popup is not None and self.menu_popup.winfo_exists():
            self.menu_popup.destroy()
            self.menu_popup=None
            return
        # Menü ayrı bir pencere açmaz; ana uygulama yüzeyinin üzerinde açılan paneldir.
        panel=ttk.Frame(self.root,padding=12,relief="solid")
        self.menu_popup=panel
        panel.configure(style="TFrame")
        panel.place(x=10,y=58,width=270)
        panel.lift()
        ttk.Label(panel,text="BÖLÜMLER",font=("Segoe UI",11,"bold")).pack(anchor="w",pady=(0,8))
        items=[("Başlangıç",0),("Video düzenleme / sahneler",1),("Video kütüphanem",2),("Karakter stüdyosu",3),("Senarist",4),("Güncelleme",5),("Eski Videoyu Düzenle",6)]
        for label,index in items:
            ttk.Button(panel,text=label,command=lambda i=index:self._select_tab(i)).pack(fill="x",pady=3)


    def _select_tab(self, index):
        # Notebook, root'un doğrudan çocuğu değil shell çerçevesinin içindedir.
        # Bu nedenle root.winfo_children() taraması sekmeyi bulamıyordu.
        nb = getattr(self, "main_notebook", None)
        if nb is not None and nb.winfo_exists():
            tabs = nb.tabs()
            if 0 <= index < len(tabs):
                nb.select(tabs[index])
        if self.menu_popup is not None:
            try: self.menu_popup.destroy()
            except Exception: pass
            self.menu_popup=None

    def start_wizard(self):
        self.wizard_data={"platform":"YouTube yatay video","character":"Karakter kullanma","voice":"Erkek — Ahmet","caption":"Türkçe altyazı","script":""}
        self.wizard_step=0
        win=tk.Toplevel(self.root); self.wizard_win=win
        win.title("Yeni Video — Adım adım kurulum"); win.geometry("700x520"); win.transient(self.root)
        # Sihirbaz modal değildir: kullanıcı karakter stüdyosu ve senarist sekmelerine geçebilir.
        self.wizard_body=ttk.Frame(win,padding=22); self.wizard_body.pack(fill="both",expand=True)
        self.wizard_footer=ttk.Frame(win,padding=(22,8)); self.wizard_footer.pack(fill="x")
        self.wizard_back_btn=ttk.Button(self.wizard_footer,text="← Geri",command=self.wizard_back)
        self.wizard_back_btn.pack(side="left")
        self.wizard_next_btn=ttk.Button(self.wizard_footer,text="Devam →",command=self.wizard_next)
        self.wizard_next_btn.pack(side="right")
        self.wizard_render()

    def wizard_render(self):
        for w in self.wizard_body.winfo_children(): w.destroy()
        titles=["Video hangi platform için?","Karakterlerini seç","Ses sistemini belirle","Altyazı dili","Senaryonu ekle","Kontrol ve sahne hazırlığı"]
        ttk.Label(self.wizard_body,text=f"ADIM {self.wizard_step+1} / 6",foreground="#777").pack(anchor="w")
        ttk.Label(self.wizard_body,text=titles[self.wizard_step],font=("Segoe UI",20,"bold")).pack(anchor="w",pady=(6,18))
        d=self.wizard_data
        if self.wizard_step==0:
            self.w_platform=tk.StringVar(value=d["platform"])
            for v in ["YouTube yatay video","YouTube Shorts","Instagram Reels","Instagram Hikâye","TikTok","Diğer dikey kısa video","Özel format"]:
                ttk.Radiobutton(self.wizard_body,text=v,variable=self.w_platform,value=v).pack(anchor="w",pady=4)
        elif self.wizard_step==1:
            self.w_character=tk.StringVar(value=d["character"])
            opts=["Karakter kullanma","Yeni karakter oluştur ve kaydet"]+["Kayıtlı: "+c.get("name","Karakter") for c in self.project.get("characters",[])]
            ttk.Label(self.wizard_body,text="Yeni karakter oluşturmayı seçersen karakter stüdyosunda fotoğrafını ve tarifini kaydedebilirsin.",wraplength=600).pack(anchor="w",pady=(0,12))
            self.w_char_combo=ttk.Combobox(self.wizard_body,textvariable=self.w_character,values=opts,state="readonly",width=48); self.w_char_combo.pack(anchor="w")
            ttk.Button(self.wizard_body,text="Karakter stüdyosunu aç",command=lambda:self._select_tab(3)).pack(anchor="w",pady=12)
        elif self.wizard_step==2:
            self.w_voice=tk.StringVar(value=d["voice"])
            ttk.Label(self.wizard_body,text="Anlatıcı / konuşmacı").pack(anchor="w")
            ttk.Combobox(self.wizard_body,textvariable=self.w_voice,values=["Erkek — Ahmet","Kadın — Emel","Sessiz video / konuşma yok"],state="readonly",width=42).pack(anchor="w",pady=8)
            ttk.Label(self.wizard_body,text="Sesin ayrıntılı tarzı, hızı ve seviyesi video düzenleme ekranında ayarlanabilir.",foreground="#666").pack(anchor="w",pady=10)
        elif self.wizard_step==3:
            self.w_caption=tk.StringVar(value=d["caption"])
            ttk.Label(self.wizard_body,text="Altyazı tercihi").pack(anchor="w")
            ttk.Combobox(self.wizard_body,textvariable=self.w_caption,values=["Altyazı yok","Türkçe altyazı","İngilizce altyazı","Almanca altyazı","Fransızca altyazı","İspanyolca altyazı","İtalyanca altyazı","Arapça altyazı","Rusça altyazı","Japonca altyazı","Korece altyazı","Çince altyazı"],state="readonly",width=42).pack(anchor="w",pady=8)
            ttk.Label(self.wizard_body,text="Çeviri altyazısı için internet bağlantısı gerekebilir.",foreground="#666").pack(anchor="w")
        elif self.wizard_step==4:
            ttk.Label(self.wizard_body,text="Senaryonu buraya yazabilir veya Senarist sekmesinde hazırladığın metni aktarabilirsin.",wraplength=620).pack(anchor="w",pady=(0,10))
            self.w_script=tk.Text(self.wizard_body,height=12,wrap="word",font=("Segoe UI",10),undo=True); self.w_script.pack(fill="both",expand=True)
            self.w_script.insert("1.0",d.get("script",self.project.get("script", "")))
            ttk.Button(self.wizard_body,text="Senarist sekmesine git",command=lambda:self._select_tab(4)).pack(anchor="w",pady=6)
        else:
            p=platform_profile(d["platform"])
            summary=f"Platform: {d['platform']}\nÇözünürlük: {p['size'][0]} × {p['size'][1]} ({p['ratio']})\nKare hızı: {p['fps']} FPS\nDosya: {p['format']}\nKarakter: {d['character']}\nSes: {d['voice']}\nAltyazı: {d['caption']}\n\nVideo seçilen platforma uygun boyutlarda hazırlanacak."
            ttk.Label(self.wizard_body,text=summary,justify="left",font=("Segoe UI",11)).pack(anchor="w",pady=8)
        self.wizard_back_btn.config(state="normal" if self.wizard_step>0 else "disabled")
        self.wizard_next_btn.config(text="Projeyi hazırla ✓" if self.wizard_step==5 else "Devam →")

    def _wizard_collect(self):
        d=self.wizard_data
        if self.wizard_step==0: d["platform"]=self.w_platform.get()
        elif self.wizard_step==1: d["character"]=self.w_character.get()
        elif self.wizard_step==2: d["voice"]=self.w_voice.get()
        elif self.wizard_step==3: d["caption"]=self.w_caption.get()
        elif self.wizard_step==4: d["script"]=self.w_script.get("1.0","end").strip()

    def wizard_next(self):
        self._wizard_collect()
        if self.wizard_step==4 and len(self.wizard_data.get("script", ""))<3:
            messagebox.showinfo("Senaryo gerekli","Devam etmek için senaryo metnini yaz veya Senarist sekmesinden aktar.",parent=self.wizard_win); return
        if self.wizard_step<5:
            self.wizard_step+=1; self.wizard_render(); return
        d=self.wizard_data
        self.project["platform"]=d["platform"]
        self.name_var.set("Yeni "+d["platform"])
        self.script.delete("1.0","end"); self.script.insert("1.0",d.get("script",""))
        profile=platform_profile(d["platform"])
        self.ratio.set(profile["ratio"])
        self.project["export_profile"]=dict(profile)
        self.captions.set(d["caption"]!="Altyazı yok")
        if d["voice"].startswith("Kadın"): self.voice_gender.set("Kadın"); self.filter_voice_choices()
        elif d["voice"].startswith("Erkek"): self.voice_gender.set("Erkek"); self.filter_voice_choices()
        if d["character"]=="Yeni karakter oluştur ve kaydet":
            self._select_tab(3); messagebox.showinfo("Karakter oluştur","Karakter stüdyosunda karakterini kaydet. Ardından Video oluşturma sekmesine dön.")
        self.parse_script()
        self.wizard_win.destroy()
        self._select_tab(1)
        self.set_status("Sihirbaz ayarları aktarıldı. Sahneleri ve ön izlemeyi düzenleyebilirsin.")

    def wizard_back(self):
        self._wizard_collect()
        if self.wizard_step>0: self.wizard_step-=1; self.wizard_render()

    def build_old_edit_tab(self):
        box=ttk.LabelFrame(self.old_edit_tab,text="Mevcut videoyu içe aktar",padding=16); box.pack(fill="x")
        self.old_video_path=tk.StringVar()
        row=ttk.Frame(box); row.pack(fill="x")
        ttk.Entry(row,textvariable=self.old_video_path).pack(side="left",fill="x",expand=True)
        ttk.Button(row,text="Video seç",command=self.choose_old_video).pack(side="left",padx=6)
        settings=ttk.LabelFrame(self.old_edit_tab,text="Yeni çıktı ayarları",padding=16); settings.pack(fill="x",pady=14)
        self.old_platform=tk.StringVar(value="YouTube yatay video")
        ttk.Label(settings,text="Hedef platform").grid(row=0,column=0,sticky="w")
        ttk.Combobox(settings,textvariable=self.old_platform,values=["YouTube yatay video","YouTube Shorts","Instagram Reels","Instagram Hikâye","TikTok"],state="readonly",width=30).grid(row=1,column=0,sticky="w",pady=5)
        self.old_subtitle=tk.StringVar(value="Mevcut altyazıyı koru")
        ttk.Label(settings,text="Altyazı işlemi").grid(row=0,column=1,sticky="w",padx=20)
        ttk.Combobox(settings,textvariable=self.old_subtitle,values=["Mevcut altyazıyı koru","Altyazıyı kaldır (varsa)","Yeni SRT dosyası ekle"],state="readonly",width=28).grid(row=1,column=1,sticky="w",padx=20,pady=5)
        self.old_srt=tk.StringVar()
        ttk.Button(settings,text="SRT altyazı dosyası seç",command=self.choose_old_srt).grid(row=2,column=1,sticky="w",padx=20,pady=5)
        self.old_srt_label=ttk.Label(settings,text="SRT seçilmedi",foreground="#666"); self.old_srt_label.grid(row=3,column=1,sticky="w",padx=20)
        ttk.Button(self.old_edit_tab,text="Yeni formatta dışa aktar",command=self.export_old_video).pack(anchor="w",pady=6,ipadx=10,ipady=7)
        ttk.Label(self.old_edit_tab,text="Not: Bu bölüm videoyu yeniden boyutlandırır/kadrajlar. Altyazıyı değiştirmek için SRT dosyası ekleyebilirsin. Kaynak dosyanın üzerine yazılmaz.",wraplength=850,foreground="#666").pack(anchor="w",pady=8)

    def choose_old_video(self):
        f=filedialog.askopenfilename(filetypes=[("Video dosyaları","*.mp4 *.mov *.mkv *.avi")])
        if f:self.old_video_path.set(f)

    def choose_old_srt(self):
        f=filedialog.askopenfilename(filetypes=[("Altyazı","*.srt")])
        if f:self.old_srt.set(f); self.old_srt_label.config(text=Path(f).name)

    def export_old_video(self):
        src=self.old_video_path.get().strip()
        if not src or not Path(src).exists():
            messagebox.showwarning("Video seç","Önce düzenlenecek videoyu seç."); return
        platform=self.old_platform.get(); vertical=platform!="YouTube yatay video"
        dest=filedialog.asksaveasfilename(defaultextension=".mp4",initialfile=Path(src).stem+"_yeni_format.mp4",filetypes=[("MP4 video","*.mp4")])
        if not dest:return
        w,h=(1080,1920) if vertical else (1920,1080)
        vf=f"scale={w}:{h}:force_original_aspect_ratio=decrease,pad={w}:{h}:(ow-iw)/2:(oh-ih)/2"
        cmd=[ffmpeg(),"-y","-i",src]
        if self.old_srt.get() and self.old_subtitle.get()=="Yeni SRT dosyası ekle":
            sub=self.old_srt.get().replace("\\","/").replace(":","\\:")
            vf += f",subtitles='{sub}'"
        cmd += ["-vf",vf,"-c:v","libx264","-preset","veryfast","-crf","23","-c:a","aac","-b:a","192k",dest]
        try:
            self.set_status("Eski video yeni platform formatına dönüştürülüyor…")
            subprocess.Popen(cmd).wait()
            if Path(dest).exists() and Path(dest).stat().st_size>0:
                messagebox.showinfo("Tamamlandı",f"Yeni video kaydedildi:\n{dest}")
            else: messagebox.showerror("Dönüştürme başarısız","FFmpeg çıktı oluşturamadı. Dosya biçimini kontrol et.")
        except Exception as e: messagebox.showerror("Dönüştürme hatası",str(e))

    def build_update_tab(self):
        box=ttk.LabelFrame(self.update_tab,text="Karabudak Film Stüdyoları güncelleme merkezi",padding=18)
        box.pack(fill="x",anchor="n")
        ttk.Label(box,text=f"Kurulu sürüm: {APP_VERSION}",font=("Segoe UI",12,"bold")).pack(anchor="w",pady=(0,8))
        ttk.Label(box,text="Yeni sürümü kontrol et, indirme ve kurulum aşamalarını durum çubuğundan izle. Kurulum sırasında program kapanır ve işlem tamamlanınca yeniden açılır. Proje ve video klasörlerin korunur.",wraplength=760,justify="left").pack(anchor="w",pady=(0,14))
        self.update_check_button = ttk.Button(box,text="Güncellemeleri kontrol et",command=self.check_for_updates)
        self.update_check_button.pack(anchor="w")
        self.update_status_var = tk.StringVar(value="Henüz kontrol edilmedi.")
        ttk.Label(box,textvariable=self.update_status_var,wraplength=760,justify="left",foreground="#245b8f").pack(anchor="w",pady=(12,0))
        ttk.Label(self.update_tab,text="Projelerin ve dışa aktardığın videolar güncelleme sırasında korunur. Program dosyası değiştirilmeden önce yedeklenir.",foreground="#555",wraplength=760,justify="left").pack(anchor="w",pady=16)

    def _set_update_status(self, message, checking=False):
        self.update_status_var.set(message)
        self.update_check_button.config(state=("disabled" if checking else "normal"))

    def check_for_updates(self):
        if self.busy:
            self._set_update_status("Kontrol yapılamadı: Video hazırlanırken güncelleme kontrol edilemez.")
            messagebox.showinfo("Güncelleme", "Video hazırlanırken güncelleme kontrol edilemez.")
            return
        self._set_update_status("GitHub üzerinde yeni sürüm kontrol ediliyor...", checking=True)
        self.set_status("Güncelleme kontrol ediliyor...")
        threading.Thread(target=self._check_for_updates_worker, kwargs={"silent": False}, daemon=True).start()

    def _check_for_updates_worker(self, silent=True):
        try:
            url = f"https://api.github.com/repos/{GITHUB_REPO}/releases/latest"
            req = urllib.request.Request(url, headers={"User-Agent": "VideoStudyosu-Updater", "Accept": "application/vnd.github+json"})
            with urllib.request.urlopen(req, timeout=15) as response:
                release = json.loads(response.read().decode("utf-8"))
            tag = str(release.get("tag_name", "")).lstrip("v")
            if not tag:
                raise RuntimeError("GitHub'da yayımlanmış bir sürüm bulunamadı.")
            if self._version_tuple(tag) <= self._version_tuple(APP_VERSION):
                def current():
                    self._set_update_status(f"Program güncel. Kurulu sürüm: {APP_VERSION} | Son sürüm: {tag}")
                    self.set_status("Güncelleme kontrolü tamamlandı: program güncel.")
                    if not silent:
                        messagebox.showinfo("Güncelleme", f"Program güncel.\nKurulu sürüm: {APP_VERSION}\nSon sürüm: {tag}")
                self.root.after(0, current)
                return
            patch_name = f"VideoStudyosu_Patch_from_{APP_VERSION}.zip"
            asset = next((a for a in release.get("assets", []) if a.get("name") == patch_name), None)
            package_type = "yama" if asset else "tam"
            if not asset:
                asset = next((a for a in release.get("assets", []) if a.get("name") == UPDATE_ASSET), None)
            if not asset:
                raise RuntimeError("Yeni sürüm bulundu ancak uyumlu yama veya tam kurulum paketi yayımlanmamış.")
            download_url = asset.get("browser_download_url", "")
            if not download_url:
                raise RuntimeError("Yeni sürüm paketi için indirme bağlantısı bulunamadı.")
            def found():
                self._set_update_status(f"Yeni sürüm bulundu: {tag} ({package_type} paket). Onay bekleniyor.")
                self.set_status(f"Yeni sürüm bulundu: {tag}")
                self._ask_update(tag, download_url, package_type)
            self.root.after(0, found)
        except Exception as exc:
            error_text = str(exc)
            def failed():
                self._set_update_status("Güncelleme kontrolü başarısız: " + error_text)
                self.set_status("Güncelleme kontrolü başarısız.")
                if not silent:
                    messagebox.showerror("Güncelleme kontrolü", "Güncelleme kontrol edilemedi.\n" + error_text)
            self.root.after(0, failed)

    @staticmethod
    def _version_tuple(value):
        nums = re.findall(r"\d+", str(value))
        return tuple(int(x) for x in nums[:4]) if nums else (0,)

    def _ask_update(self, version, download_url, package_type="tam"):
        accepted = messagebox.askyesno(
            "Yeni sürüm bulundu",
            f"Yeni sürüm: {version} ({package_type} paket)\\n"
            "Güncellemeyi şimdi indirip kurmak ister misiniz?\\n"
            "Projeleriniz ve dışa aktardığınız videolar korunur."
        )
        if not accepted:
            self.set_status("Güncelleme kullanıcı tarafından iptal edildi.")
            return
        threading.Thread(
            target=self._download_and_install_update,
            args=(version, download_url),
            daemon=True
        ).start()

    def _download_and_install_update(self, version, download_url):
        try:
            if not download_url:
                raise RuntimeError("İndirme bağlantısı bulunamadı.")
            self.root.after(0, lambda: self.set_status("Güncelleme indiriliyor..."))
            work = Path(tempfile.mkdtemp(prefix="KarabudakFilmStudyoUpdate_"))
            archive = work / "update_package.zip"
            req = urllib.request.Request(download_url, headers={"User-Agent": "KarabudakFilmStudyo-Updater"})
            with urllib.request.urlopen(req, timeout=60) as response, open(archive, "wb") as out:
                total = int(response.headers.get("Content-Length", 0) or 0)
                done = 0
                while True:
                    chunk = response.read(1024 * 1024)
                    if not chunk:
                        break
                    out.write(chunk)
                    done += len(chunk)
                    if total:
                        pct = int(done * 100 / total)
                        self.root.after(0, lambda p=pct: self.set_status(f"Güncelleme indiriliyor: %{p}"))
            self.root.after(0, lambda: self.set_status("Paket doğrulanıyor..."))
            with zipfile.ZipFile(archive, "r") as zf:
                names = zf.namelist()
                is_patch = "manifest.json" in names and "apply_patch.ps1" in names
                is_full = "Video Studyosu.exe" in names and "update_install.bat" in names
                if not (is_patch or is_full) or "update_install.bat" not in names:
                    raise RuntimeError("Güncelleme paketi eksik veya hatalı.")
                if is_patch:
                    manifest = json.loads(zf.read("manifest.json").decode("utf-8"))
                    if str(manifest.get("from_version", "")) != APP_VERSION:
                        raise RuntimeError("Bu yama kurulu sürümle uyumlu değil. Tam kurulum paketi gerekli.")
                    if str(manifest.get("to_version", "")) != str(version):
                        raise RuntimeError("Yama hedef sürüm bilgisi uyuşmuyor.")
                zf.extractall(work)
            if not getattr(sys, "frozen", False):
                raise RuntimeError("Otomatik EXE güncellemesi yalnızca kurulu masaüstü uygulamasında çalışır.")
            target_exe = Path(sys.executable).resolve()
            bat = work / "update_install.bat"
            self.root.after(0, lambda: self.set_status("Kurulum başlatılıyor; program kapanıp yeniden açılacak..."))
            subprocess.Popen(["cmd.exe", "/c", str(bat), str(target_exe)], cwd=str(work),
                             creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
            self.root.after(1200, self.root.destroy)
        except Exception as exc:
            self.root.after(0, lambda e=str(exc): messagebox.showerror("Güncelleme başarısız", e))

    def build_editor(self):
        left=ttk.Frame(self.editor); left.pack(side="left",fill="both",expand=True)
        right=ttk.Frame(self.editor,width=330); right.pack(side="right",fill="y",padx=(12,0))
        row=ttk.Frame(left); row.pack(fill="x")
        ttk.Label(row,text="Proje adı").pack(side="left")
        self.name_var=tk.StringVar(value=self.project["name"])
        ttk.Entry(row,textvariable=self.name_var).pack(side="left",fill="x",expand=True,padx=8)
        ttk.Button(row,text="Projeyi kaydet",command=self.save_project).pack(side="left")
        ttk.Button(row,text="Proje aç",command=self.load_project).pack(side="left",padx=5)
        ttk.Label(left,text="Hikâyeni/metnini buraya yapıştır. Paragraflar ayrı sahnelere dönüşür.",font=("Segoe UI",10,"bold")).pack(anchor="w",pady=(12,4))
        self.script=tk.Text(left,height=10,wrap="word",font=("Segoe UI",10),undo=True)
        self.script.pack(fill="x")
        controls=ttk.Frame(left); controls.pack(fill="x",pady=6)
        ttk.Button(controls,text="Metni sahnelere ayır",command=self.parse_script).pack(side="left")
        ttk.Button(controls,text="Sahne ekle",command=self.add_scene).pack(side="left",padx=5)
        ttk.Button(controls,text="Seçili sahneyi sil",command=self.delete_scene).pack(side="left")
        self.scene_list=tk.Listbox(left,height=8,exportselection=False,font=("Segoe UI",10))
        self.scene_list.pack(fill="both",expand=True)
        self.scene_list.bind("<<ListboxSelect>>",self.select_scene)
        editbar=ttk.Frame(left); editbar.pack(fill="x",pady=(8,3))
        ttk.Label(editbar,text="Seçili sahne metni").pack(side="left")
        ttk.Button(editbar,text="Metni uygula",command=self.apply_scene_text).pack(side="right")
        self.scene_text=tk.Text(left,height=4,wrap="word",font=("Segoe UI",10))
        self.scene_text.pack(fill="x")
        # Ön izleme / sahne tasarım asistanı
        preview_box=ttk.LabelFrame(left,text="Sahne ön izlemesi ve tasarım asistanı",padding=8)
        preview_box.pack(fill="both",expand=True,pady=(8,4))
        preview_top=ttk.Frame(preview_box); preview_top.pack(fill="x")
        ttk.Button(preview_top,text="SEÇİLİ SAHNEYİ AI İLE OLUŞTUR",command=self.generate_comfy_visual).pack(side="left")
        ttk.Button(preview_top,text="TÜM SAHNELERİ AI İLE OLUŞTUR",command=self.generate_all_comfy_visuals).pack(side="left",padx=5)
        ttk.Button(preview_top,text="VİDEOYU OLUŞTUR",command=self.create_video).pack(side="left",padx=5)
        self.comfy_url_var=tk.StringVar(value="http://127.0.0.1:8188")
        self.comfy_workflow_var=tk.StringVar(value="")
        self.comfy_status=ttk.Label(preview_box,text="Otomatik görsel motoru: Kurulu yerel motor aranır ve gerekirse kendisi başlatılır.",foreground="#777")
        self.comfy_status.pack(anchor="w")
        self.preview_label=ttk.Label(preview_box,text="Bir sahne seçip ön izleme oluştur.",anchor="center")
        self.preview_label.pack(fill="both",expand=True,pady=4)
        self.preview_photo=None
        request_row=ttk.Frame(preview_box); request_row.pack(fill="x")
        ttk.Label(request_row,text="Şunu değiştir:").pack(side="left")
        self.visual_request_var=tk.StringVar()
        ttk.Entry(request_row,textvariable=self.visual_request_var).pack(side="left",fill="x",expand=True,padx=6)
        ttk.Button(request_row,text="Uygula ve yeniden çiz",command=self.apply_visual_request).pack(side="right")
        order=ttk.Frame(left); order.pack(fill="x",pady=5)
        ttk.Button(order,text="↑ Yukarı",command=lambda:self.move_scene(-1)).pack(side="left")
        ttk.Button(order,text="↓ Aşağı",command=lambda:self.move_scene(1)).pack(side="left",padx=5)
        ttk.Button(order,text="Görsel seç",command=self.choose_image).pack(side="left",padx=5)
        ttk.Button(order,text="Varsayılan görsele dön",command=self.reset_scene_image).pack(side="left",padx=5)
        ttk.Button(order,text="Kendi sesimi seç",command=self.choose_audio).pack(side="left")
        

        ttk.Label(right,text="Video ayarları",font=("Segoe UI",12,"bold")).pack(anchor="w")
        self.ratio=tk.StringVar(value="16:9")
        ttk.Label(right,text="Video formatı").pack(anchor="w",pady=(10,2))
        ttk.Combobox(right,textvariable=self.ratio,values=["16:9","9:16"],state="readonly").pack(fill="x")
        self.captions=tk.BooleanVar(value=True)
        ttk.Checkbutton(right,text="Altyazı ekle",variable=self.captions).pack(anchor="w",pady=6)
        ttk.Label(right,text="Türkçe yapay ses (kendi sesin seçilmemiş sahnelerde)").pack(anchor="w",pady=(8,2))
        self.voice_gender=tk.StringVar(value="Erkek")
        gender_box=ttk.Combobox(right,textvariable=self.voice_gender,values=["Erkek","Kadın"],state="readonly")
        gender_box.pack(fill="x")
        gender_box.bind("<<ComboboxSelected>>",lambda _e:self.filter_voice_choices())
        ttk.Label(right,text="Ses modeli / konuşmacı").pack(anchor="w",pady=(7,2))
        self.voice=tk.StringVar(value="tr-TR-AhmetNeural")
        self.voice_catalog={
            "tr-TR-AhmetNeural":{"label":"Ahmet — Türkçe erkek, doğal","gender":"Male"},
            "tr-TR-EmelNeural":{"label":"Emel — Türkçe kadın, doğal","gender":"Female"},
        }
        self.voice_combo=ttk.Combobox(right,textvariable=self.voice,state="readonly",width=30)
        self.voice_combo.pack(fill="x")
        self.filter_voice_choices()
        ttk.Button(right,text="Kullanılabilir sesleri yenile",command=self.refresh_voice_catalog).pack(fill="x",pady=(4,2))
        self.voice_status=ttk.Label(right,text="Edge Neural sesleri • İnternet gerekir",foreground="#555",wraplength=280)
        self.voice_status.pack(anchor="w")
        self.voice_style_vars={}
        styles_frame=ttk.LabelFrame(right,text="Konuşma tarzı (birden fazla seçebilirsin)",padding=6)
        styles_frame.pack(fill="x",pady=(8,4))
        for style_name in ["Dini / manevi","Korkulu / ürpertici","Yavaş","Hızlı","Davudi","Tok ve güçlü","Duygusal","Sakin","Otoriter","Gizemli","Belgesel anlatımı","Masalsı"]:
            var=tk.BooleanVar(value=False)
            self.voice_style_vars[style_name]=var
            ttk.Checkbutton(styles_frame,text=style_name,variable=var).pack(anchor="w")
        ttk.Label(right,text="Konuşma hızı").pack(anchor="w",pady=(8,2))
        self.rate=tk.IntVar(value=0)
        ttk.Scale(right,from_=-30,to=30,variable=self.rate,orient="horizontal").pack(fill="x")
        ttk.Label(right,text="Ses seviyesi").pack(anchor="w",pady=(6,2))
        self.voice_vol=tk.IntVar(value=100)
        ttk.Scale(right,from_=30,to=150,variable=self.voice_vol,orient="horizontal").pack(fill="x")
        ttk.Label(right,text="Kendi ses kaydın: sahne seçip 'Kendi sesimi seç' ile WAV/MP3 ekle.").pack(anchor="w",pady=(12,4))
        ttk.Label(right,text="Arka plan müziği").pack(anchor="w",pady=(8,2))
        self.music_label=ttk.Label(right,text="Seçilmedi",wraplength=290)
        self.music_label.pack(anchor="w")
        ttk.Button(right,text="Müzik dosyası seç",command=self.choose_music).pack(fill="x",pady=4)
        ttk.Label(right,text="Müzik seviyesi").pack(anchor="w",pady=(8,2))
        self.music_vol=tk.IntVar(value=12)
        ttk.Scale(right,from_=0,to=40,variable=self.music_vol,orient="horizontal").pack(fill="x")
        ttk.Label(right,text="Görsel efekt paketi").pack(anchor="w",pady=(9,2))
        self.visual_effect=tk.StringVar(value="Sinematik")
        ttk.Combobox(right,textvariable=self.visual_effect,values=list(VIDEO_EFFECT_PRESETS),state="readonly").pack(fill="x")
        ttk.Label(right,text="Efektler FFmpeg ile yerel uygulanır; ek API veya abonelik gerekmez.",foreground="#777",wraplength=280).pack(anchor="w",pady=(3,2))
        ttk.Separator(right).pack(fill="x",pady=12)
        ttk.Button(right,text="VİDEOYU OLUŞTUR",command=self.create_video).pack(fill="x",ipady=10)
        self.progress=ttk.Progressbar(right,mode="indeterminate")
        self.progress.pack(fill="x",pady=8)
        self.status=ttk.Label(right,text="Hazır",wraplength=300)
        self.status.pack(anchor="w")
        ttk.Label(right,text="Görsel motoru 2.0: Sahne metnine göre farklı yerel sinematik kompozisyonlar üretir; gerçek AI resmi değildir.",wraplength=300,foreground="#666").pack(anchor="w",pady=15)

    def build_library(self):
        ttk.Label(self.library,text="Bu bilgisayarda oluşturulan videolar",font=("Segoe UI",12,"bold")).pack(anchor="w")
        self.lib_list=tk.Listbox(self.library,font=("Segoe UI",10),height=24,exportselection=False)
        self.lib_list.pack(fill="both",expand=True,pady=8)
        self.lib_list.bind("<Double-Button-1>",lambda e:self.play_selected())
        bar=ttk.Frame(self.library); bar.pack(fill="x")
        ttk.Button(bar,text="Listeyi yenile",command=self.refresh_library).pack(side="left")
        ttk.Button(bar,text="Videoyu oynat",command=self.play_selected).pack(side="left",padx=5)
        ttk.Button(bar,text="Klasörü aç",command=self.open_selected_folder).pack(side="left")
        ttk.Button(bar,text="Videoyu sil",command=self.delete_video).pack(side="left",padx=5)
        ttk.Button(bar,text="YouTube yayın paketi hazırla",command=self.youtube_package).pack(side="left",padx=5)
        ttk.Label(self.library,text=f"Kayıt klasörü: {OUT_ROOT}",foreground="#666").pack(anchor="w",pady=8)

    def build_writer(self):
        """Ücretsiz, çevrimdışı kural/şablon tabanlı yardımcı senarist."""
        ttk.Label(self.writer_tab,text="Senarist",font=("Segoe UI",16,"bold")).pack(anchor="w")
        ttk.Label(self.writer_tab,text="Fikrini yaz; taslak hikâye, karakterler, sahneler ve diyaloglar oluştur. Metnin tamamı düzenlenebilir. Bu ücretsiz sürüm gerçek bir dil modeli değildir; internet/API kullanmadan şablon ve kurallarla çalışır.",wraplength=980).pack(anchor="w",pady=(4,10))
        form=ttk.Frame(self.writer_tab); form.pack(fill="x")
        ttk.Label(form,text="Hikâye fikrin").grid(row=0,column=0,sticky="w")
        self.writer_idea=tk.Text(form,height=4,wrap="word",font=("Segoe UI",10),undo=True)
        self.writer_idea.grid(row=1,column=0,columnspan=4,sticky="ew",pady=(3,8))
        ttk.Label(form,text="Tür").grid(row=2,column=0,sticky="w")
        self.writer_genre=tk.StringVar(value="Korku / gizem")
        ttk.Combobox(form,textvariable=self.writer_genre,values=["Korku / gizem","Dram","Komedi","Macera","Bilim kurgu","Tarihî","Fantastik","Belgesel / anlatı"],state="readonly",width=22).grid(row=3,column=0,sticky="w",pady=3)
        ttk.Label(form,text="Ana karakter adı").grid(row=2,column=1,sticky="w",padx=8)
        self.writer_hero=tk.StringVar(value="Murat")
        ttk.Entry(form,textvariable=self.writer_hero,width=20).grid(row=3,column=1,sticky="ew",padx=8)
        ttk.Label(form,text="İkinci karakter adı").grid(row=2,column=2,sticky="w",padx=8)
        self.writer_other=tk.StringVar(value="Ayşe")
        ttk.Entry(form,textvariable=self.writer_other,width=20).grid(row=3,column=2,sticky="ew",padx=8)
        ttk.Label(form,text="Bölüm uzunluğu").grid(row=2,column=3,sticky="w",padx=8)
        self.writer_length=tk.StringVar(value="Kısa (5-7 sahne)")
        ttk.Combobox(form,textvariable=self.writer_length,values=["Kısa (5-7 sahne)","Orta (8-10 sahne)","Uzun (11-14 sahne)"],state="readonly",width=20).grid(row=3,column=3,sticky="ew",padx=8)
        form.columnconfigure(0,weight=3); form.columnconfigure(1,weight=1); form.columnconfigure(2,weight=1); form.columnconfigure(3,weight=1)
        actions=ttk.Frame(self.writer_tab); actions.pack(fill="x",pady=8)
        ttk.Button(actions,text="Fikri geliştir ve senaryo taslağı oluştur",command=self.generate_writer_draft).pack(side="left")
        ttk.Button(actions,text="Taslağı kaydet",command=self.save_writer_draft).pack(side="left",padx=6)
        ttk.Button(actions,text="Video oluşturma bölümüne aktar",command=self.send_writer_to_editor).pack(side="left")
        ttk.Button(actions,text="Yeniden Başla",command=self.reset_writer).pack(side="right")
        ttk.Label(self.writer_tab,text="Senaryo taslağı — istediğin yeri doğrudan değiştirebilirsin",font=("Segoe UI",10,"bold")).pack(anchor="w")
        self.writer_output=tk.Text(self.writer_tab,wrap="word",font=("Consolas",10),undo=True)
        self.writer_output.pack(fill="both",expand=True,pady=5)
        self.writer_status=ttk.Label(self.writer_tab,text="Henüz taslak oluşturulmadı. Taslaklar senin kontrolündedir.",foreground="#555")
        self.writer_status.pack(anchor="w")

    def reset_writer(self):
        has_content = bool(self.writer_idea.get("1.0","end").strip() or self.writer_output.get("1.0","end").strip())
        if has_content and not messagebox.askyesno("Senariste yeniden başla","Mevcut fikir ve taslak temizlensin mi? Kaydetmediğin metin kaybolur.",parent=self.root):
            return
        self.writer_idea.delete("1.0","end")
        self.writer_output.delete("1.0","end")
        self.writer_genre.set("Korku / gizem")
        self.writer_hero.set("Murat")
        self.writer_other.set("Ayşe")
        self.writer_length.set("Kısa (5-7 sahne)")
        self.writer_status.config(text="Yeni senaryo için hazırsın. Fikrini yazıp başlayabilirsin.")
        self.writer_idea.focus_set()

    def generate_writer_draft(self):
        idea=self.writer_idea.get("1.0","end").strip()
        if len(idea)<8:
            messagebox.showinfo("Fikir gerekli","Hikâyenin temel fikrini birkaç cümleyle yaz."); return
        genre=self.writer_genre.get(); a=self.writer_hero.get().strip() or "Murat"; b=self.writer_other.get().strip() or "Ayşe"
        count={"Kısa (5-7 sahne)":6,"Orta (8-10 sahne)":9,"Uzun (11-14 sahne)":12}.get(self.writer_length.get(),6)
        beats=[
            ("AÇILIŞ — DÜNYAYI KUR",f"{a}, sıradan görünen bir günün içinde fikrin merkezindeki tuhaflıkla karşılaşır. {idea}"),
            ("İLK İPUCU",f"{a} olayın tesadüf olmadığını düşündüren küçük ama rahatsız edici bir ayrıntı fark eder. {b}, bunun üzerinde durmamasını söyler."),
            ("İLK YÜZLEŞME",f"{a}: ‘Bunun bir açıklaması olmalı.’\n{b}: ‘Ya açıklaması sandığımızdan daha kötüyse?’\nİkili, gerçeği araştırmaya karar verir."),
            ("GERİ DÖNÜŞÜ OLMAYAN KARAR",f"Araştırma onları güvenli alanlarının dışına çıkarır. {a}, geri dönme fırsatı varken devam etmeyi seçer."),
            ("ORTA NOKTA — GERÇEK DEĞİŞİYOR",f"Yeni bir kanıt, başta doğru sandıkları şeyi tersine çevirir. {b} önemli bir ayrıntıyı sakladığını itiraf eder."),
            ("KRİZ",f"Planları bozulur. {a} ile {b} birbirlerinden şüphe etmeye başlar. Tehlike artık uzakta değil, hemen yanlarındadır."),
            ("YÜZLEŞME",f"{a}, en büyük korkusuyla yüzleşir ve çözüm için bedel ödemesi gerektiğini anlar."),
            ("TERS KÖŞE",f"Son anda ortaya çıkan ayrıntı, olayların arkasındaki kişinin veya sebebin ilk bakışta görünen olmadığını gösterir."),
            ("FİNAL",f"{a} bir seçim yapar. Olayın ana düğümü çözülür; ancak son görüntü yeni bir soruyu açık bırakır."),
            ("SONRAKİ BÖLÜME KANCA",f"Sessizlik çöker. Ardından daha önce açıklanamayan bir işaret yeniden belirir. Hikâye burada kesilir.")]
        if "Komedi" in genre:
            beats[2]=(beats[2][0],f"{a}: ‘Bence her şey kontrol altında.’\n{b}: ‘Geçen sefer de böyle dedin ve mutfağı itfaiye söndürdü.’\nİkili, giderek büyüyen bir yanlış anlaşılmanın içine düşer.")
            beats[7]=(beats[7][0],"Bütün karmaşanın sebebi beklenmedik derecede basit ama komik bir yanlış anlaşılmadır. Yine de son bir sürpriz kapıdadır.")
        elif "Dram" in genre:
            beats[2]=(beats[2][0],f"{a}: ‘Bunu yıllardır içimde taşıyorum.’\n{b}: ‘Bana güvenseydin tek başına taşımak zorunda kalmazdın.’\nİkili geçmişleriyle yüzleşir.")
            beats[7]=(beats[7][0],"Gerçek ortaya çıktığında herkesin haklı ve haksız olduğu bir taraf bulunduğu anlaşılır. Barışmak kolay olmayacaktır.")
        elif "Bilim kurgu" in genre or "Fantastik" in genre:
            beats[4]=(beats[4][0],"Buldukları kanıt, bildikleri gerçeklik kurallarının eksik olduğunu gösterir. Olay daha büyük bir düzeni etkilemektedir.")
        elif "Tarihî" in genre:
            beats[4]=(beats[4][0],"Eski bir kayıt ve mühür, bugünkü olayların geçmişte alınmış gizli bir karara dayandığını ortaya çıkarır.")
        beats=beats[:count]
        lines=[f"PROJE: {self.name_var.get().strip() or 'Yeni Hikâye'}",f"TÜR: {genre}",f"ANA FİKİR: {idea}","", "KARAKTERLER",f"{a}: Olayların merkezindeki karakter. Hedefi gerçeğe ulaşmak; temel zaafı acele karar vermek.",f"{b}: {a} için önemli bir ortak/karşı karakter. Bilgiyi saklama veya farklı bakış açısı taşıma işlevi var.","", "BÖLÜM AKIŞI"]
        for i,(heading,body) in enumerate(beats,1):
            lines += ["",f"SAHNE {i} — {heading}","MEKÂN: Hikâyenin ihtiyacına göre belirlenir.","AKSİYON: "+body,"DİYALOG:",f"{a}: ‘Burada bir şeyler ters gidiyor.’",f"{b}: ‘O zaman gerçeği öğrenmeden buradan ayrılmayalım.’"]
        lines += ["", "SENARİST NOTU", "Bu taslak başlangıç iskeletidir. Mekân, olay ayrıntıları ve diyaloglar kullanıcı tarafından düzenlenmelidir. Her sahneyi genişlet, kısalt, sil veya yeniden yaz. Taslak otomatik olarak kesin senaryo sayılmaz."]
        self.writer_output.delete("1.0","end"); self.writer_output.insert("1.0","\n".join(lines))
        self.writer_status.config(text=f"{len(beats)} sahnelik düzenlenebilir {genre.lower()} taslağı oluşturuldu. İstediğin her satırı değiştirebilirsin.")

    def save_writer_draft(self):
        content=self.writer_output.get("1.0","end").strip()
        if not content:
            messagebox.showinfo("Taslak yok","Önce bir senaryo taslağı oluştur."); return
        folder=PROJECT_ROOT/safe_name(self.name_var.get())/"senaryo_taslaklari"; folder.mkdir(parents=True,exist_ok=True)
        stamp=time.strftime("%Y%m%d_%H%M%S")
        path=folder/f"Senaryo_{stamp}.txt"
        path.write_text(content,encoding="utf-8")
        self.writer_status.config(text=f"Taslak kaydedildi: {path}")
        messagebox.showinfo("Kaydedildi",f"Senaryo taslağı kaydedildi:\n{path}")

    def send_writer_to_editor(self):
        content=self.writer_output.get("1.0","end").strip()
        if not content:
            messagebox.showinfo("Taslak yok","Önce senaryo oluştur."); return
        self.script.delete("1.0","end"); self.script.insert("1.0",content)
        self.project["script"]=content
        self.parse_script()
        self.set_status("Yardımcı Senarist taslağı video oluşturma bölümüne aktarıldı.")
        self.writer_status.config(text="Taslak aktarıldı. Video oluşturma sekmesinde sahneleri düzenleyebilirsin.")

    def build_characters(self):
        ttk.Label(self.characters_tab,text="Karakter kütüphanesi",font=("Segoe UI",14,"bold")).pack(anchor="w")
        ttk.Label(self.characters_tab,text="Karakter fotoğrafı ekle; aynı referans görselini istediğin sahnelere bağla. Bu yöntem karakteri yeniden çizmez, referans portresini sahnede gösterir.",wraplength=900).pack(anchor="w",pady=6)
        body=ttk.Frame(self.characters_tab); body.pack(fill="both",expand=True,pady=8)
        left=ttk.Frame(body); left.pack(side="left",fill="y")
        self.character_list=tk.Listbox(left,width=34,height=18,exportselection=False,selectmode="extended"); self.character_list.pack(fill="y",expand=True)
        self.character_list.bind("<<ListboxSelect>>",self.select_character)
        right=ttk.Frame(body,padding=(18,0)); right.pack(side="left",fill="both",expand=True)
        ttk.Label(right,text="Karakter adı").pack(anchor="w")
        self.character_name=tk.StringVar(); ttk.Entry(right,textvariable=self.character_name,width=50).pack(fill="x",pady=(2,10))
        ttk.Label(right,text="Karakter notu / yüz ve fiziksel görünüş tarifi").pack(anchor="w")
        self.character_desc=tk.Text(right,height=4,wrap="word"); self.character_desc.pack(fill="x",pady=(2,8))
        ttk.Label(right,text="Sabit kıyafet / aksesuar (sahneler arasında korunur)").pack(anchor="w")
        self.character_wardrobe=tk.Text(right,height=3,wrap="word")
        self.character_wardrobe.pack(fill="x",pady=(2,10))
        self.character_image_label=ttk.Label(right,text="Referans fotoğrafı seçilmedi"); self.character_image_label.pack(anchor="w",pady=4)
        ttk.Button(right,text="Farklı açılardan referans fotoğrafları ekle",command=self.choose_character_references).pack(anchor="w",pady=3)
        self.character_references_label=ttk.Label(right,text="Ek referans: yok",wraplength=650,foreground="#777")
        self.character_references_label.pack(anchor="w",pady=2)
        ttk.Button(right,text="Seçili sahneyi referanslarla karşılaştır",command=self.compare_character_reference).pack(anchor="w",pady=3)
        self.character_preview_label=ttk.Label(right,text="Karakter ön izlemesi",anchor="center"); self.character_preview_label.pack(fill="x",pady=6)
        self.character_preview_photo=None
        ttk.Button(right,text="Ön izlemeyi yenile / yeniden oluştur",command=self.refresh_character_preview).pack(anchor="w",pady=4)
        row=ttk.Frame(right); row.pack(fill="x",pady=6)
        ttk.Button(row,text="Fotoğraf seç",command=self.choose_character_image).pack(side="left")
        ttk.Button(row,text="Arka planı AI ile sil",command=self.remove_character_background).pack(side="left",padx=6)
        ttk.Button(row,text="Karakteri kaydet",command=self.save_character).pack(side="left",padx=6)
        ttk.Button(row,text="Karakteri sil",command=self.delete_character).pack(side="left")
        ttk.Separator(right).pack(fill="x",pady=14)
        ttk.Label(right,text="Seçili sahneye karakter ata").pack(anchor="w")
        self.character_scene_var=tk.StringVar()
        self.character_scene_combo=ttk.Combobox(right,textvariable=self.character_scene_var,state="readonly")
        self.character_scene_combo.pack(fill="x",pady=4)
        ttk.Button(right,text="Seçili karakteri sahneye bağla",command=self.assign_character).pack(anchor="w",pady=4)
        ttk.Label(right,text="Not: Karakter fotoğrafı, videoda küçük bir referans portresi olarak görünür. Gerçek AI karakter tutarlılığı için harici görsel üretim modeli gerekir.",wraplength=700,foreground="#666").pack(anchor="w",pady=12)
        self.character_image=""
        self.character_reference_images=[]
        self.refresh_characters()

    def refresh_characters(self):
        if not hasattr(self,"character_list"): return
        self.character_list.delete(0,"end")
        for c in self.project.get("characters",[]): self.character_list.insert("end",c.get("name","Karakter"))
        if hasattr(self,"character_scene_combo"):
            self.character_scene_combo["values"]=[f"{i+1}. {x.get('text','')[:55]}" for i,x in enumerate(self.project.get("scenes",[]))]
            if self.project.get("scenes") and not self.character_scene_var.get(): self.character_scene_combo.current(0)

    def select_character(self,event=None):
        sel=self.character_list.curselection()
        if not sel:return
        c=self.project.get("characters",[])[sel[0]]
        self.character_name.set(c.get("name","")); self.character_image=c.get("image","")
        self.character_reference_images=list(c.get("reference_images",[]))
        self.character_desc.delete("1.0","end"); self.character_desc.insert("1.0",c.get("description",""))
        self.character_wardrobe.delete("1.0","end"); self.character_wardrobe.insert("1.0",c.get("wardrobe",""))
        self.character_image_label.config(text=Path(self.character_image).name if self.character_image else "Referans fotoğrafı seçilmedi")
        self.refresh_character_references_label()
        self.refresh_character_preview()

    def compare_character_reference(self):
        selected=self.character_list.curselection()
        scene_index=self.selected_index()
        if not selected:
            messagebox.showinfo("Karakter seç","Önce karşılaştırılacak karakteri seç.")
            return
        if scene_index is None:
            messagebox.showinfo("Sahne seç","Önce görseli kontrol edilecek sahneyi seç.")
            return
        scene=self.project.get("scenes",[])[scene_index]
        generated=scene.get("image","")
        if not generated or not Path(generated).is_file():
            messagebox.showinfo("Görsel yok","Seçili sahnede karşılaştırılacak bir görsel bulunamadı.")
            return
        character=self.project.get("characters",[])[selected[0]]
        refs=[character.get("image","")]+list(character.get("reference_images",[]))
        refs=[p for p in refs if p and Path(p).is_file()]
        if not refs:
            messagebox.showinfo("Referans yok","Bu karakter için önce referans fotoğrafı ekle.")
            return
        win=tk.Toplevel(self.root); win.title("Karakter görsel kontrolü — "+character.get("name","Karakter"))
        win.geometry("900x520")
        body=ttk.Frame(win,padding=12); body.pack(fill="both",expand=True)
        ttk.Label(body,text="Karakter referansı").grid(row=0,column=0,sticky="w",padx=8)
        ttk.Label(body,text=f"Üretilen sahne {scene_index+1}").grid(row=0,column=1,sticky="w",padx=8)
        left=ttk.Label(body,text="Referans yüklenemedi"); left.grid(row=1,column=0,sticky="nsew",padx=8,pady=8)
        right=ttk.Label(body,text="Sahne görseli yüklenemedi"); right.grid(row=1,column=1,sticky="nsew",padx=8,pady=8)
        body.columnconfigure(0,weight=1); body.columnconfigure(1,weight=1); body.rowconfigure(1,weight=1)
        try:
            ref=Image.open(refs[0]).convert("RGB"); ref.thumbnail((400,400),Image.Resampling.LANCZOS)
            generated_im=Image.open(generated).convert("RGB"); generated_im.thumbnail((400,400),Image.Resampling.LANCZOS)
            left_photo=ImageTk.PhotoImage(ref); right_photo=ImageTk.PhotoImage(generated_im)
            left.configure(image=left_photo,text=""); right.configure(image=right_photo,text="")
            win._character_compare_photos=(left_photo,right_photo)
        except Exception as exc:
            messagebox.showerror("Karşılaştırma açılamadı",str(exc)); win.destroy(); return
        ttk.Label(body,text="Bu ekran yan yana görsel inceleme içindir; otomatik yüz tanıma veya benzerlik puanı üretmez.").grid(row=2,column=0,columnspan=2,sticky="w",padx=8,pady=6)

    def refresh_character_references_label(self):
        refs=getattr(self,"character_reference_images",[])
        valid=[p for p in refs if p and Path(p).is_file()]
        self.character_references_label.config(text=("Ek referanslar: "+", ".join(Path(p).name for p in valid)) if valid else "Ek referans: yok")

    def choose_character_references(self):
        paths=filedialog.askopenfilenames(title="Karakterin farklı açılardan fotoğraflarını seç",
            filetypes=[("Görsel","*.png *.jpg *.jpeg *.webp *.bmp")])
        if paths:
            current=list(getattr(self,"character_reference_images",[]))
            for path in paths:
                if path != self.character_image and path not in current:
                    current.append(path)
            self.character_reference_images=current
            self.refresh_character_references_label()
            self.set_status(f"{len(current)} ek karakter referansı kaydedilmek üzere seçildi.")

    def choose_character_image(self):
        path=filedialog.askopenfilename(filetypes=[("Görsel","*.png *.jpg *.jpeg *.webp *.bmp")])
        if path:
            self.character_image=path; self.character_image_label.config(text=Path(path).name); self.refresh_character_preview()

    def remove_character_background(self):
        if not self.character_image or not Path(self.character_image).exists():
            messagebox.showinfo("Fotoğraf gerekli","Önce karakter fotoğrafı seç.")
            return
        try:
            source=Path(self.character_image)
            target=source.with_name(source.stem+"_arkaplan_silindi.png")
            self.set_status("Ücretsiz yerel AI arka plan silme hazırlanıyor...")
            remove_image_background(str(source),str(target))
            self.character_image=str(target)
            self.character_image_label.config(text=target.name+" — şeffaf PNG")
            self.refresh_character_preview()
            self.set_status("Arka plan silindi. Şeffaf karakter görseli hazır.")
            messagebox.showinfo("Tamamlandı","Arka plan kaldırıldı. Şeffaf PNG karakter görseli olarak seçildi.")
        except Exception as exc:
            messagebox.showerror("Arka plan silinemedi",str(exc))
            self.set_status("AI arka plan silme başarısız oldu.")

    def refresh_character_preview(self):
        """Show chosen portrait or a local concept card; this is not AI image generation."""
        try:
            if self.character_image and Path(self.character_image).exists():
                im=Image.open(self.character_image).convert("RGB")
                im.thumbnail((300,300),Image.Resampling.LANCZOS)
            else:
                name=self.character_name.get().strip() or "Yeni karakter"
                desc=self.character_desc.get("1.0","end").strip()
                target=PROJECT_ROOT/"karakter_onizleme_gecici.jpg"
                make_original_visual(name+" "+desc,target,size=(480,300),seed=len(name),draw_text=True)
                im=Image.open(target).convert("RGB")
                im.thumbnail((300,190),Image.Resampling.LANCZOS)
            self.character_preview_photo=ImageTk.PhotoImage(im)
            self.character_preview_label.configure(image=self.character_preview_photo,text="")
            self.set_status("Karakter ön izlemesi yenilendi.")
        except Exception as exc:
            self.character_preview_label.configure(image="",text="Ön izleme oluşturulamadı: "+str(exc))

    def save_character(self):
        name=self.character_name.get().strip()
        if not name:
            messagebox.showwarning("Karakter adı","Karaktere bir isim ver."); return
        desc=self.character_desc.get("1.0","end").strip()
        wardrobe=self.character_wardrobe.get("1.0","end").strip()
        sel=self.character_list.curselection()
        item={"name":name,"description":desc,"wardrobe":wardrobe,"image":self.character_image,
              "reference_images":[p for p in getattr(self,"character_reference_images",[]) if p and Path(p).is_file()]}
        if sel:self.project["characters"][sel[0]]=item
        else:self.project.setdefault("characters",[]).append(item)
        self.refresh_characters(); self.character_list.selection_clear(0,"end"); self.character_list.selection_set(len(self.project["characters"])-1); self.refresh_character_preview(); self.set_status("Karakter kütüphaneye kaydedildi.")

    def delete_character(self):
        sel=self.character_list.curselection()
        if not sel:return
        deleted=sel[0]
        del self.project["characters"][deleted]
        # Keep every scene's character links aligned with the shifted character list.
        remap_character_scene_links(self.project.get("scenes",[]),deleted)
        self.character_image=""
        self.character_reference_images=[]
        self.character_list.selection_clear(0,"end")
        self.character_name.set("")
        self.character_desc.delete("1.0","end")
        self.character_wardrobe.delete("1.0","end")
        self.character_image_label.config(text="Referans fotoğrafı seçilmedi")
        self.refresh_character_references_label()
        self.refresh_character_preview()
        self.refresh_characters()
        self.set_status("Karakter silindi; sahne bağlantıları yeniden düzenlendi.")

    def assign_character(self):
        cs=list(self.character_list.curselection()); ss=self.character_scene_combo.current()
        if not cs or ss<0 or ss>=len(self.project.get("scenes",[])):
            messagebox.showinfo("Atama","Bir veya daha fazla karakteri ve sahneyi seç."); return
        scene=self.project["scenes"][ss]
        scene["character_ids"]=cs
        scene["character_id"]=cs[0]
        names=", ".join(self.project["characters"][i]["name"] for i in cs)
        self.set_status(f"{names} karakterleri {ss+1}. sahneye bağlandı.")

    def youtube_package(self):
        scenes=self.project.get("scenes",[])
        if not scenes:
            messagebox.showinfo("Yayın paketi","Önce bir proje oluştur ve sahneleri hazırla."); return
        win=tk.Toplevel(self.root); win.title("YouTube yayın paketi"); win.geometry("620x540"); win.transient(self.root); win.grab_set()
        box=ttk.Frame(win,padding=14); box.pack(fill="both",expand=True)
        ttk.Label(box,text="Video başlığı").pack(anchor="w")
        title=tk.StringVar(value=self.name_var.get().strip() or "Yeni Video")
        ttk.Entry(box,textvariable=title).pack(fill="x",pady=(2,8))
        ttk.Label(box,text="Açıklama").pack(anchor="w")
        desc=tk.Text(box,height=10,wrap="word"); desc.pack(fill="both",expand=True,pady=(2,8))
        desc.insert("1.0", "\n\nBu videoda: "+" ".join(x.get("text","") for x in scenes)[:1800])
        ttk.Label(box,text="Etiketler (virgülle ayır)").pack(anchor="w")
        tags=tk.StringVar(value="hikaye, kısa film, video, anlatı")
        ttk.Entry(box,textvariable=tags).pack(fill="x",pady=(2,8))
        def export():
            folder=PROJECT_ROOT/safe_name(self.name_var.get())/"youtube_yayin"; folder.mkdir(parents=True,exist_ok=True)
            (folder/"YouTube_Aciklama_ve_Etiketler.txt").write_text(f"BAŞLIK\n{title.get()}\n\nAÇIKLAMA\n{desc.get('1.0','end').strip()}\n\nETİKETLER\n{tags.get()}",encoding="utf-8")
            first=scenes[0].get("image","")
            thumb=folder/"YouTube_Kapak.jpg"
            if first and Path(first).exists():
                im=fit_image(first,(1280,720)); d=ImageDraw.Draw(im,"RGBA"); d.rectangle((0,500,1280,720),fill=(0,0,0,165))
                f=font(54,True); label=title.get()[:55]; d.text((55,555),label,font=f,fill=(255,255,255,255),stroke_width=2,stroke_fill=(0,0,0,255)); im.save(thumb,quality=94)
            else:
                make_original_visual(title.get(),thumb,size=(1280,720),draw_text=True)
            messagebox.showinfo("Hazır",f"YouTube yayın dosyaları hazır:\n{folder}"); win.destroy()
        ttk.Button(box,text="Yayın dosyalarını oluştur",command=export).pack(anchor="e",pady=6)

    def set_status(self,s): self.status.config(text=s)

    def parse_script(self):
        self.project["script"]=self.script.get("1.0","end").strip()
        self.project["scenes"]=split_scenes(self.project["script"])
        self.refresh_scenes()
        self.refresh_characters()
        self.set_status(f'{len(self.project["scenes"])} sahne oluşturuldu.')

    def refresh_scenes(self,select=0):
        self.scene_list.delete(0,"end")
        for i,s in enumerate(self.project["scenes"]):
            label=s["text"].replace("\n"," ")
            self.scene_list.insert("end",f"{i+1}. {label[:75]}")
        if self.project["scenes"]:
            select=max(0,min(select,len(self.project["scenes"])-1))
            self.scene_list.selection_set(select); self.scene_list.activate(select)
            self.select_scene()

    def selected_index(self):
        a=self.scene_list.curselection()
        return a[0] if a else None

    def select_scene(self,event=None):
        i=self.selected_index()
        if i is None or i>=len(self.project["scenes"]): return
        self.current=i
        self.project["scenes"][i].setdefault("character_id",None)
        self.scene_text.delete("1.0","end")
        self.scene_text.insert("1.0",self.project["scenes"][i]["text"])
        s=self.project["scenes"][i]
        self.set_status(("Görsel: "+Path(s["image"]).name if s.get("image") else "Otomatik görsel")+
                        (" | Kendi ses kaydı var" if s.get("audio") else " | Türkçe yapay ses kullanılacak"))
        if hasattr(self,"preview_label") and s.get("image") and Path(s["image"]).exists():
            self.show_preview(i)

    def apply_scene_text(self):
        i=self.selected_index()
        if i is None: return
        self.project["scenes"][i]["text"]=self.scene_text.get("1.0","end").strip()
        self.refresh_scenes(i)

    def add_scene(self):
        self.project["scenes"].append({"text":"Yeni sahne metni","image":"","audio":"","visual_request":"","character_id":None})
        self.refresh_scenes(len(self.project["scenes"])-1)

    def delete_scene(self):
        i=self.selected_index()
        if i is None:return
        del self.project["scenes"][i]
        self.refresh_scenes(max(0,i-1))

    def move_scene(self,step):
        i=self.selected_index()
        if i is None:return
        j=i+step
        if not 0<=j<len(self.project["scenes"]):return
        self.project["scenes"][i],self.project["scenes"][j]=self.project["scenes"][j],self.project["scenes"][i]
        self.refresh_scenes(j)

    def preview_canvas_size(self):
        # Keep generated stills in the same aspect ratio as the selected export.
        return (540,960) if getattr(self,"ratio",None) and self.ratio.get()=="9:16" else (960,540)

    def preview_path(self, i):
        folder=PROJECT_ROOT/safe_name(self.name_var.get())/"on_izleme"
        folder.mkdir(parents=True,exist_ok=True)
        return folder/f"sahne_{i+1:03d}_onizleme.jpg"

    def show_preview(self, i):
        if i is None or i>=len(self.project["scenes"]): return
        scene=self.project["scenes"][i]
        p=scene.get("image","")
        if not p or not Path(p).exists():
            p=str(self.preview_path(i))
            make_original_visual(scene["text"],p,size=self.preview_canvas_size(),seed=i,
                                 request=scene.get("visual_request",""))
            scene["image"]=p
        try:
            camera_request=scene.get("visual_request","")
            camera_path=str(self.preview_path(i)).replace("_onizleme.jpg","_kamera_onizleme.jpg")
            apply_camera_framing(p,camera_path,camera_request,self.preview_canvas_size())
            im=Image.open(camera_path).convert("RGB")
            im.thumbnail((900,560),Image.Resampling.LANCZOS)
            # Show the still inside the editor as well as the optional large preview window.
            self.preview_inline_photo=ImageTk.PhotoImage(im.copy())
            if hasattr(self,"preview_label") and self.preview_label.winfo_exists():
                self.preview_label.configure(image=self.preview_inline_photo,text="")
            self.preview_photo=ImageTk.PhotoImage(im.copy())
            # Keep the preview in a separate window for reliable visibility.
            if not hasattr(self,"preview_window") or not self.preview_window.winfo_exists():
                self.preview_window=tk.Toplevel(self.root)
                self.preview_window.title("Sahne görsel ön izlemesi")
                self.preview_window.geometry("940x650")
                self.preview_window.configure(padx=12,pady=12)
                self.preview_window.protocol("WM_DELETE_WINDOW",self.preview_window.withdraw)
                self.preview_title=ttk.Label(self.preview_window,text="",font=("Segoe UI",11,"bold"))
                self.preview_title.pack(anchor="w",pady=(0,8))
                self.preview_image_label=ttk.Label(self.preview_window,anchor="center")
                self.preview_image_label.pack(fill="both",expand=True)
            self.preview_window.deiconify()
            self.preview_window.lift()
            self.preview_title.config(text=f"Sahne {i+1} / {len(self.project['scenes'])}")
            self.preview_image_label.configure(image=self.preview_photo,text="")
            self._start_preview_animation(p)
            self.set_status(f"Sahne {i+1} hareketli ön izlemede.")
        except Exception as e:
            messagebox.showerror("Ön izleme açılamadı",str(e))

    def _start_preview_animation(self, image_path):
        if hasattr(self,"preview_animation_after"):
            try: self.root.after_cancel(self.preview_animation_after)
            except Exception: pass
        self.preview_animation_source=Image.open(image_path).convert("RGB")
        self.preview_animation_frame=0
        self._animate_preview_frame()

    def _animate_preview_frame(self):
        if not hasattr(self,"preview_window") or not self.preview_window.winfo_exists():
            return
        frame=make_motion_preview_frame(self.preview_animation_source,self.preview_animation_frame)
        frame.thumbnail((900,560),Image.Resampling.LANCZOS)
        self.preview_photo=ImageTk.PhotoImage(frame)
        self.preview_image_label.configure(image=self.preview_photo,text="")
        self.preview_animation_frame+=1
        self.preview_animation_after=self.root.after(90,self._animate_preview_frame)

    def prepare_all_previews(self):
        self.apply_scene_text_if_needed()
        if not self.project["scenes"]:
            self.parse_script()
        for i,s in enumerate(self.project["scenes"]):
            p=s.get("image","")
            if not p or not Path(p).exists():
                p=self.preview_path(i)
                make_original_visual(s["text"],p,size=self.preview_canvas_size(),seed=i,request=s.get("visual_request",""))
                s["image"]=str(p)
        self.refresh_scenes(0)
        self.show_preview(0)
        messagebox.showinfo("Ön izlemeler hazır",f"{len(self.project['scenes'])} sahnenin görseli hazır. Sahne listesinden seçerek tek tek inceleyebilir ve değiştirebilirsin.")

    def apply_visual_request(self):
        i=self.selected_index()
        if i is None:return
        self.apply_scene_text()
        request=self.visual_request_var.get().strip()
        if not request:
            messagebox.showinfo("Değişiklik isteği","Örneğin: Daha karanlık yap, sis ekle ve uzakta bir insan silueti olsun.")
            return
        s=self.project["scenes"][i]
        s["visual_request"]=request
        p=self.preview_path(i)
        try:
            make_original_visual(s["text"],p,size=self.preview_canvas_size(),seed=i+int(time.time())%10000,request=request)
            s["image"]=str(p)
            self.show_preview(i)
            self.set_status("Yerel sahne asistanı isteğini görsel kurallara uyguladı.")
        except Exception as e:
            messagebox.showerror("Sahne değiştirilemedi",str(e))

    def choose_image(self):
        i=self.selected_index()
        if i is None:
            messagebox.showinfo("Görsel seçimi","Önce görsel eklemek istediğin sahneyi seç.")
            return
        p=filedialog.askopenfilename(filetypes=[("Görsel","*.png *.jpg *.jpeg *.webp *.bmp")])
        if not p:
            return
        try:
            with Image.open(p) as candidate:
                candidate.verify()
            with Image.open(p) as candidate:
                candidate.load()
        except Exception as e:
            messagebox.showerror("Geçersiz görsel",f"Bu dosya okunabilir bir görsel değil.\n\n{e}")
            return
        self.project["scenes"][i]["image"]=p
        self.show_preview(i)
        self.set_status("Sahne görseli eklendi ve ön izleme yenilendi.")

    def reset_scene_image(self):
        i=self.selected_index()
        if i is None:
            messagebox.showinfo("Görsel","Önce sıfırlamak istediğin sahneyi seç.")
            return
        scene=self.project["scenes"][i]
        scene["image"]=""
        try:
            p=self.preview_path(i)
            make_original_visual(scene["text"],p,size=self.preview_canvas_size(),seed=i,
                                 request=scene.get("visual_request",""))
            scene["image"]=str(p)
            self.show_preview(i)
            self.set_status("Sahne görseli varsayılan yerel kompozisyona döndürüldü.")
        except Exception as e:
            messagebox.showerror("Görsel sıfırlanamadı",str(e))

    def choose_audio(self):
        i=self.selected_index()
        if i is None:return
        p=filedialog.askopenfilename(filetypes=[("Ses dosyası","*.wav *.mp3 *.m4a *.aac *.ogg")])
        if p:
            self.project["scenes"][i]["audio"]=p
            self.set_status("Kendi ses kaydın bu sahneye bağlandı.")

    def choose_music(self):
        p=filedialog.askopenfilename(filetypes=[("Ses dosyası","*.wav *.mp3 *.m4a *.aac *.ogg")])
        if p:
            self.project["music"]=p; self.music_label.config(text=Path(p).name)

    def check_comfyui_connection(self):
        base_url="http://127.0.0.1:8188"
        self.comfy_status.config(text="ComfyUI bağlantısı ve model kontrol ediliyor...")
        def worker():
            try:
                request=urllib.request.Request(base_url.rstrip("/")+"/models/checkpoints",headers={"User-Agent":"VideoStudyosu"})
                with urllib.request.urlopen(request,timeout=10) as response:
                    models=json.loads(response.read().decode("utf-8"))
                if not models:
                    raise RuntimeError("ComfyUI açık ancak checkpoint modeli bulunamadı.")
                message=f"Bağlantı başarılı. {len(models)} model bulundu. İlk model: {models[0]}"
                self.root.after(0,lambda:self.comfy_status.config(text=message))
            except Exception as exc:
                message=str(exc)
                self.root.after(0,lambda:self.comfy_status.config(text="Görsel motoru hazır değil: "+message))
        threading.Thread(target=worker,daemon=True).start()

    def choose_comfy_workflow(self):
        path=filedialog.askopenfilename(title="ComfyUI API iş akışını seç",filetypes=[("JSON iş akışı","*.json")])
        if path:
            self.comfy_workflow_var.set(path)
            self.comfy_status.config(text="API iş akışı: "+Path(path).name)
            self.set_status("ComfyUI iş akışı seçildi.")

    def generate_comfy_visual(self):
        i=self.selected_index()
        if i is None:
            messagebox.showinfo("Sahne seç","Önce görsel üretilecek sahneyi seç.")
            return
        if getattr(self,"comfy_busy",False): return
        self.apply_scene_text()
        scene=dict(self.project["scenes"][i])
        characters=list(self.project.get("characters",[]))
        request=scene.get("visual_request","")
        character_cues=build_character_consistency_prompt(scene,characters)
        continuity_cues=build_scene_continuity_prompt(scene,i,self.project.get("scenes",[]))
        camera_cues=("Camera framing: "+next((label for keys,label in [
            (("yakın plan","yakın çekim","close-up","close up"),"close-up shot"),
            (("geniş açı","genel plan","uzak plan","wide shot"),"wide establishing shot"),
            (("tepeden çekim","üst açı","kuş bakışı","top-down"),"high-angle overhead shot"),
            (("alttan çekim","alt açı","low angle"),"low-angle shot")
        ] if any(k in request.lower() for k in keys)),"cinematic eye-level framing")+". ")
        prompt_text=("Photorealistic live-action cinematic film still, real actors, natural skin texture, "
                     "physically accurate lighting and detailed production design. "+camera_cues+
                     scene.get("text","")+" "+request+" "+character_cues+" "+continuity_cues).strip()
        width,height=(1024,1792) if self.ratio.get()=="9:16" else (1280,720)
        folder=PROJECT_ROOT/safe_name(self.name_var.get())/"gorseller"
        character_images=collect_character_reference_images(scene,characters)
        scene_seed=int(hashlib.sha256((str(i)+"|"+scene.get("text","")+"|"+request).encode("utf-8")).hexdigest()[:8],16)
        self.comfy_busy=True
        self.comfy_status.config(text="Görsel motoru otomatik hazırlanıyor...")
        self.preview_label.configure(image="",text="İlk kurulum veya sahne görseli hazırlanıyor. İşlem bitince ön izleme burada görünecek.")
        self.set_status("Görsel motoru hazırlanıyor; ilk kurulumda büyük dosyalar indirilebilir.")
        def worker():
            try:
                def progress(message):
                    self.root.after(0,lambda m=message:self.comfy_status.config(text=m))
                ensure_comfyui_running("http://127.0.0.1:8188",progress=progress)
                workflow,checkpoint=create_default_comfyui_workflow("http://127.0.0.1:8188",width,height)
                progress("Sahne görseli üretiliyor: "+Path(checkpoint).name)
                result=comfyui_generate_image("http://127.0.0.1:8188",workflow,prompt_text,folder,width,height,reference_images=character_images,seed=scene_seed)
                self.root.after(0,lambda:self._comfy_visual_done(i,result,None))
            except Exception as exc:
                message=str(exc)
                self.root.after(0,lambda:self._comfy_visual_done(i,None,message))
        threading.Thread(target=worker,daemon=True).start()

    def generate_all_comfy_visuals(self):
        """Automatically install, configure and run the local visual engine for every scene."""
        if not self.project.get("scenes"):
            messagebox.showinfo("Sahne yok","Önce metni sahnelere ayır.")
            return
        if getattr(self,"comfy_busy",False): return
        self.apply_scene_text_if_needed()
        scenes=[dict(scene) for scene in self.project["scenes"]]
        characters=list(self.project.get("characters",[]))
        width,height=(1024,1792) if self.ratio.get()=="9:16" else (1280,720)
        folder=PROJECT_ROOT/safe_name(self.name_var.get())/"gorseller"
        self.comfy_busy=True
        self.comfy_status.config(text="Görsel motoru otomatik hazırlanıyor...")
        self.preview_label.configure(image="",text="İlk kurulum veya sahne görselleri hazırlanıyor. İşlem bitince ön izleme burada görünecek.")
        self.set_status("Görsel motoru hazırlanıyor; ilk kurulumda büyük dosyalar indirilebilir.")
        def worker():
            results=[]
            try:
                def progress(message):
                    self.root.after(0,lambda m=message:self.comfy_status.config(text=m))
                ensure_comfyui_running("http://127.0.0.1:8188",progress=progress)
                workflow,checkpoint=create_default_comfyui_workflow("http://127.0.0.1:8188",width,height)
                for index,scene in enumerate(scenes):
                    request=scene.get("visual_request","")
                    character_cues=build_character_consistency_prompt(scene,characters)
                    continuity_cues=build_scene_continuity_prompt(scene,index,scenes)
                    camera_cues=("Cinematic camera framing. "+request+" ") if request else "Cinematic eye-level camera framing. "
                    prompt=("Create a single photorealistic live-action feature-film frame with real actors, "
                            "natural skin texture, physically plausible anatomy, realistic lighting and production design. "
                            "Show the exact action and location described; no illustration, cartoon, graphic placeholder or text. "
                            +camera_cues+scene.get("text","")+" "+character_cues+" "+continuity_cues).strip()
                    seed=int(hashlib.sha256((str(index)+"|"+scene.get("text","")+"|"+request).encode("utf-8")).hexdigest()[:8],16)
                    refs=collect_character_reference_images(scene,characters)
                    self.root.after(0,lambda n=index+1,total=len(scenes):self.comfy_status.config(text=f"AI sahne görseli üretiliyor: {n}/{total}"))
                    result=comfyui_generate_image("http://127.0.0.1:8188",workflow,prompt,folder,width,height,reference_images=refs,seed=seed)
                    results.append((index,result))
                self.root.after(0,lambda r=results:self._comfy_all_done(r,None))
            except Exception as exc:
                message=str(exc)
                self.root.after(0,lambda r=results,e=message:self._comfy_all_done(r,e))
        threading.Thread(target=worker,daemon=True).start()

    def _comfy_all_done(self,results,error):
        for index,image_path in results:
            if index<len(self.project.get("scenes",[])):
                self.project["scenes"][index]["image"]=image_path
        self.comfy_busy=False
        if error:
            self.comfy_status.config(text=f"{len(results)} sahne üretildi; işlem hata nedeniyle durdu.")
            self.set_status("AI üretimi kısmen tamamlandı; üretilen görseller korundu.")
            messagebox.showerror("AI sahne üretimi",f"{len(results)} sahne başarıyla üretildi. Sonraki sahnede hata oluştu:\n\n{error}")
        else:
            self.comfy_status.config(text=f"Tamamlandı: {len(results)} sahnenin AI görseli üretildi.")
            self.set_status(f"{len(results)} sahne için gerçek AI görselleri hazır.")
            messagebox.showinfo("AI sahneleri hazır",f"{len(results)} sahnenin görselleri üretildi ve projeye eklendi.")
        if results:
            self.refresh_scenes(results[-1][0])
            self.show_preview(results[-1][0])

    def _comfy_visual_done(self,index,image_path,error):
        self.comfy_busy=False
        if error:
            self.comfy_status.config(text="ComfyUI hatası: "+error[:220])
            self.set_status("AI görsel üretimi tamamlanamadı.")
            messagebox.showerror("ComfyUI görsel üretimi",error)
            return
        if index>=len(self.project.get("scenes",[])):
            return
        self.project["scenes"][index]["image"]=image_path
        self.show_preview(index)
        self.comfy_status.config(text="AI görseli hazır: "+Path(image_path).name)
        self.set_status("ComfyUI gerçek AI görseli sahneye aktarıldı.")

    def generate_visual(self):
        i=self.selected_index()
        if i is None:return
        s=self.project["scenes"][i]
        folder=PROJECT_ROOT/safe_name(self.name_var.get())/"gorseller"
        folder.mkdir(parents=True,exist_ok=True)
        p=folder/f"sahne_{i+1:03d}.jpg"
        try:
            make_original_visual(s["text"],p,size=self.preview_canvas_size(),seed=i,request=s.get("visual_request",""))
            s["image"]=str(p)
            self.show_preview(i)
            self.set_status("Özgün grafik görseli oluşturuldu.")
        except Exception as e: messagebox.showerror("Görsel hatası",str(e))

    def filter_voice_choices(self):
        gender=self.voice_gender.get()
        choices=[]
        for voice_id,meta in self.voice_catalog.items():
            if not voice_id.startswith("tr-TR-"): continue
            voice_gender=meta.get("gender","Unknown") if isinstance(meta,dict) else "Unknown"
            if (gender=="Erkek" and voice_gender=="Male") or (gender=="Kadın" and voice_gender=="Female"):
                choices.append(voice_id)
        if not choices:
            defaults=["tr-TR-AhmetNeural"] if gender=="Erkek" else ["tr-TR-EmelNeural"]
            choices=[v for v in defaults if v in self.voice_catalog]
        self.voice_combo["values"]=choices
        if self.voice.get() not in choices and choices:
            self.voice.set(choices[0])

    def refresh_voice_catalog(self):
        self.voice_status.config(text="Türkçe Neural sesleri aranıyor...")
        def worker():
            try:
                import asyncio, edge_tts
                voices=asyncio.run(edge_tts.list_voices())
                found={}
                for v in voices:
                    if v.get("Locale")=="tr-TR":
                        short=v.get("ShortName","")
                        gender=v.get("Gender","")
                        display=f"{short} — {'Kadın' if gender=='Female' else 'Erkek'}"
                        found[short]={"label":display,"gender":gender}
                def done():
                    if found:
                        self.voice_catalog.update(found)
                        self.filter_voice_choices()
                        self.voice_status.config(text=f"{len(found)} Türkçe Neural ses bulundu.")
                    else:
                        self.voice_status.config(text="Türkçe ses listesi alınamadı; mevcut sesler kullanılacak.")
                self.root.after(0,done)
            except Exception as exc:
                error_text=str(exc)
                self.root.after(0,lambda e=error_text:self.voice_status.config(text=f"Ses listesi alınamadı: {e}"))
        threading.Thread(target=worker,daemon=True).start()

    def selected_voice_name(self):
        return self.voice.get() or ("tr-TR-EmelNeural" if self.voice_gender.get()=="Kadın" else "tr-TR-AhmetNeural")

    def selected_voice_styles(self):
        return [name for name,var in self.voice_style_vars.items() if var.get()]

    def effective_voice_controls(self):
        # Edge TTS supports rate/pitch/volume controls, not arbitrary acting styles.
        # These presets approximate delivery through pace and pitch.
        styles=self.selected_voice_styles()
        rate=int(self.rate.get())
        pitch=0
        if "Dini / manevi" in styles: rate-=8; pitch-=2
        if "Korkulu / ürpertici" in styles: rate-=10; pitch-=5
        if "Yavaş" in styles: rate-=12
        if "Hızlı" in styles: rate+=15
        if "Davudi" in styles: pitch-=12
        if "Tok ve güçlü" in styles: pitch-=5
        if "Duygusal" in styles: rate-=4; pitch+=2
        if "Sakin" in styles: rate-=6
        if "Otoriter" in styles: rate-=2; pitch-=2
        if "Gizemli" in styles: rate-=7; pitch-=4
        if "Belgesel anlatımı" in styles: rate-=2
        if "Masalsı" in styles: rate-=5; pitch+=3
        rate=max(-50,min(50,rate))
        pitch=max(-30,min(30,pitch))
        return rate,pitch

    def save_project(self):
        self.apply_scene_text_if_needed()
        self.project["name"]=self.name_var.get().strip() or "Yeni Video"
        self.project["script"]=self.script.get("1.0","end").strip()
        self.project["ratio"]=self.ratio.get()
        self.project["captions"]=self.captions.get()
        self.project["voice"]=self.selected_voice_name()
        self.project["voice_gender"]=self.voice_gender.get()
        self.project["voice_styles"]=self.selected_voice_styles()
        self.project["rate"]=int(self.rate.get())
        self.project["voice_volume"]=int(self.voice_vol.get())
        self.project["music_volume"]=int(self.music_vol.get())
        self.project["visual_effect"]=self.visual_effect.get()
        p=filedialog.asksaveasfilename(initialdir=PROJECT_ROOT,initialfile=safe_name(self.project["name"])+".json",
            defaultextension=".json",filetypes=[("Video Studyosu projesi","*.json")])
        if not p:return
        try:
            Path(p).write_text(json.dumps(self.project,ensure_ascii=False,indent=2),encoding="utf-8")
            self.set_status("Proje UTF-8 olarak kaydedildi.")
        except Exception as e: messagebox.showerror("Kayıt hatası",str(e))

    def apply_scene_text_if_needed(self):
        i=self.selected_index()
        if i is not None and i<len(self.project["scenes"]):
            self.project["scenes"][i]["text"]=self.scene_text.get("1.0","end").strip()

    def load_project(self):
        p=filedialog.askopenfilename(initialdir=PROJECT_ROOT,filetypes=[("Video Studyosu projesi","*.json")])
        if not p:return
        try:
            self.project=json.loads(Path(p).read_text(encoding="utf-8"))
            self.project.setdefault("characters",[])
            self.name_var.set(self.project.get("name","Video"))
            self.script.delete("1.0","end"); self.script.insert("1.0",self.project.get("script",""))
            self.ratio.set(self.project.get("ratio","16:9"))
            self.captions.set(self.project.get("captions",True))
            self.voice_gender.set(self.project.get("voice_gender","Kadın" if self.project.get("voice")=="tr-TR-EmelNeural" else "Erkek"))
            saved_voice=self.project.get("voice","tr-TR-AhmetNeural")
            if saved_voice not in self.voice_catalog:
                self.voice_catalog[saved_voice]={"label":saved_voice,"gender":"Female" if self.voice_gender.get()=="Kadın" else "Male"}
            self.voice.set(saved_voice)
            self.filter_voice_choices()
            saved_styles=self.project.get("voice_styles",[])
            for style_name,var in self.voice_style_vars.items():
                var.set(style_name in saved_styles)
            self.rate.set(self.project.get("rate",0))
            self.voice_vol.set(self.project.get("voice_volume",100))
            self.music_vol.set(self.project.get("music_volume",12))
            self.visual_effect.set(self.project.get("visual_effect","Sinematik"))
            self.music_label.config(text=Path(self.project.get("music","")).name if self.project.get("music") else "Seçilmedi")
            self.refresh_scenes()
            self.refresh_characters()
            self.set_status("Proje açıldı; Türkçe karakterler korundu.")
        except Exception as e: messagebox.showerror("Proje açılamadı",str(e))

    def ask_platform_format(self):
        """Choose a social platform and one of its actual export profiles before rendering."""
        profiles={
            "Instagram":{
                "Reels (9:16) — 1080×1920":(1080,1920,30,"instagram_reels"),
                "Hikâye / Story (9:16) — 1080×1920":(1080,1920,30,"instagram_story"),
                "Gönderi dikey (4:5) — 1080×1350":(1080,1350,30,"instagram_portrait"),
                "Gönderi kare (1:1) — 1080×1080":(1080,1080,30,"instagram_square"),
                "Gönderi yatay (1.91:1) — 1080×566":(1080,566,30,"instagram_landscape"),
            },
            "YouTube":{
                "Standart video (16:9) — 1920×1080":(1920,1080,30,"youtube_standard"),
                "Shorts (9:16) — 1080×1920":(1080,1920,30,"youtube_shorts"),
                "Kare video (1:1) — 1080×1080":(1080,1080,30,"youtube_square"),
            },
            "TikTok":{
                "Dikey video (9:16) — 1080×1920":(1080,1920,30,"tiktok_vertical"),
                "Kare video (1:1) — 1080×1080":(1080,1080,30,"tiktok_square"),
                "Yatay video (16:9) — 1920×1080":(1920,1080,30,"tiktok_landscape"),
            },
        }
        win=tk.Toplevel(self.root)
        win.title("Platform ve video formatı")
        win.transient(self.root); win.grab_set(); win.resizable(False,False)
        box=ttk.Frame(win,padding=18); box.pack(fill="both",expand=True)
        ttk.Label(box,text="Videoyu hangi platform için hazırlıyoruz?",font=("Segoe UI",13,"bold")).pack(anchor="w",pady=(0,12))
        platform=tk.StringVar(value="YouTube")
        fmt=tk.StringVar(value="Standart video (16:9) — 1920×1080")
        ttk.Label(box,text="Sosyal medya platformu").pack(anchor="w")
        platform_box=ttk.Combobox(box,textvariable=platform,values=list(profiles),state="readonly",width=42)
        platform_box.pack(fill="x",pady=(4,10))
        ttk.Label(box,text="Platforma uygun video formatı").pack(anchor="w")
        format_box=ttk.Combobox(box,textvariable=fmt,state="readonly",width=42)
        format_box.pack(fill="x",pady=(4,8))
        hint=ttk.Label(box,text="",foreground="#555")
        hint.pack(anchor="w")
        selected={}
        def update_formats(_event=None):
            options=list(profiles[platform.get()])
            format_box.configure(values=options)
            if fmt.get() not in options: fmt.set(options[0])
            w,h,fps,key=profiles[platform.get()][fmt.get()]
            hint.config(text=f"Çıktı: {w} × {h} piksel  •  {fps} FPS  •  MP4 / H.264")
        def confirm():
            w,h,fps,key=profiles[platform.get()][fmt.get()]
            selected.update(platform=platform.get(),format=fmt.get(),width=w,height=h,fps=fps,profile_key=key)
            win.destroy()
        platform_box.bind("<<ComboboxSelected>>",update_formats)
        update_formats()
        row=ttk.Frame(box); row.pack(fill="x",pady=(16,0))
        ttk.Button(row,text="Devam et",command=confirm).pack(side="right")
        ttk.Button(row,text="Vazgeç",command=win.destroy).pack(side="right",padx=6)
        self.root.wait_window(win)
        return selected or None

    def ask_output_mode(self):
        win=tk.Toplevel(self.root)
        win.title("Video ses ve altyazı ayarları")
        win.transient(self.root); win.grab_set()
        win.resizable(False,False)
        box=ttk.Frame(win,padding=18); box.pack(fill="both",expand=True)
        ttk.Label(box,text="Videon nasıl olsun?",font=("Segoe UI",13,"bold")).pack(anchor="w",pady=(0,10))
        mode=tk.StringVar(value="both")
        for val,label in [("voice","Sadece sesli anlatım"),("subtitle","Sadece altyazılı (seslendirme yok)"),("both","Sesli anlatım + altyazı")]:
            ttk.Radiobutton(box,text=label,value=val,variable=mode).pack(anchor="w",pady=3)
        ttk.Separator(box).pack(fill="x",pady=10)
        ttk.Label(box,text="Altyazı dili").pack(anchor="w")
        lang=tk.StringVar(value="İngilizce")
        cb=ttk.Combobox(box,textvariable=lang,values=list(SUBTITLE_LANGUAGES.keys()),state="readonly",width=25)
        cb.pack(fill="x",pady=(4,10))
        hint=ttk.Label(box,text="Türkçe metin seçtiğin dile çevrilir. Çeviri için internet gerekir.",foreground="#555")
        hint.pack(anchor="w")
        result={}
        def confirm():
            result["mode"]=mode.get()
            result["language"]=lang.get() if mode.get() in ("subtitle","both") else None
            win.destroy()
        def cancel():
            win.destroy()
        row=ttk.Frame(box); row.pack(fill="x",pady=(14,0))
        ttk.Button(row,text="Devam et",command=confirm).pack(side="right")
        ttk.Button(row,text="Vazgeç",command=cancel).pack(side="right",padx=6)
        self.root.wait_window(win)
        return result or None

    def create_video(self):
        if self.busy:return
        self.apply_scene_text_if_needed()
        if not self.project["scenes"]:
            self.parse_script()
        if not self.project["scenes"]:
            messagebox.showwarning("Metin gerekli","Önce hikâyeni yazıp sahnelere ayır.")
            return
        export=self.ask_platform_format()
        if not export:
            return
        choices=self.ask_output_mode()
        if not choices:
            return
        self.project["export_platform"]=export["platform"]
        self.project["export_format"]=export["format"]
        self.project["export_profile"]=export["profile_key"]
        self.project["render_width"]=export["width"]
        self.project["render_height"]=export["height"]
        self.project["render_fps"]=export["fps"]
        self.project["name"]=self.name_var.get().strip() or "Video"
        self.project["ratio"]=self.ratio.get()
        self.project["voice"]=self.selected_voice_name()
        self.project["voice_gender"]=self.voice_gender.get()
        self.project["voice_styles"]=self.selected_voice_styles()
        self.project["rate"]=int(self.rate.get())
        self.project["voice_volume"]=int(self.voice_vol.get())
        self.project["music_volume"]=int(self.music_vol.get())
        self.project["visual_effect"]=self.visual_effect.get()
        # Read Tk variables on the UI thread; the render worker uses plain values only.
        voice_rate,voice_pitch=self.effective_voice_controls()
        self.project["render_voice_rate"]=voice_rate
        self.project["render_voice_pitch"]=voice_pitch
        self.project["output_mode"]=choices["mode"]
        self.project["subtitle_language"]=choices.get("language")
        self.busy=True; self.progress.start(10); self.set_status("Video hazırlanıyor...")
        threading.Thread(target=self._build_video,daemon=True).start()

    def _build_video(self):
        try:
            mode=self.project.get("output_mode","both")
            subtitle_name=self.project.get("subtitle_language") or "İngilizce"
            subtitle_code=SUBTITLE_LANGUAGES.get(subtitle_name,"en")
            name=safe_name(self.project["name"])
            platform_key=safe_name(self.project.get("export_platform","Video"))
            format_key=safe_name(self.project.get("export_profile","default"))
            folder=OUT_ROOT/name/platform_key/format_key
            folder.mkdir(parents=True,exist_ok=True)
            assets=folder/"gecici"; assets.mkdir(exist_ok=True)
            ratio=self.project["ratio"]
            size=(int(self.project.get("render_width",1920)),int(self.project.get("render_height",1080)))
            fps=int(self.project.get("render_fps",30))
            clips=[]
            for idx,scene in enumerate(self.project["scenes"]):
                self._ui_status(f"{idx+1}/{len(self.project['scenes'])}: Sahne hazırlanıyor...")
                original=scene.get("image","")
                img=str(assets/f"gorsel_{idx:03d}.jpg")
                if not original or not Path(original).exists():
                    make_original_visual(scene["text"],img,size=size,seed=idx,
                                         request=scene.get("visual_request",""),draw_text=False)
                else:
                    fit_image(original,size).save(img,quality=94)
                camera_img=str(assets/f"kamera_{idx:03d}.jpg")
                apply_camera_framing(img,camera_img,scene.get("visual_request",""),size)
                img=camera_img
                chars=self.project.get("characters",[])
                char_ids=scene.get("character_ids")
                if not isinstance(char_ids,list):
                    old_id=scene.get("character_id")
                    char_ids=[old_id] if isinstance(old_id,int) else []
                valid_ids=[cid for cid in char_ids if isinstance(cid,int) and 0 <= cid < len(chars)]
                for char_no,char_id in enumerate(valid_ids):
                    char_img=str(assets/f"karakter_{idx:03d}_{char_no:02d}.jpg")
                    add_character_reference(img,chars[char_id],char_img,char_no,len(valid_ids))
                    img=char_img

                # Translate the Turkish scene text for subtitle-only or bilingual output.
                if mode in ("subtitle","both"):
                    self._ui_status(f"{idx+1}/{len(self.project['scenes'])}: {subtitle_name} altyazı hazırlanıyor...")
                    caption=translate_caption(scene["text"],subtitle_code)
                    caption_img=str(assets/f"altyazili_{idx:03d}.jpg")
                    add_subtitle_to_image(img,caption,caption_img)
                    img=caption_img

                audio=scene.get("audio","") if mode in ("voice","both") else ""
                if mode in ("voice","both"):
                    if audio and Path(audio).exists():
                        a=str(assets/f"ses_{idx:03d}.wav")
                        run_ffmpeg(["-i",audio,"-vn","-ac","2","-ar","44100",a])
                    else:
                        a=str(assets/f"ses_{idx:03d}.mp3")
                        rate=int(self.project.get("render_voice_rate",self.project.get("rate",0)))
                        pitch=int(self.project.get("render_voice_pitch",0))
                        rate_str=f"{rate:+d}%"
                        pitch_str=f"{pitch:+d}Hz"
                        import edge_tts
                        vol=max(-50,min(50,int(self.project.get("voice_volume",100))-100))
                        communicate=edge_tts.Communicate(scene["text"],self.project.get("voice","tr-TR-AhmetNeural"),rate=rate_str,pitch=pitch_str,volume=f"{vol:+d}%")
                        import asyncio
                        try:
                            asyncio.run(communicate.save(a))
                        except Exception as tts_error:
                            # Ses servisi gecici olarak erisilemezse sessiz ses parcasi uret;
                            # video montaji tamamen durmasin.
                            self._ui_status(f"{idx+1}/{len(self.project['scenes'])}: Ses servisine ulasilamadi; sessiz parca hazirlaniyor...")
                            silence_duration=max(4,len(scene["text"])/13)
                            run_ffmpeg(["-f","lavfi","-i","anullsrc=r=44100:cl=stereo","-t",str(silence_duration),"-q:a","9","-acodec","libmp3lame",a])
                    probe=subprocess.run([ffmpeg(),"-i",a],stdout=subprocess.PIPE,stderr=subprocess.PIPE,text=True)
                    m=re.search(r"Duration: (\d+):(\d+):(\d+(?:\.\d+)?)",probe.stderr)
                    dur=(int(m.group(1))*3600+int(m.group(2))*60+float(m.group(3))) if m else max(4,len(scene["text"])/13)
                    frame=str(assets/f"clip_{idx:03d}.mp4")
                    vf=camera_motion_filter(scene.get("visual_request",""),size,fps)
                    effect_filter=get_video_effect_filter(self.project.get("visual_effect","Sinematik"))
                    if effect_filter: vf += "," + effect_filter
                    run_ffmpeg(["-loop","1","-i",img,"-i",a,"-vf",vf,"-t",str(max(2,dur)),"-r",str(fps),"-c:v","libx264","-preset","medium","-b:v","8M","-pix_fmt","yuv420p","-c:a","aac","-b:a","192k","-shortest",frame])
                else:
                    # Subtitle-only: show each translated scene for a readable fixed duration.
                    dur=max(4,min(12,len(scene["text"])/18))
                    frame=str(assets/f"clip_{idx:03d}.mp4")
                    vf=camera_motion_filter(scene.get("visual_request",""),size,fps)
                    effect_filter=get_video_effect_filter(self.project.get("visual_effect","Sinematik"))
                    if effect_filter: vf += "," + effect_filter
                    run_ffmpeg(["-loop","1","-i",img,"-vf",vf,"-t",str(dur),"-r",str(fps),"-c:v","libx264","-preset","ultrafast","-pix_fmt","yuv420p",frame])
                clips.append(frame)

            concat=assets/"concat.txt"
            concat.write_text("\n".join(f"file '{p.replace(chr(39), chr(39)+chr(92)+chr(39)+chr(39))}'" for p in clips)+"\n",encoding="utf-8")
            silent=folder/(name+"_sessiz.mp4")
            run_ffmpeg(["-f","concat","-safe","0","-i",str(concat),"-c","copy",str(silent)])
            final=folder/(name+"_"+format_key+".mp4")
            music=self.project.get("music","")
            if music and Path(music).exists():
                vol=max(0,min(0.4,int(self.project.get("music_volume",12))/100))
                if mode in ("voice","both"):
                    run_ffmpeg(["-i",str(silent),"-stream_loop","-1","-i",music,"-filter_complex",f"[1:a]volume={vol}[m];[0:a][m]amix=inputs=2:duration=first:dropout_transition=2[a]","-map","0:v","-map","[a]","-c:v","copy","-c:a","aac","-shortest",str(final)])
                else:
                    run_ffmpeg(["-i",str(silent),"-stream_loop","-1","-i",music,"-filter_complex",f"[1:a]volume={vol}[m]","-map","0:v","-map","[m]","-c:v","copy","-c:a","aac","-shortest",str(final)])
                silent.unlink(missing_ok=True)
            elif mode in ("voice","both"):
                shutil.move(str(silent),str(final))
            else:
                shutil.move(str(silent),str(final))
            shutil.rmtree(assets,ignore_errors=True)
            self.root.after(0,lambda:self._done(final))
        except Exception as e:
            self.root.after(0,lambda err=str(e):self._failed(err))

    def _ui_status(self,s): self.root.after(0,lambda:self.set_status(s))
    def _done(self,p):
        self.busy=False; self.progress.stop(); self.set_status("Video hazır: "+str(p))
        self.refresh_library()
        messagebox.showinfo("Tamamlandı",f"Video oluşturuldu:\\n{p}")
    def _failed(self,e):
        self.busy=False; self.progress.stop(); self.set_status("Hata oluştu.")
        messagebox.showerror("Video oluşturulamadı",e)

    def refresh_library(self):
        if not hasattr(self,"lib_list"):return
        self.lib_list.delete(0,"end")
        self.lib_paths=[]
        for p in sorted(OUT_ROOT.rglob("*.mp4"),key=lambda x:x.stat().st_mtime,reverse=True):
            if p.name.endswith("_sessiz.mp4"):continue
            self.lib_paths.append(p); self.lib_list.insert("end",f"{p.parent.name}  —  {p.name}")
    def selected_video(self):
        a=self.lib_list.curselection()
        return self.lib_paths[a[0]] if a and a[0]<len(self.lib_paths) else None
    def play_selected(self):
        p=self.selected_video()
        if p:
            try: os.startfile(str(p))
            except Exception as e: messagebox.showerror("Açılamadı",str(e))
    def open_selected_folder(self):
        p=self.selected_video()
        if p:
            try: os.startfile(str(p.parent))
            except Exception as e: messagebox.showerror("Açılamadı",str(e))
    def delete_video(self):
        p=self.selected_video()
        if p and messagebox.askyesno("Sil",f"{p.name} silinsin mi?"):
            try:p.unlink(); self.refresh_library()
            except Exception as e:messagebox.showerror("Silinemedi",str(e))
    def close(self):
        if self.busy:
            if not messagebox.askyesno("Çıkış","Video hazırlanıyor. Yine de kapatılsın mı?"):return
        self.root.destroy()

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
