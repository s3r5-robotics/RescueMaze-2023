import usb_midi
import usb_hid
import wifi

usb_midi.disable()
usb_hid.disable()

wifi.radio.enabled = False
