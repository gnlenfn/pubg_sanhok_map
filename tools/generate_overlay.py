from PIL import Image, ImageDraw

def create_overlay():
    try:
        img = Image.open('image.png').convert('RGBA')
    except FileNotFoundError:
        print("image.png not found. Creating a placeholder circle.")
        width, height = 2475, 2475
    else:
        width, height = img.size
    
    # Create a new transparent image
    overlay = Image.new('RGBA', (width, height), (0, 0, 0, 0))

    # Center and Radius from previous analysis
    # Center: (1190, 1177), Radius: 765
    cx, cy = 1192, 1175
    r = 773.44
    thickness = 5 # Thickness of the circle line
    color = (255, 50, 80, 255) # Stylish Neon Red

    draw = ImageDraw.Draw(overlay)
    
    # Draw the circle on the transparent layer
    left_up = (cx - r, cy - r)
    right_down = (cx + r, cy + r)
    
    draw.ellipse([left_up, right_down], outline=color, width=thickness)

    overlay.save('assets/overlay_circle.png')
    print("assets/overlay_circle.png created.")

if __name__ == "__main__":
    create_overlay()
