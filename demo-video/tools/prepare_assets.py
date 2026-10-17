"""Copy existing repository branding for a local Remotion preview. No network calls."""
from pathlib import Path
import shutil

root = Path(__file__).resolve().parents[1]
source = root.parent / "web/dist"
for name in ["mark.svg", "fonts/OFL.txt", *(f"fonts/dm-sans-{w}.ttf" for w in (400, 500, 600, 700))]:
    destination = root / "public" / name
    destination.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(source / name, destination)
print("Copied the existing project logo and licensed fonts. No media uploaded.")
