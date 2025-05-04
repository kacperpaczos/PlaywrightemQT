#!/usr/bin/env python3
# -*- coding: utf-8 -*-

from PIL import Image, ImageDraw, ImageFont
import os

def generate_app_icon():
    """Generuje ikonę aplikacji i zapisuje w folderze app/resources."""
    # Utwórz pusty obraz 256x256 pikseli z przezroczystym tłem
    img = Image.new('RGBA', (256, 256), color=(0, 0, 0, 0))
    draw = ImageDraw.Draw(img)
    
    # Narysuj koło jako tło
    circle_color = (51, 122, 183, 255)  # #337ab7 - niebieski
    draw.ellipse((10, 10, 246, 246), fill=circle_color)
    
    # Narysuj literę "F" (jak Fakturator) w środku
    try:
        # Próbuj załadować czcionkę systemową
        font = ImageFont.truetype("Arial", 150)
    except:
        # Jeśli nie ma czcionki Arial, użyj domyślnej
        font = ImageFont.load_default()
    
    draw.text((90, 40), "F", fill="white", font=font)
    
    # Zapisz jako icon.png w katalogu app/resources
    resources_dir = os.path.join("app", "resources")
    os.makedirs(resources_dir, exist_ok=True)
    
    img.save(os.path.join(resources_dir, "icon.png"))
    
    # Zapisz również jako icon.ico dla Windows
    img.save(os.path.join(resources_dir, "icon.ico"))
    
    print(f"Ikona została wygenerowana i zapisana w {resources_dir}")

if __name__ == "__main__":
    generate_app_icon() 