from PIL import Image, ImageOps
from waveshare_epd import epd7in5_V2
import time

img = Image.open("/home/pi/dodgers-tracker/output/standings_test.png").convert("1")
inv = ImageOps.invert(img.convert("L")).point(lambda p: 0 if p < 128 else 255, "1")

epd = epd7in5_V2.EPD()
epd.init()

print("Clear")
epd.Clear()
time.sleep(1)

print("Display inverted precharge")
epd.display(epd.getbuffer(inv))
time.sleep(3)

print("Display normal final")
epd.display(epd.getbuffer(img))
time.sleep(3)

epd.sleep()
print("Done")
