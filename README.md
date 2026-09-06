# ravenbin-upload

Upload a file to [Raven Bin](https://ravenbin.com/) from one shell command.

The command opens Raven's current web client in headless Chromium. Raven performs the client-side encryption and upload, so this tool does not reimplement or bypass Raven's protocol.

## Install

```bash
python3 -m venv .venv
. .venv/bin/activate
python -m pip install .
playwright install chromium
```

On Linux, a system Chromium binary can be selected with:

```bash
export RAVENBIN_CHROMIUM_PATH=/usr/bin/chromium
```

## Use

```bash
ravenbin-upload ./report.zip
```

The share URL is printed to stdout. Progress and errors go to stderr.

```bash
link="$(ravenbin-upload /tmp/output.json)"
printf '%s\n' "$link"
```

Choose an expiry from Raven's current public options:

```bash
ravenbin-upload --expiry 5m ./short-lived.log
ravenbin-upload --expiry 12h ./artifact.tar
```

Available values are `5m`, `15m`, `1h`, `2h`, `4h`, and `12h`. The default is `15m`.

## Notes

- Raven currently limits users to six active bins and two in-progress uploads.
- The returned URL contains the decryption key after `#`. Treat the complete URL as a secret.
- The wrapper stages the input in a temporary directory under the user's home directory. This supports Chromium sandbox variants that cannot read `/tmp`. The staged copy is removed after upload.
- Uploads depend on Raven's service availability and current web client.
- Do not use this as the only protection for credentials, private keys, or regulated data.

## License

MIT. Raven Bin is a separate service operated by Raven Technologies Group.
