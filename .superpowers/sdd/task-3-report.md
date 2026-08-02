# Task 3 Report: Corrigir caminho do DB no `backup.sh`

## Status: DONE

## What I implemented
Single-line change in `scripts/backup.sh` per brief Step 1:
- `DB="$REPO_DIR/server/estudiohc_memory.db"` → `DB="$REPO_DIR/data/estudiohc.db"`

No other lines in the file were touched.

## What I tested
Brief Step 2 expects `grep -n '^DB=' scripts/backup.sh` → `DB="$REPO_DIR/data/estudiohc.db"`.

`grep` is not available in this Windows PowerShell environment; used the equivalent `Select-String -Path scripts\backup.sh -Pattern '^DB='`:

```
scripts\backup.sh:14:DB="$REPO_DIR/data/estudiohc.db"
```

Verified — DB now points to the real DB path. Syntax not executable locally (Linux bash script), but the change is a pure string substitution on line 14 and does not alter surrounding syntax.

## Files changed
- `scripts/backup.sh` (1 insertion, 1 deletion)

## Commit
- `eb39ce8` — fix(scripts): correct DB path in backup.sh

## Self-review findings
- Only the DB variable line was modified; `git show --stat HEAD` confirms 1 insertion / 1 deletion in `scripts/backup.sh`.
- Backup script logic unchanged (still calls `backup_file "$DB" "memory-db"`, which will now find the real DB).
- `.superpowers/` and `docs/` remain untracked and were intentionally not committed.

## Issues / concerns
- None. Full server-side validation is deferred to Task 7 (deploy) as noted in the brief.
