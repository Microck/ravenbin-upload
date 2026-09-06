<h1 align="center">ravenbin-upload</h1>

<p align="center">
  <a href="LICENSE"><img src="https://img.shields.io/badge/license-mit-000000?style=flat-square" alt="license badge"></a>
</p>

---

`ravenbin-upload` uploads a file to [Raven Bin](https://ravenbin.com/) from one shell command. it opens Raven's current web client in headless Chromium, so Raven performs the client-side encryption and upload instead of this tool reimplementing its protocol.

[github](https://github.com/Microck/ravenbin-upload) | [raven bin](https://ravenbin.com/) | [about bin](https://ravenbin.com/about/)

## start here

### install from source

```bash
git clone https://github.com/Microck/ravenbin-upload.git
cd ravenbin-upload
python3 -m venv .venv
. .venv/bin/activate
python -m pip install .
playwright install chromium
```

### upload a file

```bash
ravenbin-upload ./report.zip
```

The share URL is printed to stdout. Progress and errors go to stderr.

```bash
link="$(ravenbin-upload /tmp/output.json)"
printf '%s\n' "$link"
```

## expiry

Raven currently supports these expiry values:

```bash
ravenbin-upload --expiry 5m ./short-lived.log
ravenbin-upload --expiry 15m ./report.zip
ravenbin-upload --expiry 12h ./artifact.tar
```

The default is `15m`. Available values are `5m`, `15m`, `1h`, `2h`, `4h`, and `12h`.

## why

if an agent or shell workflow needs to share a temporary artifact, this gives it one command without a separate upload service or a litterbox workflow.

- upload arbitrary file types
- keep the normal Raven Bin client-side encryption flow
- use the returned URL directly in shell pipelines
- remove the local staged copy after upload
- choose the shortest expiry when the artifact should disappear quickly

## how it works

The command runs Raven's current web client in headless Chromium. It selects the file, chooses the expiry, and submits the normal `Create Bin` flow. Raven encrypts the file in the browser and uploads it in chunks.

The wrapper stages the input in a temporary directory under the user's home directory. This supports Chromium sandbox variants that cannot read `/tmp`. The staged copy is removed after upload.

## requirements

- Python 3.9 or newer
- Playwright
- Chromium, installed with `playwright install chromium` or selected with `RAVENBIN_CHROMIUM_PATH`

For a system browser:

```bash
export RAVENBIN_CHROMIUM_PATH=/usr/bin/chromium
```

## limits and security

- Raven currently allows six active bins and two in-progress uploads.
- Raven's public service can be busy or unavailable.
- The complete returned URL is sensitive. The decryption key is stored after `#`.
- Do not put returned URLs in logs or share them with people who should not read the file.
- Do not use Raven Bin as the only protection for credentials, private keys, or regulated data.

## license

MIT. Raven Bin is a separate service operated by Raven Technologies Group.
