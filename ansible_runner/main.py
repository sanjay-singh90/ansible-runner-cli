import os
import subprocess
import sys
import re
from pathlib import Path
import configparser

# ====== CONFIGURATION ======
REPO_URL = "git@yourgitlab.com:yourgroup/ansible-repo.git"
LOCAL_REPO_PATH = Path.home() / "ansible-repo"
ANSIBLE_CFG_PATH = LOCAL_REPO_PATH / "ansible.cfg"
CUSTOM_COMMANDS_FILE = LOCAL_REPO_PATH / "custom_commands.txt"
# ===========================

def clone_or_update_repo():
    if LOCAL_REPO_PATH.exists():
        print("[INFO] Pulling latest changes from repo...")
        subprocess.run(["git", "-C", str(LOCAL_REPO_PATH), "pull"], check=True)
    else:
        print("[INFO] Cloning repo...")
        subprocess.run(["git", "clone", REPO_URL, str(LOCAL_REPO_PATH)], check=True)

def get_ansible_config():
    """Read ansible.cfg for default SSH user/key."""
    user, key = None, None
    if ANSIBLE_CFG_PATH.exists():
        config = configparser.ConfigParser(allow_no_value=True, delimiters=('=',))
        config.read(ANSIBLE_CFG_PATH)
        if 'defaults' in config:
            if 'private_key_file' in config['defaults']:
                key = os.path.expanduser(config['defaults']['private_key_file'])
            if 'remote_user' in config['defaults']:
                user = config['defaults']['remote_user']
    return user, key

def list_inventories():
    inventories_dir = LOCAL_REPO_PATH / "inventories"
    if not inventories_dir.exists():
        print("[ERROR] No inventories directory found.")
        sys.exit(1)
    return [d.name for d in inventories_dir.iterdir() if d.is_dir()]

def get_hosts_from_inventory(inventory_path):
    hosts = []
    try:
        with open(inventory_path, "r") as f:
            for line in f:
                line = line.strip()
                if line and not line.startswith("[") and not line.startswith("#"):
                    hostname = re.split(r"\s+", line)[0]
                    hosts.append(hostname)
    except FileNotFoundError:
        print(f"[ERROR] Inventory file not found: {inventory_path}")
    return hosts

def check_ssh_connectivity(hosts, ssh_key=None, user=None):
    failed_hosts = []
    for host in hosts:
        ssh_cmd = ["ssh", "-o", "BatchMode=yes", "-o", "ConnectTimeout=5"]
        if ssh_key:
            ssh_cmd.extend(["-i", ssh_key])
        target = f"{user}@{host}" if user else host
        ssh_cmd.append(target)
        ssh_cmd.append("exit")
        result = subprocess.run(ssh_cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        if result.returncode != 0:
            failed_hosts.append(host)
    return failed_hosts

def run_ansible_playbook(inventory, playbook):
    inventory_path = LOCAL_REPO_PATH / "inventories" / inventory / "hosts"
    hosts = get_hosts_from_inventory(inventory_path)

    user, key = get_ansible_config()
    print(f"[INFO] Checking SSH connectivity to {len(hosts)} hosts...")
    failed = check_ssh_connectivity(hosts, ssh_key=key, user=user)

    if failed:
        print("\n[WARNING] Could not connect to the following hosts:")
        for h in failed:
            print(f" - {h}")
        cont = input("\nContinue anyway? (y/N): ").strip().lower()
        if cont != "y":
            print("[INFO] Aborting run.")
            return

    if "prod" in inventory.lower():
        confirm = input("[WARNING] You are about to run against PROD. Type 'PROD' to continue: ")
        if confirm != "PROD":
            print("[INFO] Aborted.")
            return

    cmd = ["ansible-playbook", "-i", str(inventory_path), playbook]
    subprocess.run(cmd)

def run_custom_command(inventory, command):
    inventory_path = LOCAL_REPO_PATH / "inventories" / inventory / "hosts"
    hosts = get_hosts_from_inventory(inventory_path)

    user, key = get_ansible_config()
    print(f"[INFO] Checking SSH connectivity to {len(hosts)} hosts...")
    failed = check_ssh_connectivity(hosts, ssh_key=key, user=user)

    if failed:
        print("\n[WARNING] Could not connect to the following hosts:")
        for h in failed:
            print(f" - {h}")
        cont = input("\nContinue anyway? (y/N): ").strip().lower()
        if cont != "y":
            print("[INFO] Aborting run.")
            return

    if "prod" in inventory.lower():
        confirm = input("[WARNING] You are about to run against PROD. Type 'PROD' to continue: ")
        if confirm != "PROD":
            print("[INFO] Aborted.")
            return

    cmd = command.split() + ["-i", str(inventory_path)]
    subprocess.run(cmd)

def manage_custom_commands():
    if not CUSTOM_COMMANDS_FILE.exists():
        CUSTOM_COMMANDS_FILE.touch()
    while True:
        print("\n[Custom Commands Menu]")
        print("1. View saved commands")
        print("2. Add a new command")
        print("3. Back to main menu")
        choice = input("Select an option: ")
        if choice == "1":
            with open(CUSTOM_COMMANDS_FILE, "r") as f:
                cmds = f.readlines()
                for i, c in enumerate(cmds, 1):
                    print(f"{i}. {c.strip()}")
        elif choice == "2":
            new_cmd = input("Enter the full ansible/ansible-playbook command: ")
            with open(CUSTOM_COMMANDS_FILE, "a") as f:
                f.write(new_cmd + "\n")
        elif choice == "3":
            break

def main():
    clone_or_update_repo()

    while True:
        print("\n[Main Menu]")
        print("1. Run Ansible Playbook")
        print("2. Run Custom Command")
        print("3. Manage Custom Commands")
        print("4. Exit")
        choice = input("Select an option: ")

        if choice == "1":
            inventories = list_inventories()
            for i, inv in enumerate(inventories, 1):
                print(f"{i}. {inv}")
            inv_choice = int(input("Select inventory: "))
            inventory = inventories[inv_choice - 1]
            playbook = input("Enter playbook file name (relative to repo): ")
            run_ansible_playbook(inventory, playbook)

        elif choice == "2":
            inventories = list_inventories()
            for i, inv in enumerate(inventories, 1):
                print(f"{i}. {inv}")
            inv_choice = int(input("Select inventory: "))
            inventory = inventories[inv_choice - 1]

            if not CUSTOM_COMMANDS_FILE.exists():
                print("[ERROR] No custom commands saved yet.")
                continue
            with open(CUSTOM_COMMANDS_FILE, "r") as f:
                cmds = f.readlines()
            if not cmds:
                print("[ERROR] No custom commands saved yet.")
                continue
            for i, c in enumerate(cmds, 1):
                print(f"{i}. {c.strip()}")
            cmd_choice = int(input("Select command: "))
            command = cmds[cmd_choice - 1].strip()
            run_custom_command(inventory, command)

        elif choice == "3":
            manage_custom_commands()

        elif choice == "4":
            print("Exiting...")
            sys.exit(0)
        else:
            print("[ERROR] Invalid option.")

if __name__ == "__main__":
    main()
