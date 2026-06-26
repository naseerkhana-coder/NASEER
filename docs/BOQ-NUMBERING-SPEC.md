# BOQ & Project Numbering

## Project number (auto on create)

- **Prefix:** first two letters of project name (uppercase, letters only). Single letter is doubled (`G` → `GG`). No letters → `XX`.
- **Sequence:** per-prefix counter in `number_sequences`, starting at **100**.
- **Examples:** `MAXEK Tower` → `MA100`, `MAXEK Residency` → `MA101`, `GREEN CITY` → `GR100`.

Existing projects keep their current `project_code` (numeric or legacy). New projects only get the new format.

## BOQ master number

- Uses the **same prefix + per-prefix sequence** as projects (shared counter).
- Prefix is taken from the **selected project’s name** at create time.
- **Examples:** after `MA100` / `MA101` projects, the next `MA` BOQ is `MA102`. Under `GR100`, BOQs continue `GR101`, `GR102`, etc.

Legacy `BOQ###` masters are unchanged.

## BOQ line items

- Inside each BOQ master: `BOQ1`, `BOQ2`, `BOQ3`, … stored in `boq_items.item_code`.
- Restarts at `BOQ1` for every new BOQ master (not global per project).

## Audit fields

| Table        | Fields |
|-------------|--------|
| `projects`  | `created_by`, `created_at`, `modified_by`, `modified_at` |
| `boq_master`| above + `deleted_by`, `deleted_at`, `is_deleted` (soft delete) |
| `boq_items` | `created_by`, `created_at`, `modified_by`, `modified_at`, `deleted_by`, `deleted_at`, `is_deleted` |

## API

- `GET /api/projects/next-code?name=...` — preview next project code.
- `GET /api/projects/<id>/next-boq-number` — preview next BOQ master number for a project.

## Routes

- `GET /boq-print/<id>` — printable BOQ (`?print=1` auto-opens print dialog).
- `POST /boq-management` with `form_action=delete_boq` — soft-delete master and lines.
