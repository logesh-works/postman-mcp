"""The Witness Engine — the demoted parsers, now an independent verification oracle.

The framework parsers under ``postman_mcp.input`` are **not removed**. This package
wraps them without moving or rewriting their logic, and gives them three roles:
verification witness (cross-checked against a submitted APIM), fallback extraction
engine (:func:`witness_to_apim` produces a valid APIM with no LLM involved, keeping
every legacy command working unchanged), and nothing else — no new framework
intelligence is added here.
"""

from postman_mcp.witness.engine import WitnessSet, build_witness_set, witness_to_apim

__all__ = ["WitnessSet", "build_witness_set", "witness_to_apim"]
