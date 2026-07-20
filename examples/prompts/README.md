# Prompt examples

Ready-made personas for [`/postman:prompt`](../../docs/commands/prompt.md). Each file is a
copy-paste persona plus the command to run it with.

These prompts are **read by Claude**, not by the MCP server. They shape how Claude
reasons about and frames a sync — the terminology, examples, and documentation style it
favors — which Claude folds directly into the collection it authors. They do **not**
change route identity, citations, or field grounding; those come from your code
regardless of the instruction, and the MCP server verifies them the same way either way.
See the [Prompt & skill layer](../../docs/architecture/overview.md#prompt-skill-layer).

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

> `/postman:prompt` guides Claude, which folds the instruction directly into what it
> authors. The MCP server stays deterministic and runs no LLM — it validates, verifies,
> and diffs whatever Claude wrote, and nothing reaches Postman before you've seen and
> confirmed the diff.

Looking ahead, these prompts are the seed for the named `--skill` bundles on the
[roadmap](../../ROADMAP.md).
