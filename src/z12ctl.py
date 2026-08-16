#!/usr/bin/env python3
"""z12ctl — EVGA Z12 keyboard configuration CLI (macOS/Linux).

Reads onboard settings via HID feature reports. All read operations are
safe (GET_FEATURE only). Write operations are gated behind explicit flags.

Usage:
    z12ctl info                          # device info
    z12ctl keymap dump [--layer secondary]  # full 121-key mapping
    z12ctl keymap get <position>          # single key
    z12ctl keymap set <position> <binding> [--save]
    z12ctl macro list                     # macro status + names
    z12ctl macro get <index>              # single macro with decoded actions
    z12ctl profile get                    # current profile number
    z12ctl profile list                   # profiles 1-9
    z12ctl profile save                   # write RAM to flash (profile=0)
    z12ctl led get                        # report 7 LED mode parameters

All protocol constants are verified against on-device captures
(docs/research.md). Only opens interface 1 (vendor collection 0x08/0x4B),
never interface 0 (boot keyboard).
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

# Allow `python src/z12ctl.py ...` without installing the package.
sys.path.insert(0, str(Path(__file__).resolve().parent))

from evga_z12 import protocol
from evga_z12.hid_io import DeviceNotFoundError, HIDError, Z12Device
from evga_z12.keymap import KeyEntry, dump_keymap, parse_binding, read_key, write_key
from evga_z12.led import decode_lighting_effect_mode, read_all_led_modes, read_led_mode
from evga_z12.macro import MacroInfo, read_macro, read_macro_name, read_macro_status
from evga_z12.profile import get_profile_number, save_profile, scan_profiles

# --- Output helpers ---


def _print_device(dev: Z12Device) -> None:
    info = dev.info
    print(f"  VID:PID     {protocol.VENDOR_ID:#06x}:{protocol.PRODUCT_ID:#06x}")
    print(f"  Interface   {info.interface_number}")
    print(f"  Usage       page {info.usage_page:#06x} / usage {info.usage:#06x}")
    print(f"  Product     {dev.product!r}")
    print(f"  Manufacturer {dev.manufacturer!r}")


def _format_key_entry(entry: KeyEntry, show_raw: bool = False) -> str:
    pos_str = f"0x{entry.position:02X}"
    name = entry.position_name
    desc = entry.key_define.describe()
    fn_name = entry.key_define.function_name
    line = f"  {pos_str:>6s}  {name:>16s}  {fn_name:<20s}  {desc}"
    if show_raw:
        raw = entry.raw[7:12].hex(" ")
        line += f"  [{raw}]"
    return line


def _format_macro_action(idx: int, action) -> str:
    return f"    {idx:3d}. [{action.tag}] {action.detail}"


def _format_macro_summary(info: MacroInfo) -> str:
    lines = [
        f"  Macro #{info.index:02d}",
        f"    Name:         {info.name!r}",
        f"    RunMethod:    {info.run_method_name}",
        f"    RepeatTime:   {info.repeat_time}",
        f"    DataLength:   {info.data_length} bytes",
        f"    StatusOfUse:  0x{info.status_of_use:02x} ({'used' if info.is_used else 'unused'})",
        f"    Actions:      {len(info.actions)}",
    ]
    return "\n".join(lines)


# --- Subcommands ---


def cmd_info(args: argparse.Namespace) -> int:
    """Show device info."""
    from evga_z12.hid_io import find_device

    try:
        info = find_device()
    except DeviceNotFoundError:
        print("No EVGA Z12 device found.", file=sys.stderr)
        return 1

    print("=== EVGA Z12 Device ===")
    with Z12Device(info) as dev:
        _print_device(dev)
    return 0


def cmd_keymap_dump(args: argparse.Namespace) -> int:
    """Dump all 121 key mappings."""
    layer = protocol.SUB_SECONDARY_KEY if args.layer == "secondary" else protocol.SUB_PRIMARY_KEY
    layer_name = "Secondary (Shift/FN)" if layer == protocol.SUB_SECONDARY_KEY else "Primary"

    with Z12Device() as dev:
        print(f"=== Keymap Dump ({layer_name} layer) ===")
        _print_device(dev)
        print()
        entries = dump_keymap(dev, layer=layer)

    print(f"  {len(entries)} valid positions")
    print()
    print(f"  {'Pos':>6s}  {'Name':>16s}  {'Function':<20s}  {'Binding'}")
    print(f"  {'---':>6s}  {'----':>16s}  {'--------':<20s}  {'-------'}")
    for entry in entries:
        print(_format_key_entry(entry, show_raw=args.raw))
    return 0


def cmd_keymap_get(args: argparse.Namespace) -> int:
    """Read a single key's mapping."""
    pos = _parse_position(args.position)
    layer = protocol.SUB_SECONDARY_KEY if args.layer == "secondary" else protocol.SUB_PRIMARY_KEY
    with Z12Device() as dev:
        try:
            entry = read_key(dev, pos, layer=layer)
        except HIDError as exc:
            print(f"Error: {exc}", file=sys.stderr)
            return 1
    print(_format_key_entry(entry, show_raw=True))
    return 0


