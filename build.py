import PyInstaller.__main__
import platform
import os

def build():
    # Determine the separator for --add-data based on the OS
    if platform.system() == "Windows":
        separator = ";"
    else:
        separator = ":"

    print(f"Building for {platform.system()}...")

    print(f"Building for {platform.system()}...")
    print(f"Resource separator: '{separator}'")

    PyInstaller.__main__.run([
        'main.py',
        '--name=PUBG_Map_Overlay',
        '--onefile',
        '--noconsole',
        f'--add-data={os.path.join("assets", "overlay_circle.png")}{separator}assets',
        f'--add-data={os.path.join("assets", "icon.ico")}{separator}assets',
        '--clean',
        '--icon=' + os.path.join('assets', 'icon.ico'),
        # '--windowed' is implied by --noconsole but good to be explicit for Mac
        '--windowed', 
    ])

    print("\nBuild complete!")
    print(f"Check the 'dist' folder for the executable.")

if __name__ == "__main__":
    build()
