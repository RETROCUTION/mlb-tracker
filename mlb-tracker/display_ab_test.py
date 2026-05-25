from PIL import Image, ImageOps
from waveshare_epd import epd7in5_V2
import time

TEST_IMAGE = "/home/pi/dodgers-tracker/output/standings_test.png"


def show(img, label):
    print("Displaying:", label, "mode=", img.mode, "size=", img.size)

    epd = epd7in5_V2.EPD()
    epd.init()
    epd.Clear()
    time.sleep(1)
    epd.display(epd.getbuffer(img))
    time.sleep(2)
    epd.sleep()

    input("Press ENTER for next test...")


base = Image.open(TEST_IMAGE)

# 1. Original 1-bit image
img1 = base.convert("1")
show(img1, "1-bit normal")

# 2. Original converted through grayscale back to 1-bit
img2 = base.convert("L").point(lambda p: 0 if p < 128 else 255, "1")
show(img2, "L threshold to 1-bit normal")

# 3. Inverted 1-bit
img3 = ImageOps.invert(base.convert("L")).point(lambda p: 0 if p < 128 else 255, "1")
show(img3, "1-bit inverted")

# 4. Old sharp path: inverted grayscale converted to RGB
img4 = ImageOps.invert(base.convert("L")).convert("RGB")
show(img4, "inverted L to RGB")
