# SINGLE-FILE VERSION (no external imports from generator/)
# Generates 1080x1920 Shorts and uploads them to YouTube.

import os, csv, io, requests, pickle, textwrap, tempfile
from datetime import datetime
import pytz

from googleapiclient.discovery import build
from googleapiclient.http import MediaFileUpload

# --- video maker (inline) ---
from moviepy.editor import ImageClip, VideoFileClip, ColorClip, CompositeVideoClip, vfx
from PIL import Image, ImageDraw, ImageFont

W, H = 1080, 1920

def _wrap_text(s, width=28, max_lines=14):
    s = (s or "").strip()
    if not s:
        s = "Quick tip: keep going."
    lines = []
    for p in s.split("\n"):
        lines += textwrap.wrap(p, width=width) or [""]
    return lines[:max_lines]

def _render_text_image(title, script, out_png):
    # Try nice fonts; fall back if unavailable
    try:
        font_title = ImageFont.truetype("DejaVuSans-Bold.ttf", 84)
        font_body  = ImageFont.truetype("DejaVuSans.ttf",       60)
    except Exception:
        font_title = ImageFont.load_default()
        font_body  = ImageFont.load_default()

    img = Image.new("RGBA", (W, H), (12,12,16,255))
    draw = ImageDraw.Draw(img)

    # Title box
    t = (title or "Daily Short").strip()
    pad = 24
    tw, th = draw.textbbox((0,0), t, font=font_title)[2:]
    box_w = min(W-120, tw + 2*pad)
    box_h = th + 2*pad
    tx = (W - box_w)//2
    ty = int(H*0.10)
    draw.rounded_rectangle([tx, ty, tx+box_w, ty+box_h], radius=28, fill=(0,0,0,140))
    draw.text((W//2, ty+pad), t, font=font_title, fill="white", anchor="ma")

    # Body lines
    lines = _wrap_text(script, width=28)
    y = int(H*0.55)
    for line in lines:
        lw, lh = draw.textbbox((0,0), line, font=font_body)[2:]
        draw.rounded_rectangle(
            [(W-lw)//2-20, y-10, (W+lw)//2+20, y+lh+10],
            radius=20, fill=(0,0,0,110)
        )
        draw.text((W//2, y), line, font=font_body, fill="white", anchor="ma")
        y += lh + 22

    # CTA
    cta = "Like & Subscribe • #Shorts"
    cw, ch = draw.textbbox((0,0), cta, font=font_body)[2:]
    cy = int(H*0.90)
    draw.rounded_rectangle(
        [(W-cw)//2-20, cy-10, (W+cw)//2+20, cy+ch+10],
        radius=20, fill=(0,0,0,120)
    )
    draw.text((W//2, cy), cta, font=font_body, fill="white", anchor="ma")

    img.save(out_png)

def make_video(title, script, out_path, duration=30, assets_dir="assets"):
    D = max(10, min(int(duration or 30), 58))
    bg_mp4 = os.path.join(assets_dir, "bg.mp4")
    bg_jpg = os.path.join(assets_dir, "bg.jpg")

    if os.path.exists(bg_mp4):
        base = VideoFileClip(bg_mp4).without_audio().resize((W, H))
        bg = base.loop(duration=D)
        bg = bg.fx(vfx.colorx, 0.85).fx(vfx.lum_contrast, lum=0, contrast=-20, contrast_thr=127)
    elif os.path.exists(bg_jpg):
        bg = ImageClip(bg_jpg).resize((W, H)).set_duration(D)
    else:
        bg = ColorClip(size=(W, H), color=(12,12,16)).set_duration(D)

    with tempfile.TemporaryDirectory() as tmp:
        overlay_png = os.path.join(tmp, "overlay.png")
        _render_text_image(title or "Daily Short", script or "", overlay_png)
        overlay = ImageClip(overlay_png).set_duration(D).set_position(("center","center"))
        overlay = overlay.fx(vfx.fadein, 0.6).fx(vfx.fadeout, 0.6)

        video = CompositeVideoClip([bg, overlay], size=(W, H))
        os.makedirs(os.path.dirname(out_path), exist_ok=True)
        video.write_videofile(out_path, fps=30, codec="libx264", audio_codec="aac", threads=4, preset="medium")
    return out_path
# --- end video maker ---

def _getenv_int(name, default):
    v = os.environ.get(name, '')
    v = (v or '').strip()
    try:
        return int(v) if v != '' else int(default)
    except Exception:
        return int(default)

def _getenv_str(name, default):
    v = os.environ.get(name, '')
    v = (v or '').strip()
    return v if v else default

SHEET_CSV_URL   = _getenv_str('SHEET_CSV_URL', '')
TIMEZONE        = _getenv_str('LOCAL_TZ', 'America/New_York')
MAX_PER_DAY     = _getenv_int('MAX_PER_DAY', 6)
DEFAULT_DURATION= _getenv_int('VIDEO_DURATION', 30)
CATEGORY_ID     = _getenv_str('VIDEO_CATEGORY', '22')
PRIVACY_STATUS  = _getenv_str('VIDEO_PRIVACY', 'public')

with open('token.pickle','rb') as f:
    creds = pickle.load(f)
yt = build('youtube','v3', credentials=creds)

def parse_date(s):
    s=(s or '').strip()
    for fmt in ("%m/%d/%Y","%Y-%m-%d","%m/%d/%y"):
        try: return datetime.strptime(s, fmt).date()
        except Exception:
            pass
    return None

# Read today's rows
resp = requests.get(SHEET_CSV_URL, timeout=30)
resp.raise_for_status()
rows = list(csv.DictReader(io.StringIO(resp.text)))

today = datetime.now(pytz.timezone(TIMEZONE)).date()
today_rows = [r for r in rows if parse_date(r.get('date','')) == today][:MAX_PER_DAY]
if not today_rows:
    print("No rows for today. Add rows with today's date in your Google Form/Sheet.")
    raise SystemExit(0)

os.makedirs('output', exist_ok=True)

for i, r in enumerate(today_rows, 1):
    subject = (r.get('subject') or f'Daily Short {i}').strip()
    script  = (r.get('script')  or f"{subject}: quick tip. Take action today.").strip()
    tags    = [t.strip() for t in (r.get('tags') or 'Shorts').split(',') if t.strip()]

    out = f"output/{i:02d}.mp4"
    print(f"Making: {subject}")
    make_video(subject, script, out, duration=DEFAULT_DURATION)

    body = {
      'snippet': {
        'title': (subject[:95] + ' #Shorts') if len(subject) <= 95 else subject[:92] + '... #Shorts',
        'description': (script + "\n\n#Shorts")[:4900],
        'tags': tags, 'categoryId': CATEGORY_ID
      },
      'status': { 'privacyStatus': PRIVACY_STATUS, 'selfDeclaredMadeForKids': False }
    }
    media = MediaFileUpload(out, chunksize=-1, resumable=True)
    request = yt.videos().insert(part=','.join(body.keys()), body=body, media_body=media)
    response = None
    while response is None:
        status, response = request.next_chunk()
        if status:
            print(f"Uploaded {int(status.progress()*100)}%")
    print("Video id:", response.get('id'))

print("All done.")
