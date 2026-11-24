from PIL import Image, ImageDraw
from pathlib import Path

static_dir = Path("static")
static_dir.mkdir(exist_ok=True)

def generate_icon(size: int, filename: str):
    img = Image.new("RGBA", (size, size), (9, 10, 15, 255))
    draw = ImageDraw.Draw(img)
    
    # Rounded corners background
    center = size // 2
    
    # Draw radar concentric circles
    r1 = int(size * 0.38)
    r2 = int(size * 0.24)
    r3 = int(size * 0.10)
    
    draw.ellipse([center - r1, center - r1, center + r1, center + r1], outline=(255, 255, 255, 30), width=max(1, size // 100))
    draw.ellipse([center - r2, center - r2, center + r2, center + r2], outline=(255, 255, 255, 45), width=max(1, size // 100))
    draw.ellipse([center - r3, center - r3, center + r3, center + r3], outline=(255, 255, 255, 60), width=max(1, size // 100))
    
    # Crosshair ticks
    tick_len = int(size * 0.06)
    draw.line([center - r1 - tick_len, center, center - r1 + tick_len, center], fill=(255, 255, 255, 70), width=max(1, size // 120))
    draw.line([center + r1 - tick_len, center, center + r1 + tick_len, center], fill=(255, 255, 255, 70), width=max(1, size // 120))
    draw.line([center, center - r1 - tick_len, center, center - r1 + tick_len], fill=(255, 255, 255, 70), width=max(1, size // 120))
    draw.line([center, center + r1 - tick_len, center, center + r1 + tick_len], fill=(255, 255, 255, 70), width=max(1, size // 120))
    
    # Glowing radar sweep blip (Emerald)
    blip_x = center + int(r2 * 0.65)
    blip_y = center - int(r2 * 0.65)
    blip_r = max(3, int(size * 0.035))
    
    # Glow ring
    glow_r = blip_r * 2
    draw.ellipse([blip_x - glow_r, blip_y - glow_r, blip_x + glow_r, blip_y + glow_r], fill=(52, 209, 122, 60))
    # Core dot
    draw.ellipse([blip_x - blip_r, blip_y - blip_r, blip_x + blip_r, blip_y + blip_r], fill=(60, 224, 133, 255))
    
    # Center dot
    center_dot_r = max(2, int(size * 0.018))
    draw.ellipse([center - center_dot_r, center - center_dot_r, center + center_dot_r, center + center_dot_r], fill=(255, 255, 255, 200))
    
    out_path = static_dir / filename
    img.save(out_path, "PNG")
    print(f"Generated {out_path} ({size}x{size})")

generate_icon(192, "icon-192.png")
generate_icon(512, "icon-512.png")
generate_icon(180, "apple-touch-icon.png")
