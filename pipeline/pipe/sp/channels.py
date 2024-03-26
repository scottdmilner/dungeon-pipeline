import substance_painter as sp
from typing import List

from pipe.sp.local import get_main_qt_window
from pipe.glui.dialogs import MessageDialog


class sRGBChecker:
    srgb_channels: List[sp.textureset.Channel]

    def __init__(self) -> None:
        self.srgb_channels = []

    def check(self) -> bool:
        """Return True if sRGB channels are properly configured"""
        for ts in sp.textureset.all_texture_sets():
            try:
                stack = ts.get_stack()
            except ValueError:
                MessageDialog(
                    get_main_qt_window(),
                    "Warning! sRGB Checker could not get stack! You are doing something cool with material layering. Please show this to Scott so he can fix it.",
                ).exec_()
                return False

            for ch in stack.all_channels().values():
                if ch.format() in [
                    sp.textureset.ChannelFormat.sRGB8,
                    sp.textureset.ChannelFormat.RGB8,
                ]:
                    self.srgb_channels.append(ch)

        return not bool(self.srgb_channels)

    def prompt_srgb_fix(self) -> bool:
        """Return True if fix is successful"""
        fix_channels = MessageDialog(
            get_main_qt_window(),
            "Warning! Some of your color channels do not have a high enough bit depth for this color space! (sRGB8, RGB8). Would you like to convert them to RGB16 now?",
            "Color Bit Depth Issue",
            has_cancel_button=True,
        ).exec_()

        if not fix_channels:
            return False

        for ch in self.srgb_channels:
            ch.edit(sp.textureset.ChannelFormat.RGB16)

        MessageDialog(get_main_qt_window(), "Color bit depth has been updated.").exec_()
        return True