def cmd_keymap_set(args: argparse.Namespace) -> int:
    """Write a single key's mapping. Immediately live in RAM."""
    pos = _parse_position(args.position)
    try:
        binding = parse_binding(args.binding)
    except ValueError as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 2
    layer = protocol.SUB_SECONDARY_KEY if args.layer == "secondary" else protocol.SUB_PRIMARY_KEY

    print("=== Keymap Set ===")
    print(f"  Position:  0x{pos:02X} ({protocol.LED_KEY_POSITIONS.get(pos, '?')})")
    print(f"  Layer:     {args.layer}")
    print(f"  Binding:   {binding.describe()}")
    print(f"  Save:      {'yes (profile=0)' if args.save else 'no (RAM only)'}")
    print("  Please stop typing.")

    with Z12Device() as dev:
        try:
            before = read_key(dev, pos, layer=layer)
        except HIDError as exc:
            print(f"Error reading current value: {exc}", file=sys.stderr)
            return 1
        print(f"  Before:    {before.key_define.describe()}")

        try:
            after = write_key(dev, pos, binding, layer=layer)
        except (HIDError, ValueError) as exc:
            print(f"Error writing: {exc}", file=sys.stderr)
            return 1
        print(f"  After:     {after.key_define.describe()}")

        wrote_ok = after.key_define == binding
        if not wrote_ok:
            print("  Read-back does not match the requested binding.", file=sys.stderr)
            return 1

        if args.save:
            try:
                save_profile(dev)
            except HIDError as exc:
                print(f"Error saving profile: {exc}", file=sys.stderr)
                return 1
            print("  Saved to flash (profile=0).")
    return 0


def cmd_macro_list(args: argparse.Namespace) -> int:
    """List all used macros with names."""
    with Z12Device() as dev:
        print("=== Macro List ===")
        _print_device(dev)
        print()
        used_indices = read_macro_status(dev)

        if not used_indices:
            print("  No macros in use.")
            return 0

        print(f"  {len(used_indices)} macros in use:")
        print()
        print(f"  {'Index':>6s}  {'Name':<30s}")
        print(f"  {'-----':>6s}  {'----':<30s}")

        for idx in used_indices:
            try:
                name = read_macro_name(dev, idx)
            except HIDError:
                name = "(read error)"
            print(f"  #{idx:02d}    {name!r}")
    return 0


def cmd_macro_get(args: argparse.Namespace) -> int:
    """Show a single macro with decoded actions."""
    idx = int(args.index)
    if idx < 1 or idx > protocol.MACRO_TOTAL_COUNT:
        print(f"Error: macro index must be 1-{protocol.MACRO_TOTAL_COUNT}", file=sys.stderr)
        return 1

    with Z12Device() as dev:
        try:
            info = read_macro(dev, idx)
        except HIDError as exc:
            print(f"Error: {exc}", file=sys.stderr)
            return 1

    print("=== Macro Detail ===")
    print(_format_macro_summary(info))
    print()
    if info.actions:
        print("  Decoded actions:")
        for i, action in enumerate(info.actions):
            print(_format_macro_action(i, action))
    else:
        print("  (no actions)")
    return 0


