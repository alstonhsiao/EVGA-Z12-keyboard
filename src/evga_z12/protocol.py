"""EVGA Z12 HID feature report protocol constants.

All values verified against docs/research.md (on-device GET_FEATURE capture,
2026-08-16) and docs/unleash-reverse-engineering.md (EDispNetLib.dll IL
analysis). Per AGENTS.md rule 7, no constant enters this file without a
matching on-device capture.
"""

# --- Device identification (docs/research.md:24, unleash-reverse-engineering.md:28) ---
VENDOR_ID = 0x3842
PRODUCT_ID = 0x2612

# --- Interface selection (docs/research.md:58, AGENTS.md rule 3) ---
TARGET_INTERFACE = 1
TARGET_USAGE_PAGE = 0x08
TARGET_USAGE = 0x4B

# --- 0xEA family header (docs/research.md:140, verified on-device) ---
HEADER1 = 0xEA
HEADER2 = 0x02

# --- Feature report IDs and sizes (docs/research.md:65-71, descriptor) ---
REPORT_GENERAL_USB = 0x04
REPORT_GENERAL_USB_SIZE = 17

REPORT_LED_COLOR = 0x06
REPORT_LED_COLOR_SIZE = 32

REPORT_PROFILE_IN_RAM = 0x07
REPORT_PROFILE_IN_RAM_SIZE = 136

REPORT_PROFILE_USB = 0x08
REPORT_PROFILE_USB_SIZE = 265

REPORT_MACRO_USB = 0x09
REPORT_MACRO_USB_SIZE = 265

REPORT_MACRO_NAME_USB = 0x0A
REPORT_MACRO_NAME_USB_SIZE = 59

# --- GeneralUsbMainCommand (report 4 byte[3], unleash-reverse-engineering.md:78) ---
CMD_READ_FIRMWARE_VERSION = 0x01
CMD_PROFILE = 0x06
CMD_KEY_FUNCTION_RAM = 0x07
CMD_RESET_PROFILE = 0x09
CMD_EKEY_MODE = 0x0B
CMD_GAME_MODE_DISABLE_KEYS_RAM = 0x0C
CMD_SAVE_PROFILE = 0x12
CMD_RESET_TO_FACTORY_DEFAULT = 0x31

# --- GeneralUsbSubCommand (report 4 byte[4]/[5], unleash-reverse-engineering.md:111) ---
SUB_WRITE = 0x00
SUB_READ = 0x01
SUB_DEFAULT = 0x02
SUB_PRIMARY_KEY = 0x00
SUB_SECONDARY_KEY = 0x01

# --- ProfileInRAM MainCommand (report 7 byte[3], profile-protocol.md:377) ---
RAM_CMD_KEY_FUNCTION = 0x0B
RAM_CMD_LED_LIGHTING_EFFECT_MODE = 0x0C
RAM_CMD_LED_STATIC_ON = 0x0D
RAM_CMD_LED_BREATHING = 0x0E
RAM_CMD_LED_PULSE = 0x0F
RAM_CMD_LED_SPIRAL_RAINBOW = 0x10
RAM_CMD_LED_RAINBOW_WAVE = 0x11
RAM_CMD_LED_TRIGGER = 0x12
RAM_CMD_LED_STAR_SHINING = 0x13

# --- ResponseCommand (unleash-reverse-engineering.md:189, verified on-device) ---
RESPONSE_SUCCESS = 0xC0
RESPONSE_FAIL = 0xC1
RESPONSE_IN_PROCESS = 0xC2

# --- MacroDirection (unleash-reverse-engineering.md:213) ---
MACRO_DIR_READ = 0x01
MACRO_DIR_WRITE = 0x02

# --- MacroMainCommand (unleash-reverse-engineering.md:286) ---
MACRO_CMD_STATUS = 0x00
MACRO_CMD_DATA = 0x01

# --- KeyFunction enum (function-codes.md:30, key-position-table.md:354) ---
KEY_FUNCTION_NAMES = {
    0x00: "KeyboardEmulation",
    0x02: "Consumer",
    0x03: "Macro",
    0x04: "FnKey",
    0x05: "EKey",
    0x06: "MouseWheelScroll",
    0x07: "MouseLeftClick",
    0x08: "MouseRightClick",
    0x09: "MouseWheelClick",
    0x0B: "InformationReportKeyPosition",
    0x0C: "SystemControl",
    0x11: "Profile1",
    0x12: "Profile2",
    0x13: "Profile3",
    0x14: "Profile4",
    0x15: "Profile5",
    0x16: "Profile6",
    0x17: "Profile7",
    0x18: "Profile8",
    0x19: "Profile9",
    0x1E: "ProfileCyclePlus",
    0x1F: "ProfileCycleMinus",
    0x20: "IncreaseBrightness",
    0x21: "DecreaseBrightness",
    0x22: "IncreaseLightEffect",
    0x23: "DecreaseLightEffect",
    0xFF: "Disable",
}

