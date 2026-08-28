"""
Generates the Murrelektronik Vario-X Application Icon with Murr branding behind the motor.
"""

import os
from PIL import Image, ImageDraw, ImageFilter, ImageFont

SRC_IMG = r"C:\Users\Tuttle\.gemini\antigravity-ide\brain\aeee9484-f7e6-4449-b8f4-b8d51008fd90\.user_uploaded\media_1787945235469.png"
OUT_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "assets"))
os.makedirs(OUT_DIR, exist_ok=True)

SIZE = 512
canvas = Image.new("RGBA", (SIZE, SIZE), (0, 0, 0, 0))
draw = ImageDraw.Draw(canvas)

# 1. Background Murrelektronik Badge / Shield
# Draw rounded rectangle shield
pad = 24
r_corner = 64
shield_rect = [pad, pad, SIZE - pad, SIZE - pad]

# Gradient / layered shield
draw.rounded_rectangle(shield_rect, radius=r_corner, fill=(4, 20, 18, 240), outline=(141, 234, 60, 255), width=6)

# Glowing inner ring
draw.rounded_rectangle([pad + 12, pad + 12, SIZE - pad - 12, SIZE - pad - 12], radius=r_corner - 8, outline=(25, 88, 81, 180), width=3)

# 2. Murrelektronik Stylized "MM" Logo Mark in Background
# Draw bold geometric M logo shape behind motor
logo_layer = Image.new("RGBA", (SIZE, SIZE), (0, 0, 0, 0))
logo_draw = ImageDraw.Draw(logo_layer)

# Draw Murrelektronik Lime green geometric chevron/M blocks
lime = (141, 234, 60, 70) # Subtle glow watermark
cyan = (56, 189, 248, 60)

# Left wing of M
logo_draw.polygon([(80, 180), (140, 120), (200, 180), (150, 180), (140, 170), (130, 180)], fill=lime)
# Right wing of M
logo_draw.polygon([(SIZE - 80, 180), (SIZE - 140, 120), (SIZE - 200, 180), (SIZE - 150, 180), (SIZE - 140, 170), (SIZE - 130, 180)], fill=lime)

# Text "MURRELEKTRONIK" across top inside badge
try:
    font_bold = ImageFont.truetype("arialbd.ttf", 26)
    font_sub = ImageFont.truetype("arialbd.ttf", 16)
except:
    font_bold = ImageFont.load_default()
    font_sub = ImageFont.load_default()

logo_draw.text((SIZE//2, 54), "MURRELEKTRONIK", fill=(141, 234, 60, 220), font=font_bold, anchor="mm")
logo_draw.text((SIZE//2, 84), "VARIO-X MOTOR", fill=(200, 240, 235, 180), font=font_sub, anchor="mm")

# Radial glow behind motor
glow = Image.new("RGBA", (SIZE, SIZE), (0, 0, 0, 0))
glow_draw = ImageDraw.Draw(glow)
glow_draw.ellipse([SIZE//2 - 140, SIZE//2 - 120, SIZE//2 + 140, SIZE//2 + 160], fill=(22, 100, 80, 120))
glow = glow.filter(ImageFilter.GaussianBlur(30))

canvas = Image.alpha_composite(canvas, glow)
canvas = Image.alpha_composite(canvas, logo_layer)

# 3. Paste Motor Image on Top
motor_img = Image.open(SRC_IMG).convert("RGBA")

# Resize motor to fit comfortably in badge
motor_w = int(SIZE * 0.82)
motor_h = int(motor_img.height * (motor_w / motor_img.width))
motor_resized = motor_img.resize((motor_w, motor_h), Image.Resampling.LANCZOS)

# Position motor centered/slightly bottom
offset_x = (SIZE - motor_w) // 2
offset_y = (SIZE - motor_h) // 2 + 35

canvas.paste(motor_resized, (offset_x, offset_y), motor_resized)

# Save Outputs
png_path = os.path.join(OUT_DIR, "app_icon.png")
ico_path = os.path.join(OUT_DIR, "app_icon.ico")
root_ico_path = os.path.join(os.path.dirname(OUT_DIR), "app_icon.ico")
root_png_path = os.path.join(os.path.dirname(OUT_DIR), "app_icon.png")

canvas.save(png_path, "PNG")
canvas.save(root_png_path, "PNG")

# Multi-size ICO (16, 32, 48, 64, 128, 256)
icon_sizes = [(16, 16), (24, 24), (32, 32), (48, 48), (64, 64), (128, 128), (256, 256)]
canvas.save(ico_path, format="ICO", sizes=icon_sizes)
canvas.save(root_ico_path, format="ICO", sizes=icon_sizes)

print(f"Generated Icon successfully at: {png_path} and {ico_path}")
