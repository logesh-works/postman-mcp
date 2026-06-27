// A minimal Express payments API — the code-parsing example.
//
// Express has no native OpenAPI spec and no native types, so Postman MCP uses the
// code-parsing path. Body inference is best-effort and flagged "lower confidence";
// the JSDoc @body annotations below help it.
//
// Run it:
//   npm install
//   node app.js

const express = require("express");
const app = express();
app.use(express.json());

// Auth middleware — Postman MCP detects this in the chain → Bearer {{token}}
function requireAuth(req, res, next) {
  if (!req.headers.authorization) {
    return res.status(401).json({ error: "Not authenticated" });
  }
  next();
}

/**
 * Create a new payment.
 * @route POST /payments
 * @body {number} amount   Amount in minor units (cents)
 * @body {string} currency ISO 4217 currency code
 * @body {string} method   card | bank | wallet
 */
app.post("/payments", requireAuth, (req, res) => {
  const { amount, currency = "USD" } = req.body;
  res.status(201).json({
    id: "pay_abc123",
    amount,
    currency,
    status: "succeeded",
    created_at: "2026-06-27T10:00:00Z",
  });
});

/**
 * Fetch a single payment by id.
 * @route GET /payments/:id
 */
app.get("/payments/:id", requireAuth, (req, res) => {
  res.json({
    id: req.params.id,
    amount: 4200,
    currency: "USD",
    status: "succeeded",
    created_at: "2026-06-27T10:00:00Z",
  });
});

app.listen(3000, () => console.log("listening on :3000"));
