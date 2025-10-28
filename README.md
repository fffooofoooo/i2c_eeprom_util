# I2C EEPROM Util

Script serves the purpose of giving an easy way to flash certain EEPROMs from a test file over a FT2232H Mini Module.
```
Supported Devices:
    24LC32 (For testing)
    ZL30267 (Clock chip)
```

---
## Table of Contents

- [Installation](#installation)  
- [Usage](#usage)  
- [Options](#options)  
- [Examples](#examples)  
- [License](#license)

---
## Installation

```bash
# Clone the repo
git clone https://github.com/YourUser/YourRepo.git
cd YourRepo
```

---
## Usage

```bash
python3 i2c_eeprom_util.py --help

usage: I2C EEPROM Util [-h] [--mode {file,manual,f,m}] [--zlimage IMAGE]
                       [--debug]
                       {24LC32,ZL30267} i2c_address

positional arguments:
  {24LC32,ZL30267}      Which i2c device protocol to use
  i2c_address           Address of i2c slave

options:
  -h, --help            show this help message and exit
  --mode, -m {file,manual,f,m}
                        Selection of file or manual mode
  --zlimage, -zi IMAGE  Option to give a ZL30267 .txt image file to write to
                        eeprom
  --debug, -d           Flag to enable debug outputs
```

---
## Examples

```bash
# Run program with 24LC32 eeprom for testing using it's default address of 0x50 (Changes depending on A2, A1, and A0)
python3 i2c_eeprom_util.py 24LC32 0x50

# Run program in file mode with ZL30267 with image.txt input to flash using it's default address of 0x74 (Changes depending on IC0, and IC1)
python3 i2c_eeprom_util.py ZL30267 0x74 -zi image.txt -m f
# or
python3 i2c_eeprom_util.py ZL30267 0x74 --zlimage image.txt --mode file
```

---
## License
This project is licensed under the MIT License – see the LICENSE file for details.