def cmd_profile_get(args: argparse.Namespace) -> int:
    """Show current profile number."""
    with Z12Device() as dev:
        try:
            num = get_profile_number(dev)
        except HIDError as exc:
            print(f"Error: {exc}", file=sys.stderr)
            return 1
    print(f"Current profile: {num}")
    return 0


def cmd_profile_save(args: argparse.Namespace) -> int:
    """Write current RAM profile to onboard flash (profile=0)."""
    print("=== Profile Save ===")
    print("  Command: 04 EA 02 12 00 00 00 00  (current profile)")
    print("  Please stop typing.")
    with Z12Device() as dev:
        try:
            current = get_profile_number(dev)
        except HIDError as exc:
            print(f"Error reading profile: {exc}", file=sys.stderr)
            return 1
        print(f"  Current profile: {current}")
        try:
            resp = save_profile(dev)
        except HIDError as exc:
            print(f"Error: {exc}", file=sys.stderr)
            return 1
        status = resp[6]
        print(f"  Response: {resp.hex(' ')}")
        print(f"  Status:   0x{status:02x} Success — RAM written to flash")
    return 0


def cmd_profile_list(args: argparse.Namespace) -> int:
    """List profiles 1-9."""
    with Z12Device() as dev:
        print("=== Profiles ===")
        _print_device(dev)
        print()
        try:
            current = get_profile_number(dev)
        except HIDError as exc:
            print(f"Error reading current profile: {exc}", file=sys.stderr)
            current = -1
        profiles = scan_profiles(dev)

    print(f"  Current: {current}")
    print()
    print(f"  {'Profile':>8s}  {'Valid':>6s}  {'Current':>8s}")
    print(f"  {'-------':>8s}  {'-----':>6s}  {'-------':>8s}")
    for p in profiles:
        is_current = "✅" if p.number == current else ""
        print(f"  {p.number:>8d}  {'✅' if p.valid else '❌':>6s}  {is_current:>8s}")
    return 0


def cmd_led_get(args: argparse.Namespace) -> int:
    """Read report 7 LED mode parameters."""
    with Z12Device() as dev:
        print("=== LED Mode Parameters (report 7) ===")
        _print_device(dev)
        print()

        if args.mode:
            # Read specific mode
            main_cmd = _parse_ram_cmd(args.mode)
            try:
                result = read_led_mode(dev, main_cmd)
            except HIDError as exc:
                print(f"Error: {exc}", file=sys.stderr)
                return 1
            results = [result]
        else:
            results = read_all_led_modes(dev)

    for result in results:
        status_str = "✅" if result.success else "❌"
        print(
            f"  0x{result.main_command:02x}  {result.command_name:<28s}"
            f"  {status_str}  status=0x{result.status:02x}"
            f"  {result.non_zero_count}B non-zero"
        )
        if result.success and result.non_zero_count > 0:
            print(f"        data[0:32]: {result.data[:32].hex(' ')}")
            if result.main_command == protocol.RAM_CMD_LED_LIGHTING_EFFECT_MODE:
                decoded = decode_lighting_effect_mode(result.data)
                if decoded:
                    main_name = decoded.get("main_mode_name", "?")
                    main_mode = decoded.get("main_mode", 0)
                    sub_mode = decoded.get("sub_mode", 0)
                    print(
                        f"        decoded: main={main_name}"
                        f" (0x{main_mode:02x}) sub=0x{sub_mode:02x}"
                    )
        print()
    return 0


# --- Argument parsing helpers ---


def _parse_position(s: str) -> int:
    """Parse a position argument: hex (0xNN), decimal, or key name."""
    s = s.strip()
    # Try key name first
    if s in protocol.KEY_NAME_TO_POSITION:
        return protocol.KEY_NAME_TO_POSITION[s]
    # Try hex
    if s.lower().startswith("0x"):
        return int(s, 16)
    # Try decimal
    try:
        return int(s)
    except ValueError:
        # Case-insensitive key name lookup
        for name, pos in protocol.KEY_NAME_TO_POSITION.items():
            if name.lower() == s.lower():
                return pos
    raise argparse.ArgumentTypeError(
        f"unknown position: {s!r} (use hex 0xNN, decimal, or key name)"
    )


