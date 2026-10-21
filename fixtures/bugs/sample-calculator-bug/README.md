# Sample Bug Fixture: Calculator Division Bug

### Overview
This fixture demonstrates a reproducible bug in a basic arithmetic library:
- In `calc.py`, the `divide` function incorrectly performs floor division (`//`) instead of floating-point division (`/`).
- Running the unit tests fails with `AssertionError` on tests expecting precise fractional quotients.

### Reproducing the Failure
```bash
python -m unittest test_calc.py
```
Expected output:
```
FAIL: test_divide_fractional (test_calc.TestCalculator.test_divide_fractional)
AssertionError: 2 != 2.5 within 7 places (0.5 difference)
```

### Expected Fix
Change `a // b` to `a / b` in `calc.py:22`.
