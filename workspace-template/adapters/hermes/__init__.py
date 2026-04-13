# Hermes adapter — PR 1 shell (Dockerfile + image deps only).
# adapter.py and HermesAdapter class are added in PR 2.
# The adapter loader (adapters/__init__.py:discover_adapters) gracefully skips
# this module until `Adapter` is exported from adapter.py.
