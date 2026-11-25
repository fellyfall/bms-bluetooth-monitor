# Release v0.6-alpha

## Highlights

- Store measurements in a local SQLite database using Python's standard library.
- Import existing monthly CSV logs automatically without deleting the original files.
- Export database measurements to monthly CSV files with `python database.py --export-csv`.
- Apply dashboard time filters and chart downsampling directly in SQLite.
- Keep support for variable cell counts and Windows/Linux.

## Compatibility

Existing ECO-WORTHY CSV logs are imported on first use and remain untouched. The database and its SQLite journal files are local data and are excluded from Git and release archives.

This is an alpha release. Back up the original CSV logs before trying it, and report any migration or display issues. Python 3.11 or newer is required; see [README.md](README.md) for setup and data-management instructions.
