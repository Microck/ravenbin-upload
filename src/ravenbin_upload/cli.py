#!/usr/bin/env python3
"""Upload one file to Raven Bin and print its temporary share URL."""

import argparse
import asyncio
import os
import shutil
import sys
import tempfile
from pathlib import Path

from playwright.async_api import TimeoutError as PlaywrightTimeoutError
from playwright.async_api import async_playwright

URL = "https://ravenbin.com/"
CHROMIUM_CANDIDATES = ("chromium", "chromium-browser", "google-chrome")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        prog="ravenbin-upload",
        description="Encrypt and upload a file to Raven Bin.",
    )
    parser.add_argument("file", type=Path)
    parser.add_argument(
        "--expiry",
        choices=("5m", "15m", "1h", "2h", "4h", "12h"),
        default="15m",
        help="How long Raven Bin keeps the upload (default: 15m).",
    )
    parser.add_argument(
        "--timeout",
        type=float,
        default=300,
        help="Upload timeout in seconds (default: 300).",
    )
    return parser.parse_args()


async def upload(file_path: Path, expiry: str, timeout: float) -> str:
    expiry_seconds = {"5m": "300", "15m": "900", "1h": "3600", "2h": "7200", "4h": "14400", "12h": "43200"}
    async with async_playwright() as playwright:
        launch_options = {"headless": True}
        executable = os.environ.get("RAVENBIN_CHROMIUM_PATH")
        if not executable:
            executable = next(
                (shutil.which(name) for name in CHROMIUM_CANDIDATES if shutil.which(name)),
                None,
            )
        if executable:
            launch_options["executable_path"] = executable
        if os.geteuid() == 0:
            launch_options["args"] = ["--no-sandbox"]
        browser = await playwright.chromium.launch(**launch_options)
        page = await browser.new_page()
        page.set_default_timeout(timeout * 1000)
        try:
            await page.goto(URL, wait_until="domcontentloaded")
            # The distro Chromium snap can expose /home but not /tmp to pages.
            # Stage the source inside a private home-directory temp folder so
            # uploads work consistently regardless of the source file location.
            with tempfile.TemporaryDirectory(
                prefix="ravenbin-upload-", dir=Path.home()
            ) as staging_dir:
                staged_path = Path(staging_dir) / file_path.name
                shutil.copyfile(file_path, staged_path)
                await page.set_input_files("#file", str(staged_path))
                await page.select_option("#expiry", expiry_seconds[expiry])
                await page.click("#create")
                await page.wait_for_function(
                    "() => document.querySelector('#link')?.value?.includes('#')",
                    timeout=timeout * 1000,
                )
                link = await page.input_value("#link")
            if not link.startswith("https://ravenbin.com/") or "#" not in link:
                raise RuntimeError("Raven returned an unexpected share URL")
            return link
        except PlaywrightTimeoutError as error:
            message = await page.locator("#err").text_content()
            detail = (message or "upload timed out").strip()
            raise RuntimeError(detail) from error
        finally:
            await browser.close()


def main() -> int:
    args = parse_args()
    if not args.file.is_file():
        print(f"error: file does not exist: {args.file}", file=sys.stderr)
        return 2
    try:
        link = asyncio.run(upload(args.file.resolve(), args.expiry, args.timeout))
    except Exception as error:
        print(f"error: {error}", file=sys.stderr)
        return 1
    print(link)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
