# Prompt examples

Ready-made `--prompt` guidance for the sync commands. Each file is a copy-paste persona
plus the command to run it with.

These prompts are **consumed by Claude**, not by the MCP server. They shape how Claude
reasons about and frames a sync — the terminology, examples, and documentation style it
favors. They do **not** change anything the deterministic engine produces: route matching,
identity, auth detection, schemas, response contracts, and merge behavior are computed
from your code regardless of the prompt. See the
[Prompt & skill layer](../../docs/architecture/overview.md#prompt-skill-layer).

| Prompt | Use it for |
|---|---|
| [`fintech.md`](fintech.md) | Payments, ledgers, and money-movement APIs. |
| [`healthcare.md`](healthcare.md) | Clinical / patient-data APIs with compliance framing. |
| [`enterprise.md`](enterprise.md) | Internal platform APIs that need formal documentation. |
| [`ecommerce.md`](ecommerce.md) | Storefront, cart, and order APIs. |

## How to use one

Copy the prompt text from a file and pass it to any sync command:

```text
/postman:syncapi createPayment --prompt "Act as a Stripe API architect. Use fintech terminology and enterprise-grade validation framing."
```

> `--prompt` guides Claude. The MCP server stays deterministic and runs no LLM — the same
> code always produces the same Postman item. The prompt only changes how Claude prepares
> and presents the work around that deterministic output.

Looking ahead, these prompts are the seed for the named `--skill` bundles on the
[roadmap](../../ROADMAP.md#skills).