def _parse_ram_cmd(s: str) -> int:
    """Parse a report 7 MainCommand: hex or name."""
    s = s.strip()
    if s.lower().startswith("0x"):
        return int(s, 16)
    try:
        return int(s)
    except ValueError:
        pass
    # Look up by name in RAM_CMD_NAMES
    for cmd, name in protocol.RAM_CMD_NAMES.items():
        if name.lower() == s.lower():
            return cmd
    raise argparse.ArgumentTypeError(
        f"unknown LED mode: {s!r} (use hex 0x0C or name like LED_StaticOn)"
    )


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="z12ctl",
        description="EVGA Z12 keyboard configuration tool (macOS/Linux).",
        epilog="All read operations are safe. Write operations require explicit flags.",
    )
    sub = parser.add_subparsers(dest="command", required=True)

    # info
    info_parser = sub.add_parser("info", help="show device info")
    info_parser.set_defaults(func=cmd_info)

    # keymap
    keymap_parser = sub.add_parser("keymap", help="keymap read/write operations")
    keymap_sub = keymap_parser.add_subparsers(dest="keymap_command", required=True)

    keymap_dump = keymap_sub.add_parser("dump", help="dump all 121 key mappings")
    keymap_dump.add_argument("--layer", choices=["primary", "secondary"], default="primary",
                             help="keymap layer (default: primary)")
    keymap_dump.add_argument("--raw", action="store_true", help="show raw bytes")
    keymap_dump.set_defaults(func=cmd_keymap_dump)

    keymap_get = keymap_sub.add_parser("get", help="read a single key")
    keymap_get.add_argument("position", help="position: hex (0x15), decimal (21), or key name (E1)")
    keymap_get.add_argument("--layer", choices=["primary", "secondary"], default="primary")
    keymap_get.set_defaults(func=cmd_keymap_get)

    keymap_set = keymap_sub.add_parser(
        "set",
        help="write a single key (RAM; add --save to persist)",
    )
    keymap_set.add_argument("position", help="position: hex, decimal, or key name (E5)")
    keymap_set.add_argument(
        "binding",
        help="F13, LCtrl+C, disable, macro:6, Mute, or HID 0x68",
    )
    keymap_set.add_argument("--layer", choices=["primary", "secondary"], default="primary")
    keymap_set.add_argument(
        "--save",
        action="store_true",
        help="also SaveProfile (profile=0) after a successful write",
    )
    keymap_set.set_defaults(func=cmd_keymap_set)

    # macro
    macro_parser = sub.add_parser("macro", help="macro read operations")
    macro_sub = macro_parser.add_subparsers(dest="macro_command", required=True)

    macro_list = macro_sub.add_parser("list", help="list all used macros")
    macro_list.set_defaults(func=cmd_macro_list)

    macro_get = macro_sub.add_parser("get", help="show a single macro with decoded actions")
    macro_get.add_argument("index", type=int, help="macro index (1-100)")
    macro_get.set_defaults(func=cmd_macro_get)

    # profile
    profile_parser = sub.add_parser("profile", help="profile operations")
    profile_sub = profile_parser.add_subparsers(dest="profile_command", required=True)

    profile_get = profile_sub.add_parser("get", help="show current profile number")
    profile_get.set_defaults(func=cmd_profile_get)

    profile_list = profile_sub.add_parser("list", help="list profiles 1-9")
    profile_list.set_defaults(func=cmd_profile_list)

    profile_save = profile_sub.add_parser(
        "save",
        help="write current RAM profile to flash (profile=0)",
    )
    profile_save.set_defaults(func=cmd_profile_save)

    # led
    led_parser = sub.add_parser("led", help="LED mode operations")
    led_sub = led_parser.add_subparsers(dest="led_command", required=True)

    led_get = led_sub.add_parser("get", help="read LED mode parameters (report 7)")
    led_get.add_argument("--mode", help="specific mode only (hex 0x0C or name LED_StaticOn)")
    led_get.set_defaults(func=cmd_led_get)

    return parser


def main() -> int:
    parser = build_parser()
    args = parser.parse_args()

    try:
        return args.func(args)
    except DeviceNotFoundError:
        print("No EVGA Z12 device found.", file=sys.stderr)
        return 1
    except HIDError as exc:
        print(f"HID error: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
