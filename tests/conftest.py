from hypothesis import settings

# Deterministic property tests: the same examples on every run and on CI (no example database).
settings.register_profile("r2h", derandomize=True, database=None, print_blob=True)
settings.load_profile("r2h")
