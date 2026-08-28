import math
from PIL import Image

def process():
    img_path = r"C:\Users\Leonardo Russo\.gemini\antigravity\brain\ac6049b3-14a2-4bdb-a017-3c6bd61e5c0b\.user_uploaded\media_1787903938352.jpg"
    out_path = r"C:\Users\Leonardo Russo\Desktop\RUSSO STOCK\app_icon.ico"
    
    img = Image.open(img_path).convert("RGBA")
    
    # Get image data
    data = img.getdata()
    
    # The background is the color at the top-left corner
    bg_color = data[0]
    
    # Create new data replacing bg with transparent
    new_data = []
    threshold = 30  # Threshold for color distance
    
    for item in data:
        # Calculate color distance
        dist = math.sqrt((item[0] - bg_color[0])**2 + (item[1] - bg_color[1])**2 + (item[2] - bg_color[2])**2)
        if dist < threshold:
            new_data.append((0, 0, 0, 0)) # Transparent
        else:
            # We can also clean up the edges slightly
            new_data.append(item)
            
    img.putdata(new_data)
    
    # Crop to bounding box of non-transparent pixels
    bbox = img.getbbox()
    if bbox:
        img = img.crop(bbox)
        
    # Pad to square
    width, height = img.size
    max_dim = max(width, height)
    padding = int(max_dim * 0.05)
    new_size = max_dim + padding * 2
    
    square_img = Image.new("RGBA", (new_size, new_size), (0, 0, 0, 0))
    x_offset = (new_size - width) // 2
    y_offset = (new_size - height) // 2
    square_img.paste(img, (x_offset, y_offset))
    
    # Save as ICO
    sizes = [(256, 256), (128, 128), (64, 64), (48, 48), (32, 32), (16, 16)]
    square_img.save(out_path, format="ICO", sizes=sizes)
    print("Fatto con Pillow")

if __name__ == "__main__":
    process()
