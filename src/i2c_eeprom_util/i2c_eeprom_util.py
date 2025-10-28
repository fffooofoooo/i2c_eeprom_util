from pyftdi import i2c, FtdiLogger
from pyftdi.i2c import I2cNackError, I2cPort
from os import environ
from time import sleep
from typing import Union, Callable, Optional, Any
import os
import sys
import argparse
import time
import logging
from importlib.metadata import PackageNotFoundError, version


DIST_NAME = "i2c_eeprom_util"


def get_version() -> str:
    try:
        return version(DIST_NAME)
    except PackageNotFoundError:
        # Fallback for dev runs before install: read pyproject.toml
        import tomllib  # Python 3.11+
        import pathlib

        pyproject = pathlib.Path(__file__).parents[2] / "pyproject.toml"
        data = tomllib.loads(pyproject.read_text(encoding="utf-8"))
        return data["project"]["version"]


def zl_eeprom_image_parse(file_name: str) -> bytearray:
    try:
        if os.path.splitext(file_name)[1] != ".txt":
            raise ValueError("Invalid file extension")
        with open(file_name, "r") as file:
            # File opened successfully, proceed with file operations
            bytes: bytearray = bytearray()
            for line in file:
                if ";" in line:
                    continue
                bytes += int(line, 16).to_bytes(1, byteorder="big")
            return bytes
    except FileNotFoundError:
        raise ValueError(f"Error: The file '{file_name}' was not found.")
    except PermissionError:
        raise ValueError(f"Error: You do not have permission to access '{file_name}'.")
    except IOError as e:
        raise ValueError(
            f"Error: An I/O error occurred while opening '{file_name}': {e}"
        )
    except Exception as e:
        raise TypeError(f"An unexpected error occurred: {e}")


def i2c_protocol_parse(
    device: str,
) -> dict[
    str,
    Union[
        int,
        str,
        tuple[bool, bytes],
        dict[str, tuple[Callable[..., Any], Optional[bytes]]],
    ],
]:
    if device == "24LC32":
        return {
            "device": device,
            "address_size": 12,
            "page_size": 32,
            "write_enable": (False, b""),
            "commands": {
                "Page Write": (
                    lambda eeprom: eeprom_page_write(
                        eeprom,
                        byte_address_parse(
                            input("Input address byte as 0x0000 or 0000: "), 2**12
                        ),
                        bytearray.fromhex(
                            input("Input data bytes as hex with spaces ex:(00 01 02): ")
                        ),
                    ),
                    None,
                ),
                "Single Write": (
                    lambda eeprom: eeprom_write(
                        eeprom,
                        byte_address_parse(
                            input("Input address byte as 0x0000 or 0000: "), 2**12
                        ),
                        byte_address_parse(
                            input("Input data as a single byte 0x00 or 00: ")
                        ),
                    ),
                    None,
                ),
                "Read": (
                    lambda eeprom: eeprom_read(
                        eeprom,
                        byte_address_parse(
                            input("Input address byte as 0x0000 or 0000: "), 2**12
                        ),
                        int(input("Input number of bytes to read (int), ")),
                    ),
                    None,
                ),
            },
        }
    elif device == "ZL30267":
        return {
            "device": device,
            "address_size": 12,
            "page_size": 32,
            "write_enable": (True, b"\x06"),
            "commands": {
                "Page Write": (
                    lambda eeprom: eeprom_page_write(
                        eeprom,
                        byte_address_parse(
                            input("Input address byte as 0x0000 or 0000: "), 2**12
                        ),
                        bytearray.fromhex(
                            input("Input data bytes as hex with spaces ex:(00 01 02): ")
                        ),
                        command=b"\x02",
                        write_enable=(True, b"\x06"),
                    ),
                    b"\x02",
                ),
                # "Single Write": (
                #     lambda eeprom: eeprom_write(
                #         eeprom,
                #         byte_address_parse(
                #             input("Input address byte as 0x0000 or 0000: "), 2**12
                #         ),
                #         byte_address_parse(
                #             input("Input data as a single byte 0x00 or 00: ")
                #         ),
                #         command=b"\x02",
                #     ),
                #     b"\x02",
                # ),
                "Read": (
                    lambda eeprom: eeprom_read(
                        eeprom,
                        byte_address_parse(
                            input("Input address byte as 0x0000 or 0000: "), 2**12
                        ),
                        int(input("Input number of bytes to read (int), ")),
                        command=b"\x03",
                    ),
                    b"\x03",
                ),
            },
        }
    else:
        raise ValueError("Invalid Device")


def eeprom_page_write(
    eeprom: I2cPort,
    address: bytes,
    data: bytearray,
    command: Optional[bytes] = None,
    write_enable: tuple[bool, bytes] = (False, b""),
) -> tuple[bytearray, bytes]:
    if write_enable[0]:
        eeprom.write(write_enable[1])
    eeprom.write((command or b"") + address + data)
    return data, (int.from_bytes(address, "big") + len(data)).to_bytes(
        len(address), "big"
    )


def eeprom_write(
    eeprom: I2cPort, address: bytes, data: bytes, command: Optional[bytes] = None
) -> tuple[bytearray, bytes]:
    eeprom.write((command or b"") + address + data)
    return bytearray(data), (int.from_bytes(address, "big") + 1).to_bytes(
        len(address), "big"
    )


