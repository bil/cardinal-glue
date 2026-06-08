import argparse
import os
import sys
import json
from cardinal_glue.workgroup_api.workgroup import Workgroup, WorkgroupManager

def setup_auth():
    cert_path = os.path.expanduser("~/cardinal-glue/stanford_workgroup.cert")
    key_path = os.path.expanduser("~/cardinal-glue/stanford_workgroup.key")
    if not os.path.exists(cert_path) or not os.path.exists(key_path):
        print(json.dumps({"error": f"Missing auth files at {cert_path} or {key_path}"}))
        sys.exit(1)
    os.environ["WORKGROUP_CERT_PATH"] = cert_path
    os.environ["WORKGROUP_KEY_PATH"] = key_path

def main():
    setup_auth()
    parser = argparse.ArgumentParser(description="Stanford Workgroup Unified CLI Tool")
    subparsers = parser.add_subparsers(dest="command", required=True)

    # list
    p_list = subparsers.add_parser("list", help="List workgroups under a stem")
    p_list.add_argument("stem")

    # query
    p_query = subparsers.add_parser("query", help="Query details of a specific workgroup")
    p_query.add_argument("stem")
    p_query.add_argument("name")

    # create
    p_create = subparsers.add_parser("create", help="Create a new workgroup")
    p_create.add_argument("stem")
    p_create.add_argument("name")
    p_create.add_argument("description")
    p_create.add_argument("--filter_in", default="NONE")
    p_create.add_argument("--reusable", default="FALSE")
    p_create.add_argument("--visibility", default="PRIVATE")
    p_create.add_argument("--privgroup", default="TRUE")

    # delete
    p_delete = subparsers.add_parser("delete", help="Delete a workgroup")
    p_delete.add_argument("stem")
    p_delete.add_argument("name")

    # copy
    p_copy = subparsers.add_parser("copy", help="Copy or move a workgroup")
    p_copy.add_argument("stem")
    p_copy.add_argument("name")
    p_copy.add_argument("--new_stem", help="Destination stem")
    p_copy.add_argument("--new_name", help="Destination name")
    p_copy.add_argument("--remove_original", action="store_true", help="Move the workgroup instead of copying")
    p_copy.add_argument("--overwrite", action="store_true", help="Sync to destination if it exists")

    # update
    p_update = subparsers.add_parser("update", help="Update properties of an existing workgroup")
    p_update.add_argument("stem")
    p_update.add_argument("name")
    p_update.add_argument("--description")
    p_update.add_argument("--reusable")
    p_update.add_argument("--visibility")
    p_update.add_argument("--privgroup")
    p_update.add_argument("--filter_in")

    # add-members
    p_add_mem = subparsers.add_parser("add-members", help="Add members to a workgroup")
    p_add_mem.add_argument("stem")
    p_add_mem.add_argument("name")
    p_add_mem.add_argument("members", nargs="+", help="List of members to add")
    p_add_mem.add_argument("--type", default="USER", help="'USER', 'WORKGROUP', or 'CERTIFICATE'")

    # remove-members
    p_rem_mem = subparsers.add_parser("remove-members", help="Remove members from a workgroup")
    p_rem_mem.add_argument("stem")
    p_rem_mem.add_argument("name")
    p_rem_mem.add_argument("members", nargs="+", help="List of members to remove")

    # add-admins
    p_add_adm = subparsers.add_parser("add-admins", help="Add admins to a workgroup")
    p_add_adm.add_argument("stem")
    p_add_adm.add_argument("name")
    p_add_adm.add_argument("admins", nargs="+", help="List of admins to add")
    p_add_adm.add_argument("--type", default="USER", help="'USER', 'WORKGROUP', or 'CERTIFICATE'")

    # remove-admins
    p_rem_adm = subparsers.add_parser("remove-admins", help="Remove admins from a workgroup")
    p_rem_adm.add_argument("stem")
    p_rem_adm.add_argument("name")
    p_rem_adm.add_argument("admins", nargs="+", help="List of admins to remove")

    args = parser.parse_args()

    try:
        if args.command == "list":
            mgr = WorkgroupManager(args.stem)
            mgr.populate_workgroup_list()
            print(json.dumps({"workgroups": mgr.workgroup_list}, indent=2))
        
        elif args.command == "query":
            wg = Workgroup(args.stem, args.name)
            print(json.dumps({
                "workgroup": f"{args.stem}:{args.name}",
                "description": wg.description,
                "members": wg.members,
                "admins": [a.get('id') for a in wg.admins if a.get('id')] if wg.admins else [],
                "privgroup_members": [m.get('id') for m in wg.privgroup_members if m.get('id')] if wg.privgroup_members else [],
                "privgroup_admins": [a.get('id') for a in wg.privgroup_admins if a.get('id')] if wg.privgroup_admins else []
            }, indent=2))

        elif args.command == "create":
            mgr = WorkgroupManager(args.stem)
            mgr.create_workgroup(args.name, args.description, args.filter_in, args.reusable, args.visibility, args.privgroup)
            print(json.dumps({"status": "success", "message": f"Created {args.stem}:{args.name}"}))

        elif args.command == "delete":
            mgr = WorkgroupManager(args.stem)
            mgr.delete_workgroup(args.name)
            print(json.dumps({"status": "success", "message": f"Deleted {args.stem}:{args.name}"}))

        elif args.command == "copy":
            mgr = WorkgroupManager(args.stem)
            res = mgr.copy_workgroup(args.name, args.new_stem, args.new_name, args.remove_original, args.overwrite)
            print(json.dumps(res, indent=2))

        elif args.command == "update":
            wg = Workgroup(args.stem, args.name)
            # Filter out None values dynamically
            update_args = {k: v for k, v in vars(args).items() if k not in ['command', 'stem', 'name'] and v is not None}
            if update_args:
                wg.update_properties(**update_args)
                print(json.dumps({"status": "success", "message": f"Updated properties for {args.stem}:{args.name}", "updated": update_args}))
            else:
                print(json.dumps({"status": "ignored", "message": "No properties provided to update."}))

        elif args.command == "add-members":
            wg = Workgroup(args.stem, args.name)
            wg.add_members(args.members, member_type=args.type, ignore_missing=True)
            print(json.dumps({"status": "success", "message": f"Added members to {args.stem}:{args.name}"}))

        elif args.command == "remove-members":
            wg = Workgroup(args.stem, args.name)
            wg.remove_members(args.members)
            print(json.dumps({"status": "success", "message": f"Removed members from {args.stem}:{args.name}"}))

        elif args.command == "add-admins":
            wg = Workgroup(args.stem, args.name)
            wg.add_admins(args.admins, admin_type=args.type, ignore_missing=True)
            print(json.dumps({"status": "success", "message": f"Added admins to {args.stem}:{args.name}"}))

        elif args.command == "remove-admins":
            wg = Workgroup(args.stem, args.name)
            wg.remove_admins(args.admins)
            print(json.dumps({"status": "success", "message": f"Removed admins from {args.stem}:{args.name}"}))

    except Exception as e:
        print(json.dumps({"error": str(e)}), file=sys.stderr)
        sys.exit(1)

if __name__ == "__main__":
    main()
