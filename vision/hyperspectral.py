#!/usr/bin/env python3
"""
Hyperspectal camera viewer for Raspiberry pi
"""
__author__ = "Daniel Casner <www.danielcasner.org>"

import picamera
import picamera.array
import infragram
import numpy
import time

WB_GAINS = (1.2, 0.9)


def main():
    with picamera.PiCamera() as camera:
        camera.resolution = (320, 240)
        camera.awb_mode = 'off'
        camera.awb_gains = WB_GAINS
        camera.framerate = 1
        camera.start_preview()
        overlay = None
        with picamera.array.PiRGBArray(camera, size=camera.resolution) as output:
            while True:
                try:
                    camera.capture(output, format='rgb', use_video_port=True)
                    ndvi_arr = infragram.ndvi(output.array)
                    rgb_arr = numpy.stack([ndvi_arr, ndvi_arr, ndvi_arr], axis=2)
                    if overlay is None:
                        overlay = camera.add_overlay(rgb_arr.tobytes(), format='rgb',
                                                     layer=3, size=camera.resolution, alpha=128)
                    else:
                        overlay.update(rgb_arr.tobytes())
                    output.seek(0)
                    output.truncate()
                    time.sleep(0.05)
                except KeyboardInterrupt:
                    if overlay:
                        camera.remove_overlay(overlay)
                    break


if __name__ == '__main__':
    main()
