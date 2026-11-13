# Releasing mangadexSDK

## Get ready

The version lives in two places, and both must agree:

- `setup.cfg` — `version = X.Y.Z`
- `src/mangadexSdk/constants.py` — the fallback string in `_resolve_version()`

Bump both, then commit and push before you upload, so what is published is
always reachable in git history. Runtime dependencies belong in
`install_requires` in `setup.cfg`; if you add an import, add it there too.

```
pytest tests/
```

## Credentials

Create an API token at https://pypi.org/manage/account/token/ (scope:
`Project: mangadexSdk`). The username is always `__token__` and the password
is the `pypi-...` value, which PyPI shows only once.

Either use `~/.pypirc` (chmod 600, and twine will then skip your system
keyring):

```
[distutils]
index-servers = pypi

[pypi]
username = __token__
password = pypi-<your-token>
```

Or set environment variables:

```
export TWINE_USERNAME=__token__
export TWINE_PASSWORD='pypi-<your-token>'
```

## Build and push

```
rm -rf dist build
python -m build --outdir dist
twine check dist/*
twine upload dist/*
```

`twine check` should report `PASSED` for both files. If it does not, fix the
metadata before uploading.

## Verify

Install the uploaded package into a throwaway virtualenv and import it. This
is the step that catches undeclared dependencies — a package can upload
cleanly and still be unusable.

```
python -m venv /tmp/verify-venv
/tmp/verify-venv/bin/pip install "mangadexSdk==X.Y.Z"
/tmp/verify-venv/bin/python -c "from mangadexSdk.constants import Constants; print(Constants.VERSION)"
```

Note: PyPI filenames are immutable, so bump the version rather than
re-uploading the same build.