# --- Modifier bitmask (key-position-table.md:418, HID standard) ---
MODIFIER_BITS = {
    0x01: "LCtrl",
    0x02: "LShift",
    0x04: "LAlt",
    0x08: "LGUI",
    0x10: "RCtrl",
    0x20: "RShift",
    0x40: "RAlt",
    0x80: "RGUI",
}

# --- HID usage code -> key name (key-position-table.md:430, Pasquotcho keys.yaml) ---
HID_USAGE_NAMES = {
    0x04: "A", 0x05: "B", 0x06: "C", 0x07: "D", 0x08: "E", 0x09: "F",
    0x0A: "G", 0x0B: "H", 0x0C: "I", 0x0D: "J", 0x0E: "K", 0x0F: "L",
    0x10: "M", 0x11: "N", 0x12: "O", 0x13: "P", 0x14: "Q", 0x15: "R",
    0x16: "S", 0x17: "T", 0x18: "U", 0x19: "V", 0x1A: "W", 0x1B: "X",
    0x1C: "Y", 0x1D: "Z",
    0x1E: "1", 0x1F: "2", 0x20: "3", 0x21: "4", 0x22: "5",
    0x23: "6", 0x24: "7", 0x25: "8", 0x26: "9", 0x27: "0",
    0x28: "Enter", 0x29: "Esc", 0x2A: "Backspace", 0x2B: "Tab",
    0x2C: "Space", 0x2D: "-", 0x2E: "=", 0x2F: "[", 0x30: "]",
    0x31: "\\", 0x32: "NonUS#", 0x33: ";", 0x34: "'", 0x35: "`",
    0x36: ",", 0x37: ".", 0x38: "/", 0x39: "CapsLock",
    0x3A: "F1", 0x3B: "F2", 0x3C: "F3", 0x3D: "F4", 0x3E: "F5",
    0x3F: "F6", 0x40: "F7", 0x41: "F8", 0x42: "F9", 0x43: "F10",
    0x44: "F11", 0x45: "F12",
    0x46: "PrintScreen", 0x47: "ScrollLock", 0x48: "Pause",
    0x49: "Insert", 0x4A: "Home", 0x4B: "PageUp",
    0x4C: "Delete", 0x4D: "End", 0x4E: "PageDown",
    0x4F: "Right", 0x50: "Left", 0x51: "Down", 0x52: "Up",
    0x53: "NumLock", 0x54: "Num/", 0x55: "Num*", 0x56: "Num-",
    0x57: "Num+", 0x58: "NumEnter",
    0x59: "Num1", 0x5A: "Num2", 0x5B: "Num3", 0x5C: "Num4",
    0x5D: "Num5", 0x5E: "Num6", 0x5F: "Num7", 0x60: "Num8",
    0x61: "Num9", 0x62: "Num0", 0x63: "Num.",
    0x64: "Intl6", 0x65: "Menu",
    0x68: "F13", 0x69: "F14", 0x6A: "F15", 0x6B: "F16",
    0x6C: "F17", 0x6D: "F18", 0x6E: "F19", 0x6F: "F20",
    0x70: "F21", 0x71: "F22", 0x72: "F23", 0x73: "F24",
    0xE0: "LCtrl", 0xE1: "LShift", 0xE2: "LAlt", 0xE3: "LGUI",
    0xE4: "RCtrl", 0xE5: "RShift", 0xE6: "RAlt", 0xE7: "RGUI",
}

# --- HID consumer codes (key-position-table.md:449) ---
HID_CONSUMER_NAMES = {
    0x0B5: "Next", 0x0B6: "Previous", 0x0B7: "Stop", 0x0CD: "PlayPause",
    0x0E2: "Mute", 0x0E9: "VolumeUp", 0x0EA: "VolumeDown",
    0x183: "MediaSelect", 0x18A: "Mail", 0x192: "Calculator",
    0x194: "MyComputer",
    0x221: "WWWSearch", 0x223: "WWWHome", 0x224: "WWWBack",
    0x225: "WWWForward", 0x226: "WWWStop", 0x227: "WWWRefresh",
    0x22A: "WWWFavorites",
}

