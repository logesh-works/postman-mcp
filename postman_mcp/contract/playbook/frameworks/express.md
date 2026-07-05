# Express discovery guide

**Registration signals:** `router.get(`, `router.post(`, `router.put(`, `router.patch(`,
`router.delete(` on any `express.Router()` instance — the variable name is often not
literally `router`, so match the pattern regardless of identifier.

**Mount chain:** `app.use('/prefix', childRouter)` — resolve `childRouter` through its
`require`/`import` specifier to the file that defines it, including the inline form
`app.use('/prefix', require('./x'))`. A prefix-less `app.use(childRouter)` mounts at
the parent's own prefix unchanged.

**Request body:** in priority order — a Joi/Zod/Yup validation schema applied via
middleware (cite the schema definition), then a JSDoc `@body` tag, then destructuring
or dot-access on `req.body` in the handler (mark this `ai_inferred`, not higher — Express
gives no static type here).

**Auth:** inline middleware in the route registration (`router.post('/x', requireAuth,
handler)`) or a file-scoped `app.use(requireAuth)` applied before the router mounts.

**Known unresolved cases:** a computed prefix (`app.use(\`/api/${version}\`, router)`) —
emit `{{api_version}}` or similar and note it in `unresolved`.
