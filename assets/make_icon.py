"""Draws the LifeOS icon (blue rounded square, white tick) and saves LifeOS.icns.

Run: .venv/bin/python assets/make_icon.py
"""
import subprocess
import tempfile
from pathlib import Path

from AppKit import (
    NSBezierPath, NSBitmapImageRep, NSCalibratedRGBColorSpace, NSColor,
    NSGraphicsContext, NSPNGFileType, NSLineCapStyleRound, NSLineJoinStyleRound,
)

HERE = Path(__file__).parent
SIZE = 1024


def draw_png(path):
    rep = NSBitmapImageRep.alloc().initWithBitmapDataPlanes_pixelsWide_pixelsHigh_bitsPerSample_samplesPerPixel_hasAlpha_isPlanar_colorSpaceName_bytesPerRow_bitsPerPixel_(
        None, SIZE, SIZE, 8, 4, True, False, NSCalibratedRGBColorSpace, 0, 0)
    NSGraphicsContext.saveGraphicsState()
    NSGraphicsContext.setCurrentContext_(NSGraphicsContext.graphicsContextWithBitmapImageRep_(rep))

    # Apple's icon grid: the shape sits inside the canvas with a margin.
    margin, radius = 100, 185
    NSColor.colorWithCalibratedRed_green_blue_alpha_(0x2F / 255, 0x6F / 255, 0xED / 255, 1).setFill()
    NSBezierPath.bezierPathWithRoundedRect_xRadius_yRadius_(
        ((margin, margin), (SIZE - 2 * margin, SIZE - 2 * margin)), radius, radius).fill()

    # The tick (y goes up in AppKit).
    tick = NSBezierPath.bezierPath()
    tick.moveToPoint_((330, 530))
    tick.lineToPoint_((455, 405))
    tick.lineToPoint_((700, 650))
    tick.setLineWidth_(80)
    tick.setLineCapStyle_(NSLineCapStyleRound)
    tick.setLineJoinStyle_(NSLineJoinStyleRound)
    NSColor.whiteColor().setStroke()
    tick.stroke()

    NSGraphicsContext.restoreGraphicsState()
    rep.representationUsingType_properties_(NSPNGFileType, {}).writeToFile_atomically_(str(path), True)


def main():
    png = HERE / "LifeOS.png"
    draw_png(png)
    with tempfile.TemporaryDirectory() as tmp:
        iconset = Path(tmp) / "LifeOS.iconset"
        iconset.mkdir()
        for size in (16, 32, 128, 256, 512):
            for scale in (1, 2):
                name = f"icon_{size}x{size}{'@2x' if scale == 2 else ''}.png"
                px = size * scale
                subprocess.run(["sips", "-z", str(px), str(px), str(png), "--out", str(iconset / name)],
                               check=True, capture_output=True)
        subprocess.run(["iconutil", "-c", "icns", str(iconset), "-o", str(HERE / "LifeOS.icns")], check=True)
    print("wrote", HERE / "LifeOS.icns")


if __name__ == "__main__":
    main()
