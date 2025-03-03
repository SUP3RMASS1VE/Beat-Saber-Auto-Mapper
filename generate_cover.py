#!/usr/bin/env python3
import os
import sys
import argparse
from PIL import Image, ImageDraw, ImageFont
import random

def generate_cover_image(output_path, text=None, size=(500, 500)):
    """Generate a simple cover image for Beat Saber maps."""
    # Create a new image with a black background
    img = Image.new('RGB', size, color=(0, 0, 0))
    draw = ImageDraw.Draw(img)
    
    # Draw a grid pattern
    grid_size = 50
    for x in range(0, size[0], grid_size):
        draw.line([(x, 0), (x, size[1])], fill=(30, 30, 30), width=1)
    for y in range(0, size[1], grid_size):
        draw.line([(0, y), (size[0], y)], fill=(30, 30, 30), width=1)
    
    # Draw some random Beat Saber-like blocks
    colors = [(255, 0, 0), (0, 0, 255)]  # Red and blue
    for _ in range(10):
        color = random.choice(colors)
        x = random.randint(50, size[0] - 100)
        y = random.randint(50, size[1] - 100)
        block_size = random.randint(30, 60)
        draw.rectangle([(x, y), (x + block_size, y + block_size)], fill=color)
    
    # Add text if provided
    if text:
        try:
            # Try to use a nice font if available
            font = ImageFont.truetype("arial.ttf", 36)
        except IOError:
            # Fall back to default font
            font = ImageFont.load_default()
        
        # Draw text with a shadow for better visibility
        text_width = draw.textlength(text, font=font)
        text_position = ((size[0] - text_width) // 2, size[1] - 100)
        
        # Draw shadow
        draw.text((text_position[0] + 2, text_position[1] + 2), text, font=font, fill=(0, 0, 0))
        # Draw text
        draw.text(text_position, text, font=font, fill=(255, 255, 255))
    
    # Save the image
    img.save(output_path)
    print(f"Cover image saved to {output_path}")
    return output_path

def main():
    """Parse arguments and generate cover image."""
    parser = argparse.ArgumentParser(description="Generate a cover image for Beat Saber maps")
    parser.add_argument("--output", "-o", default="cover.jpg", help="Output file path")
    parser.add_argument("--text", "-t", help="Text to add to the image")
    parser.add_argument("--size", "-s", type=int, default=500, help="Image size (square)")
    args = parser.parse_args()
    
    generate_cover_image(args.output, args.text, (args.size, args.size))
    
    return 0

if __name__ == "__main__":
    sys.exit(main()) 