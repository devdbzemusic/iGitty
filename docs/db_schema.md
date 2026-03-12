# Datenbankschema

## `igitty_jobs.db`

Tabelle `jobs`:

- `job_id`
- `action_type`
- `source_type`
- `repo_name`
- `status`
- `message`
- `created_at`

## `repo_struct_vault.db`

Tabelle `repo_tree_items`:

- `repo_identifier`
- `source_type`
- `root_path`
- `relative_path`
- `item_type`
- `size`
- `extension`
- `last_modified`
- `git_status`
- `last_commit_hash`
- `version_scan_timestamp`
