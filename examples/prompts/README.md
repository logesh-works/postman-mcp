# Prompt examples

Ready-made personas for [`/postman:prompt`](../../docs/commands/prompt.md). Each file is a
copy-paste persona plus the command to run it with.

These prompts are **consumed by Claude**, not by the MCP server. They shape how Claude
reasons about and frames a sync — the terminology, examples, and documentation style it
favors — and become a structured `overrides` patch the engine merges. They do **not**
change route matching, identity, auth detection, schemas, response contracts, or merge
behavior; those are computed from your code regardless of the instruction. See the
[Prompt & skill layer](../../docs/architecture/overview.md#prompt-skill-layer).

| Prompt | Use it for |
|---|---|
| [`fintech.md`](fintech.md) | Payments, ledgers, and money-movement APIs. |
| [`healthcare.md`](healthcare.md) | Clinical / patient-data APIs with compliance framing. |
| [`enterprise.md`](enterprise.md) | Internal platform APIs that need formal documentation. |
| [`ecommerce.md`](ecommerce.md) | Storefront, cart, and order APIs. |

## How to use one

Copy the persona text from a file into `/postman:prompt`, naming the target:

```text
/postman:prompt "Sync createPayment as a Stripe API architect. Use fintech terminology and strict input-validation framing."
```

> `/postman:prompt` guides Claude, which turns the instruction into a structured
> `overrides` patch. The MCP server stays deterministic and runs no LLM — the same code +
> overrides always produces the same Postman item, and everything goes through the diff
> gate before any write.

Looking ahead, these prompts are the seed for the named `--skill` bundles on the
[roadmap](../../ROADMAP.md#skills).
