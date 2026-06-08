---
name: stanford-workgroup
description: Unified CLI for managing Stanford Workgroups (querying, listing, creating, deleting, copying, updating properties, and managing members/admins). Use this skill whenever you need to interact with the Stanford Workgroup API.
---

# Stanford Workgroup Manager Skill

## Instructions

This skill provides a unified Python CLI (`wg_tool.py`) wrapped in a bash script (`wg_tool.sh`) for interacting with the Stanford Workgroup API via `cardinal-glue`. 

When the user asks you to perform a workgroup operation, determine the correct sub-command and arguments, and execute it using `run_shell_command`.

### Command Format
Use the following format for all operations:
```bash
bash __DIR__/scripts/wg_tool.sh <command> [args]
```

### Supported Commands

1. **List Workgroups**: `list <stem>`
2. **Query Workgroup Details**: `query <stem> <name>`
3. **Create Workgroup**: `create <stem> <name> <description> [--filter_in] [--reusable] [--visibility] [--privgroup]`
4. **Delete Workgroup**: `delete <stem> <name>`
5. **Copy/Move Workgroup**: `copy <stem> <name> [--new_stem] [--new_name] [--remove_original] [--overwrite]`
6. **Update Properties**: `update <stem> <name> [--description] [--reusable] [--visibility] [--privgroup] [--filter_in]`
7. **Add Members**: `add-members <stem> <name> <members...> [--type USER|WORKGROUP|CERTIFICATE]`
8. **Remove Members**: `remove-members <stem> <name> <members...>`
9. **Add Admins**: `add-admins <stem> <name> <admins...> [--type USER|WORKGROUP|CERTIFICATE]`
10. **Remove Admins**: `remove-admins <stem> <name> <admins...>`

### Examples
- Query: `bash __DIR__/scripts/wg_tool.sh query wutsaineuro dbp_slides_200`
- Create: `bash __DIR__/scripts/wg_tool.sh create dept my_group "My description" --reusable FALSE`
- Add Admin: `bash __DIR__/scripts/wg_tool.sh add-admins dept my_group other_dept:admin_group --type WORKGROUP`

## Authentication Note
The bundled script automatically configures the environment variables to look for authentication files in `~/cardinal-glue/stanford_workgroup.cert` and `~/cardinal-glue/stanford_workgroup.key`. If authentication fails due to missing files, instruct the user to ensure those files are placed in their `~/cardinal-glue/` folder.