def eeprom_read(
    eeprom: I2cPort, address: bytes, n: int = 1, command: Optional[bytes] = None
) -> tuple[bytearray, bytes]:
    eeprom.write((command or b"") + address)
    return bytearray(eeprom.read(n)), (int.from_bytes(address, "big") + n).to_bytes(
        len(address), "big"
    )


def byte_address_parse(byte_str: str, max_size: Optional[int] = None) -> bytes:
    byte_str = byte_str.strip().lower()
    if byte_str.startswith("0x"):
        byte_str = byte_str[2:]
    byte = bytes.fromhex(byte_str)
    if max_size is not None:
        if int.from_bytes(byte) >= max_size:
            raise ValueError("byte_str larger than max_size")
    return byte


def manual_mode(eeprom: I2cPort, args: argparse.Namespace) -> str:
    eeprom_i2c_config(eeprom, args.device["device"])
    cur_address = b"\x00\x00"
    while True:
        choice = (
            f"Pick a command to run on the eeprom, current address is {cur_address}"
        )
        opt = parse_options(choice, list(args.device["commands"].keys()))  # type: ignore
        if opt == "q":
            return "Program quit"
        out = args.device["commands"][opt][0](eeprom)
        cur_address = out[1]
        print(f"Data in if write, Data out if read: \n{out[0].hex(' ')}")
        print(out)


def file_mode(eeprom: I2cPort, args: argparse.Namespace) -> str:
    eeprom_i2c_config(eeprom, args.device["device"])
    page_size = args.device["page_size"]
    commands = args.device["commands"]
    cur_address = b"\x00\x00"
    if args.image is None:
        while True:
            try:
                image = zl_eeprom_image_parse(input("Input file path to use: "))
                break
            except Exception as e:
                raise e
    else:
        image = args.image

    for i in range(0, len(image), page_size):
        cur_address = eeprom_page_write(
            eeprom,
            cur_address,
            image[i : i + page_size],
            command=commands["Page Write"][1],
            write_enable=args.device["write_enable"],
        )[1]
        sleep(0.01)
    cur_eeprom_data, _ = eeprom_read(
        eeprom, b"\x00\x00", len(image), command=commands["Read"][1]
    )
    print(f"Image file: \n{image.hex(' ')}")
    print(f"Data on eeprom: \n{cur_eeprom_data.hex(' ')}")
    if cur_eeprom_data == image:
        return "Successful eeprom flash"
    return "Unseccessful eeprom flash"


def parse_options(choice: str, opts: list[Any]) -> str:
    while True:
        try:
            print(choice)
            for i in range(len(opts)):
                print(f"\t{i + 1}:  {opts[i]}")
            print("\tq:  Quit Program")
            opt = input("Choose option from list above: ")
            if opt.isnumeric():
                numopt = int(opt) - 1
                if numopt in range(len(opts)):
                    return opts[numopt]
                else:
                    raise ValueError(numopt)
            else:
                return "q"
        except Exception as e:
            print(f"Invalid choice {e}")


def eeprom_i2c_config(eeprom: I2cPort, device: str):
    if device == "ZL30267":
        eeprom_write(eeprom, b"\x00\x00", b"\x80", command=b"\x02")


def main() -> str:
    parser = argparse.ArgumentParser("I2C EEPROM Util")
    parser.add_argument(
        "--version", action="version", version=f"%(prog)s {get_version()}"
    )
    parser.add_argument(
        "device",
        help="Which i2c device protocol to use",
        choices=["24LC32", "ZL30267"],
    )
    parser.add_argument(
        "i2c_address",
        help="Address of i2c slave",
        type=byte_address_parse,
    )
    parser.add_argument(
        "--mode",
        "-m",
        dest="mode",
        help="Selection of file or manual mode",
        choices=["file", "manual", "f", "m"],
        type=str,
    )
    parser.add_argument(
        "--zlimage",
        "-zi",
        dest="image",
        help="Option to give a ZL30267 .txt image file to write to eeprom",
        type=zl_eeprom_image_parse,
    )
    parser.add_argument(
        "--debug",
        "-d",
        dest="debug",
        help="Flag to enable debug outputs",
        action="store_true",
    )

    args = parser.parse_args()
    args.device = i2c_protocol_parse(args.device)
    print(args)

    if args.debug:
        logging.basicConfig(level=logging.INFO)
        logging.getLogger("pyftdi.i2c").setLevel(logging.DEBUG)

    ft2232h = i2c.I2cController()
    url = environ.get("FTDI_DEVICE", "ftdi:///1")
    ft2232h.configure(url, frequency=100000)  # type: ignore

    try:
        eeprom_address = int.from_bytes(args.i2c_address, "big")
        eeprom = ft2232h.get_port(eeprom_address)
        eeprom.poll()
        pass
    except I2cNackError:
        return "Invalid eeprom_address, could not poll slave"
    except Exception as e:
        return f"Invalid eeprom_address, error exit with {e}"
    print("Successful connection to EEPROM slave")

    if args.mode is not None:
        if args.mode in ["file", "f"]:
            return file_mode(eeprom, args)
        elif args.mode in ["manual", "m"]:
            return manual_mode(eeprom, args)
    else:
        choice = "Which mode do you want to use?"
        mode_opts = ["Manual Mode", "File Mode"]
        opt = parse_options(choice, mode_opts)
        if opt == "q":
            return "Program quit early"
        elif opt == "File Mode":
            return file_mode(eeprom, args)
        elif opt == "Manual Mode":
            return manual_mode(eeprom, args)
    return "Program quit early"


if __name__ == "__main__":
    print(main())
