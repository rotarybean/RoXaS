# software

## tools/extract_dtcs.py

Extracts one record per DTC (code, title, detection logic, monitor type, causes)
from a factory engine-control manual that has a text layer.

Requirements: Python 3 and `poppler-utils` (`pdftotext`).

```bash
sudo apt install -y poppler-utils
python software/tools/extract_dtcs.py data/manuals/04EngineControl.pdf
```

Output is `dtc.json` and `dtc.sqlite` in the current directory. Both are
git-ignored because they are derived from copyrighted material.

Notes:

- The manual stores range dashes as a private-use glyph (U+F8E7) that extraction
  drops silently, turning `0.20-0.45` into `0.200.45`. The script replaces it
  with a hyphen.
- Two codes (P0128, P0302) appear only in the manual's summary table and are not
  captured. Handle them by hand.
- The diagnostic flowchart pages that follow each DTC are skipped on purpose.