# --- LedKeyPosition: physical key position -> name (key-position-table.md) ---
# 121 on-device valid positions. 118 from the software enum (0x00-0x78
# excluding gaps 0x11/0x5F/0x61) + 3 firmware-valid positions not in the
# enum (0x11=Grave, 0x5F=Num., 0x61=App — see keymap-scan-result.md §2.2).
# LED zones 0xA0-0xC4 excluded from keymap operations (not physical keys).
LED_KEY_POSITIONS = {
    0x00: "GameMode", 0x01: "ESC", 0x02: "F1", 0x03: "F2", 0x04: "F3",
    0x05: "F4", 0x06: "F5", 0x07: "F6", 0x08: "F7", 0x09: "F8",
    0x0A: "F9", 0x0B: "F10", 0x0C: "F11", 0x0D: "F12",
    0x0E: "PrintScreen", 0x0F: "ScrollLock", 0x10: "Pause",
    0x11: "GraveAlt",  # firmware-valid, not in software enum (keymap-scan-result.md:110)
    0x12: "PrevTrack", 0x13: "PlayPause", 0x14: "NextTrack",
    0x15: "E1",
    0x16: "Grave", 0x17: "1", 0x18: "2", 0x19: "3", 0x1A: "4",
    0x1B: "5", 0x1C: "6", 0x1D: "7", 0x1E: "8", 0x1F: "9", 0x20: "0",
    0x21: "Minus", 0x22: "Equals", 0x23: "Backspace",
    0x24: "Insert", 0x25: "Home", 0x26: "PageUp",
    0x27: "NumLock", 0x28: "Num/", 0x29: "Num*", 0x2A: "Num-",
    0x2B: "E2",
    0x2C: "Tab", 0x2D: "Q", 0x2E: "W", 0x2F: "E", 0x30: "R",
    0x31: "T", 0x32: "Y", 0x33: "U", 0x34: "I", 0x35: "O", 0x36: "P",
    0x37: "[", 0x38: "]", 0x39: "\\",
    0x3A: "Delete", 0x3B: "End", 0x3C: "PageDown",
    0x3D: "Num7", 0x3E: "Num8", 0x3F: "Num9", 0x40: "Num+",
    0x41: "E3",
    0x42: "CapsLock", 0x43: "A", 0x44: "S", 0x45: "D", 0x46: "F",
    0x47: "G", 0x48: "H", 0x49: "J", 0x4A: "K", 0x4B: "L",
    0x4C: ";", 0x4D: "'", 0x4E: "Enter",
    0x4F: "Num4", 0x50: "Num5", 0x51: "Num6",
    0x52: "E4",
    0x53: "LShift", 0x54: "Z", 0x55: "X", 0x56: "C", 0x57: "V",
    0x58: "B", 0x59: "N", 0x5A: "M",
    0x5B: ",", 0x5C: ".", 0x5D: "/", 0x5E: "RShift",
    0x5F: "NumPeriod2",  # firmware-valid, not in software enum (keymap-scan-result.md:244)
    0x60: "Up",
    0x61: "App",  # firmware-valid, not in software enum (keymap-scan-result.md:251)
    0x62: "Num1", 0x63: "Num2", 0x64: "Num3", 0x65: "NumEnter",
    0x66: "E5",
    0x67: "LCtrl", 0x68: "Win", 0x69: "LAlt", 0x6A: "Space",
    0x6B: "RAlt", 0x6C: "FN", 0x6D: "Menu", 0x6E: "RCtrl",
    0x6F: "Left", 0x70: "Down", 0x71: "Right",
    0x72: "Num0", 0x73: "Num.",
    0x74: "WheelUp", 0x75: "WheelDown", 0x76: "Mute",
    0x77: "NonUSHash", 0x78: "UKBackSlash",
}

# Reverse lookup: key name -> position
KEY_NAME_TO_POSITION = {v: k for k, v in LED_KEY_POSITIONS.items()}

# --- Profile constants (profile-protocol.md:411) ---
PROFILE_MIN = 1
PROFILE_MAX = 9
PROFILE_CURRENT = 0x00
PROFILE_DEFAULT = 0xFE
PROFILE_ALL = 0xFF

# --- RunMethodOfMacro (unleash-reverse-engineering.md:247) ---
RUN_METHOD_NAMES = {
    0x00: "Looping_KeyRelease",
    0x01: "OneShot_KeyRelease",
    0x02: "MultiStage_KeyRelease",
    0x03: "Repeat_KeyRelease",
    0x04: "TwoPhase",
    0x08: "Looping_KeyPress",
    0x09: "OneShot_KeyPress",
    0x0A: "MultiStage_KeyPress",
    0x0B: "Repeat_KeyPress",
    0x0C: "Hold",
}

# --- Macro limits (unleash-reverse-engineering.md:258) ---
MACRO_TOTAL_COUNT = 100
MACRO_PACK_COUNT = 4
MACRO_DATA_PAYLOAD = 256

# --- Report 7 LED mode names (profile-protocol.md:498) ---
LED_MAIN_MODE_NAMES = {
    0x00: "Off",
    0x01: "StaticOn",
    0x02: "Breathing",
    0x03: "Pulse",
    0x05: "RainbowWave",
    0x06: "StarShining",
    0x07: "Trigger",
}

# Report 7 MainCommand -> display name
RAM_CMD_NAMES = {
    RAM_CMD_KEY_FUNCTION: "KeyFunction",
    RAM_CMD_LED_LIGHTING_EFFECT_MODE: "LED_LightingEffectMode",
    RAM_CMD_LED_STATIC_ON: "LED_StaticOn",
    RAM_CMD_LED_BREATHING: "LED_Breathing",
    RAM_CMD_LED_PULSE: "LED_Pulse",
    RAM_CMD_LED_SPIRAL_RAINBOW: "LED_SpiralRainbow",
    RAM_CMD_LED_RAINBOW_WAVE: "LED_RainbowWave",
    RAM_CMD_LED_TRIGGER: "LED_Trigger",
    RAM_CMD_LED_STAR_SHINING: "LED_StarShining",
}
