# Disable unused modules

# noinspection PyBroadException
try:
    # noinspection PyPackageRequirements
    import usb_midi

    usb_midi.disable()
except Exception:
    pass

# noinspection PyBroadException
try:
    # noinspection PyPackageRequirements
    import usb_hid

    usb_hid.disable()
except Exception:
    pass

# noinspection PyBroadException
try:
    # noinspection PyPackageRequirements
    import wifi

    wifi.radio.enabled = False
except Exception:
    pass

# noinspection PyBroadException
try:
    # noinspection PyPackageRequirements
    import _bleio

    _bleio.adapter.enabled = False
except Exception:
    pass
