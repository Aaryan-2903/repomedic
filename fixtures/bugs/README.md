# Repomedic Bug Fixtures

This directory contains reproducible, controlled software bug benchmarks used to evaluate and test Repomedic's debugging agents.

## Structure of a Fixture

Each subdirectory under `fixtures/bugs/` represents a single isolated bug scenario:

```
fixtures/bugs/<fixture-id>/
├── fixture.json      # Metadata descriptor (language, reproduce command, expected results)
├── README.md         # Plain-language explanation of the bug and intended behavior
└── <source_files>    # Source code and reproduction tests
```

## `fixture.json` Schema

```json
{
  "id": "sample-calculator-bug",
  "name": "Calculator Off-By-One Division",
  "language": "python",
  "difficulty": "beginner",
  "description": "Division operation fails with negative divisors.",
  "reproduce_cmd": "python -m unittest test_calc.py",
  "expected_failure_pattern": "AssertionError",
  "target_file": "calc.py"
}
```

## Running a Fixture Manually

```bash
cd fixtures/bugs/sample-calculator-bug
python -m unittest test_calc.py
```
