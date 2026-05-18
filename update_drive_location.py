"""One-shot: add `location: "India"` to the Apify source's input dict on Drive."""

import logging

from src.config import ApifySource, load_config, save_config
from src.logging_config import setup_logging

setup_logging(logging.INFO)

config = load_config()
print("BEFORE:", [(s.name, getattr(s, "input", None)) for s in config.sources])

for src in config.sources:
    if isinstance(src, ApifySource):
        src.input["location"] = "India"

print("AFTER: ", [(s.name, getattr(s, "input", None)) for s in config.sources])

save_config(config)
print("uploaded to Drive")
