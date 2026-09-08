#!/usr/bin/env python3
"""Upload to or fetch a file from Raven Bin."""

import argparse
import asyncio
import base64
import os
import shutil
import sys
import tempfile
from pathlib import Path
from typing import Any, Optional
from urllib.parse import urlsplit

from playwright.async_api import TimeoutError as PlaywrightTimeoutError
from playwright.async_api import async_playwright

URL = "https://ravenbin.com/"
CHROMIUM_CANDIDATES = ("chromium", "chromium-browser", "google-chrome")
def browser_options() -> dict[str, Any]:
    options = {"headless": True}
    executable = os.environ.get("RAVENBIN_CHROMIUM_PATH")
    if not executable:
        executable = next(
            (shutil.which(name) for name in CHROMIUM_CANDIDATES if shutil.which(name)),
            None,
        )
    if executable:
        options["executable_path"] = executable
    if os.geteuid() == 0:
        options["args"] = ["--no-sandbox"]
    return options


def add_common_options(parser: argparse.ArgumentParser) -> None:
    parser.add_argument(
        "--timeout",
        type=float,
        default=300,
        help="Operation timeout in seconds (default: 300).",
    )


def parse_args() -> argparse.Namespace:
    if len(sys.argv) > 1 and sys.argv[1] == "fetch":
        parser = argparse.ArgumentParser(
            prog="ravenbin-upload fetch",
            description="Fetch and decrypt a Raven Bin URL.",
        )
        parser.add_argument("url", help="Complete Raven Bin URL, including the # key.")
        parser.add_argument("--output", type=Path, help="Output path (default: stored filename).")
        parser.add_argument("--force", action="store_true", help="Overwrite an existing output file.")
        add_common_options(parser)
        return parser.parse_args(sys.argv[2:])

    parser = argparse.ArgumentParser(
        prog="ravenbin-upload",
        description="Encrypt and upload a file to Raven Bin.",
    )
    parser.add_argument("file", type=Path)
    parser.add_argument(
        "--expiry",
        choices=("5m", "15m", "1h", "2h", "4h", "12h"),
        default="12h",
        help="How long Raven Bin keeps the upload (default: 12h).",
    )
    add_common_options(parser)
    return parser.parse_args()


async def upload(file_path: Path, expiry: str, timeout: float) -> str:
    expiry_seconds = {
        "5m": "300",
        "15m": "900",
        "1h": "3600",
        "2h": "7200",
        "4h": "14400",
        "12h": "43200",
    }
    async with async_playwright() as playwright:
        browser = await playwright.chromium.launch(**browser_options())
        page = await browser.new_page()
        page.set_default_timeout(timeout * 1000)
        try:
            await page.goto(URL, wait_until="domcontentloaded")
            # Some Chromium sandbox variants cannot expose /tmp to pages.
            # Stage the source under home so uploads work consistently.
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
            if not link.startswith(URL) or "#" not in link:
                raise RuntimeError("Raven returned an unexpected share URL")
            return link
        except PlaywrightTimeoutError as error:
            message = await page.locator("#err").text_content()
            detail = (message or "upload timed out").strip()
            raise RuntimeError(detail) from error
        finally:
            await browser.close()


def validate_fetch_url(url: str) -> None:
    parsed = urlsplit(url)
    if parsed.scheme != "https" or parsed.hostname != "ravenbin.com":
        raise ValueError("URL must be a complete https://ravenbin.com/ share URL")
    if not parsed.query or not parsed.fragment:
        raise ValueError("URL must include both the bin id and the decryption key after #")


async def fetch_bin(url: str, output: Optional[Path], force: bool, timeout: float) -> Path:
    validate_fetch_url(url)
    async with async_playwright() as playwright:
        browser = await playwright.chromium.launch(**browser_options())
        page = await browser.new_page()
        page.set_default_timeout(timeout * 1000)
        try:
            await page.goto(url, wait_until="domcontentloaded")
            await page.wait_for_function(
                """() => {
                    const download = document.querySelector('#download[href]');
                    const text = document.querySelector('#output');
                    const error = document.querySelector('#read-err:not(.hidden)');
                    return download || (text && text.value) || error;
                }""",
                timeout=timeout * 1000,
            )
            error = await page.locator("#read-err").text_content()
            if error and await page.locator("#read-err").is_visible():
                raise RuntimeError(error.strip())

            download = page.locator("#download[href]")
            if await download.count():
                blob_info = await download.evaluate(
                    """async (element) => {
                        const response = await fetch(element.href);
                        const blob = await response.blob();
                        if (blob.size > 100000000) {
                            return {tooLarge: true, size: blob.size};
                        }
                        const bytes = new Uint8Array(await blob.arrayBuffer());
                        let binary = '';
                        for (let i = 0; i < bytes.length; i += 0x8000) {
                            binary += String.fromCharCode(...bytes.subarray(i, i + 0x8000));
                        }
                        return {
                            name: element.download || 'download',
                            data: btoa(binary),
                        };
                    }"""
                )
                if blob_info.get("tooLarge"):
                    raise RuntimeError(
                        "this fetch path supports files up to 100 MB; Raven used its streaming download path"
                    )
                data = base64.b64decode(blob_info["data"])
                default_name = Path(blob_info["name"]).name or "download"
            else:
                data = (await page.locator("#output").input_value()).encode()
                default_name = "download.txt"
        except PlaywrightTimeoutError as error:
            message = await page.locator("#read-err").text_content()
            detail = (message or "fetch timed out").strip()
            raise RuntimeError(detail) from error
        finally:
            await browser.close()

    destination = output or Path(default_name)
    if destination.exists() and not force:
        raise FileExistsError(f"output exists: {destination}; use --force to overwrite")
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_bytes(data)
    return destination


def main() -> int:
    args = parse_args()
    try:
        if len(sys.argv) > 1 and sys.argv[1] == "fetch":
            path = asyncio.run(fetch_bin(args.url, args.output, args.force, args.timeout))
            print(path)
            return 0
        if not args.file.is_file():
            print(f"error: file does not exist: {args.file}", file=sys.stderr)
            return 2
        print(asyncio.run(upload(args.file.resolve(), args.expiry, args.timeout)))
        return 0
    except Exception as error:
        print(f"error: {error}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
