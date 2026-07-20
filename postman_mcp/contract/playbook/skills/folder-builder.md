# Skill: Folder Builder

**Responsibility:** decide the module boundary — which `postman/sync/<module>/` a
resource's requests belong to — and, within one module's own `collection.json`, whether
its requests need any further sub-folder nesting. Not the requests themselves, not
assembling either document (`collection-builder`).

## The top-level grouping is now a directory, not a JSON folder

Each logical module (one per controller/router/domain — a `UsersController` becomes
`postman/sync/users/`) gets its own subfolder under `postman/sync/`, each with its own
`collection.json` (+ `metadata.json`). The MCP assembles every module directory into one
named Postman folder in the target collection — `info.name` inside that module's
`collection.json` is the name that shows up. Endpoints that don't belong to any real
module (or a small API with no modules yet) can go in the ungrouped root
`postman/sync/collection.json` instead; those land at the collection's top level with no
wrapping folder.

For a narrow scope (`syncapi` on one endpoint), you don't need to invent a module at all
if the code's organization doesn't strongly imply one — write it to the ungrouped root
files, or into the one module it obviously belongs to.

## Nesting within a module

A module's own `collection.json` can still nest sub-folders in its `item[]` (e.g.
`auth/collection.json` might have "OAuth" and "Password Reset" sub-folders) exactly like
the old single-file layout did — this only matters for large modules with real internal
structure; most modules are fine as one flat list of requests.

## The one hard rule: no duplicate sibling names

**Two folders at the same level must not share a name** — this applies both to two
module directories that would resolve to the same display name, and to two sub-folders
nested inside one module's `collection.json`. The MCP matches folders by name when
merging, so two same-named siblings would be ambiguous and the whole sync is rejected as
a structural error until fixed — this is not a soft warning. Disambiguate module
directory names and `info.name` values if two different resources would naturally
collide (unlikely, but possible in a large monorepo).

## Consistency across re-syncs

Once you've picked a module directory name (and its `info.name`) for a resource, keep
using both on later syncs (`syncchanges`, subsequent `syncapi` calls) — the MCP finds
existing folders by name, so renaming either between runs creates a duplicate instead of
reusing the original, scattering that resource's requests across two folders.

## What you're producing

Which module directory (or the ungrouped root) each resource's requests go to, and —
within a module — the sub-folder tree (possibly just flat) that `collection-builder`
places request items into.
