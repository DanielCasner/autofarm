#!/usr/bin/env python3
"""
Fixed white balance calibration tool for picamera. TSTCPW style.
Original script by Dave Jones https://raspberrypi.stackexchange.com/questions/22975/custom-white-balancing-with-picamera
Rewritten and packaged by Daniel Casner <www.danielcasner.org>
"""
import picamera
import picamera.array
import numpy as np


def calibrate():
    "Return RG and BG values for the camera"
    with picamera.PiCamera() as camera:
        camera.resolution = (1280, 720)
        camera.awb_mode = 'off'
        # Start off with ridiculously low gains
        rg, bg = (1.0, 1.0)
        camera.awb_gains = (rg, bg)
        with picamera.array.PiRGBArray(camera, size=(128, 72)) as output:
            # Allow 30 attempts to fix AWB
            for i in range(30):
                # Capture a tiny resized image in RGB format, and extract the
                # average R, G, and B values
                camera.capture(output, format='rgb', resize=(128, 72), use_video_port=True)
                r, g, b = (np.mean(output.array[..., i]) for i in range(3))
                print('R:%5.2f, B:%5.2f = (%5.2f, %5.2f, %5.2f)' % (
                    rg, bg, r, g, b))
                # Adjust R and B relative to G, but only if they're significantly
                # different (delta +/- 2)
                if abs(r - g) > 2:
                    if r > g:
                        rg -= 0.1
                    else:
                        rg += 0.1
                if abs(b - g) > 1:
                    if b > g:
                        bg -= 0.1
                    else:
                        bg += 0.1
                camera.awb_gains = (rg, bg)
                output.seek(0)
                output.truncate()
        return rg, bg


def main():
    "Entry point when run as a script"
    rg, bg = calibrate()
    print(f"RG = {rg}\tBG = {bg}")


if __name__ == '__main__':
    main()
