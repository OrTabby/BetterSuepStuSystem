# BetterStuSystem

A lightweight desktop helper for viewing SUEP academic information such as timetable, grades, exams, training plan progress, and second-credit records.

This project is not an official university system. All academic data should be verified against the official SUEP academic system.

## Notes

- This app is made for personal study and daily convenience.
- It is not affiliated with, endorsed by, or maintained by Shanghai University of Electric Power.
- Timetable, grade, exam, training plan, and credit information may be delayed, incomplete, or parsed incorrectly.
- The official academic system is always the final source of truth.
- Do not use this project for bulk scraping, high-frequency requests, unauthorized access, or any activity that violates university rules.
- Local cache and saved credentials are stored under the local `data/` directory. Do not commit or publish this directory.
- When publishing a build, make sure personal cache files, logs, accounts, and credentials are not included.
- Some HTTPS requests may disable certificate verification because parts of the school system use older certificates. This is only suitable for a trusted personal environment.

Recommended files and folders to exclude from GitHub:

```text
data/
build/
dist/
__pycache__/
*.log
```

## Usage

Install dependencies:

```bash
pip install -r requirements.txt
```

Run the app:

```bash
python main.py
```

On Windows, you can also run:

```powershell
python -u main.py
```

Build with PyInstaller:

```powershell
python -m PyInstaller --clean --noconfirm BetterStuSystem.spec
```

The packaged app will be generated under:

```text
dist/BetterStuSystem/
```

If the app needs to access internal school websites through a browser, configure your browser proxy separately. The VPN started by this app is mainly used by the app itself and does not automatically take over your browser.

For browser access, a SOCKS5 proxy plugin such as SwitchyOmega can be used with:

```text
SOCKS5 127.0.0.1:1080
```

## VPN Acknowledgement

VPN support in this project is based on:

[Yan233th/SHIEP-Pipeline](https://github.com/Yan233th/SHIEP-Pipeline)

SHIEP-Pipeline is a CLI-only EasyConnect implementation for SHIEP. It provides VPN login, tunnel management, local SOCKS5 proxy support, and routing behavior used by this project.

Special thanks to the author of SHIEP-Pipeline for the open-source work and technical foundation.

SHIEP-Pipeline is licensed under AGPL-3.0. If you distribute a build that includes the SHIEP-Pipeline executable, make sure to comply with its upstream license terms and preserve proper attribution, license information, and source availability requirements.

