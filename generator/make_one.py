# generator/make_one.py
# Creates a 1080x1920 Short with background and big on-screen text (no ImageMagick).
import os, textwrap, tempfile
from moviepy.editor import ImageClip, VideoFileClip, ColorClip, CompositeVideoClip, vfx
from PIL import Image, ImageDraw, ImageFont

W, H = 1080, 1920

def _wrap_text(s, width=28):
    s = (s or "").strip()
    if not s: s = "Quick tip: keep going."
    lines = []
    for p in s.split("\n"):
        lines += textwrap.wrap(p, width=width) or [""]
    return lines[:14]  # keep it reasonable

def _render_text_image(title, script, out_png):
    # Try to load a decent font; fall back to default
    try:
        font_title = ImageFont.truetype("DejaVuSans-Bold.ttf", 84)
        font_body  = ImageFont.truetype("DejaVuSans.ttf",       60)
    except:
        font_title = ImageFont.load_default()
        font_body  = ImageFont.load_default()

    img = Image.new("RGBA", (W, H), (10, 10, 10, 255))
    draw = ImageDraw.Draw(img)

    # Title box
    t = title.strip() or "Daily Short"
    tw, th = draw.textbbox((0,0), t, font=font_title)[2:]
    pad = 24
    box_w = min(W-120, tw + 2*pad)
    box_h = th + 2*pad
    tx = (W - box_w)//2
    ty = int(H*0.10)
    draw.rounded_rectangle([tx, ty, tx+box_w, ty+box_h], radius=28, fill=(0,0,0,140))
    draw.text((W//2, ty+pad), t, font=font_title, fill="white", anchor="ma")

    # Body text
    lines = _wrap_text(script, width=28)
    y = int(H*0.55)
    for line in lines:
        lw, lh = draw.textbbox((0,0), line, font=font_body)[2:]
        draw.rounded_rectangle(
            [ (W-lw)//2-20, y-10, (W+lw)//2+20, y+lh+10 ],
            radius=20, fill=(0,0,0,110)
        )
        draw.text((W//2, y), line, font=font_body, fill="white", anchor="ma")
        y += lh + 22

    # CTA
    cta = "Like & Subscribe  •  #Shorts"
    cw, ch = draw.textbbox((0,0), cta, font=font_body)[2:]
    cy = int(H*0.90)
    draw.rounded_rectangle(
        [ (W-cw)//2-20, cy-10, (W+cw)//2+20, cy+ch+10 ],
        radius=20, fill=(0,0,0,120)
    )
    draw.text((W//2, cy), cta, font=font_body, fill="white", anchor="ma")

    img.save(out_png)

def make_video(title, script, out_path, duration=30, assets_dir="assets"):
    D = max(10, min(int(duration or 30), 58))

    # Background: use assets/bg.mp4 or assets/bg.jpg if present; else solid color
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

    # Render text overlay via Pillow, then animate simple fade
    with tempfile.TemporaryDirectory() as tmp:
        overlay_png = os.path.join(tmp, "overlay.png")
        _render_text_image(title or "Daily Short", script or "", overlay_png)
        overlay = ImageClip(overlay_png).set_duration(D).set_position(("center","center"))
        overlay = overlay.fx(vfx.fadein, 0.6).fx(vfx.fadeout, 0.6)

        video = CompositeVideoClip([bg, overlay], size=(W, H))
        os.makedirs(os.path.dirname(out_path), exist_ok=True)
        video.write_videofile(out_path, fps=30, codec="libx264", audio_codec="aac", threads=4, preset="medium")
    return out_path
