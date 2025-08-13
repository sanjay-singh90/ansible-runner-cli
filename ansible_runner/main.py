import os
import subprocess
import yaml
import datetime
from git import Repo
from InquirerPy import inquirer

CONFIG_FILE = os.path.expanduser("~/.ansible_runner_config.yml")
CUSTOM_COMMANDS_FILE = os.path.expanduser("~/.ansible_runner_commands.yml")
RUN_HISTORY_FILE = os.path.expanduser("~/.ansible_runner_history.log")
PROD_KEYWORDS = ["prod", "production"]

def load_config():
    if os.path.exists(CONFIG_FILE):
        with open(CONFIG_FILE, "r") as f:
            return yaml.safe_load(f) or {}
    return {}

def save_config(config):
    with open(CONFIG_FILE, "w") as f:
        yaml.dump(config, f)

def get_repo_path():
    config = load_config()
    if "repo_path" not in config or not os.path.isdir(config["repo_path"]):
        repo_path = inquirer.text(message="Enter full path to your Ansible repo:").execute()
        config["repo_path"] = repo_path
        save_config(config)
    return config["repo_path"]

def update_repo():
    repo_path = get_repo_path()
    print(f"[INFO] Pulling latest changes from Git in {repo_path}...")
    repo = Repo(repo_path)
    repo.remotes.origin.pull()
    print("[INFO] Repo updated.")

def list_inventories():
    path = os.path.join(get_repo_path(), "inventories")
    return sorted([f for f in os.listdir(path) if os.path.isdir(os.path.join(path, f))])

def list_playbooks():
    path = get_repo_path()
    return sorted([f for f in os.listdir(path) if f.endswith(".yml") or f.endswith(".yaml")])

def list_roles():
    path = os.path.join(get_repo_path(), "roles")
    return sorted([f for f in os.listdir(path) if os.path.isdir(os.path.join(path, f))])

def warn_if_prod(inventory):
    if any(keyword in inventory.lower() for keyword in PROD_KEYWORDS):
        confirm = inquirer.text(message=f"[WARNING] Type 'YES' to confirm run against '{inventory.upper()}':").execute()
        if confirm != "YES":
            print("[INFO] Aborted.")
            return False
    return True

def log_run(inventory, command):
    with open(RUN_HISTORY_FILE, "a") as log:
        log.write(f"{datetime.datetime.now()} | {inventory} | {command}\n")

def run_ansible(inventory, command):
    inventory_path = os.path.join(get_repo_path(), "inventories", inventory)
    full_command = f"ansible-playbook -i {inventory_path} {command}"
    print(f"[INFO] Running: {full_command}")
    subprocess.run(full_command, shell=True)
    log_run(inventory, command)

def load_custom_commands():
    if os.path.exists(CUSTOM_COMMANDS_FILE):
        with open(CUSTOM_COMMANDS_FILE, "r") as f:
            return yaml.safe_load(f) or {}
    return {}

def save_custom_commands(commands):
    with open(CUSTOM_COMMANDS_FILE, "w") as f:
        yaml.dump(commands, f)

def choose_inventory():
    return inquirer.select(
        message="Select inventory:",
        choices=list_inventories(),
    ).execute()

def run_from_playbooks():
    inventory = choose_inventory()
    if not warn_if_prod(inventory):
        return
    playbook = inquirer.select(
        message="Select playbook:",
        choices=list_playbooks(),
    ).execute()
    run_ansible(inventory, playbook)

def run_from_roles():
    inventory = choose_inventory()
    if not warn_if_prod(inventory):
        return
    role = inquirer.select(
        message="Select role:",
        choices=list_roles(),
    ).execute()
    run_ansible(inventory, f"-m include_role -a name={role}")

def run_from_custom():
    inventory = choose_inventory()
    if not warn_if_prod(inventory):
        return
    commands = load_custom_commands()
    if not commands:
        print("[INFO] No saved commands. Please add one first.")
        return
    choice = inquirer.select(
        message="Select saved command:",
        choices=[f"{name} -> {cmd}" for name, cmd in commands.items()],
    ).execute()
    cmd = choice.split(" -> ", 1)[1]
    run_ansible(inventory, cmd)

def add_custom_command():
    commands = load_custom_commands()
    name = inquirer.text(message="Enter a name for this custom command:").execute()
    cmd = inquirer.text(message="Enter the ansible command (without inventory):").execute()
    commands[name] = cmd
    save_custom_commands(commands)
    print(f"[INFO] Custom command '{name}' saved.")

def view_run_history():
    if os.path.exists(RUN_HISTORY_FILE):
        with open(RUN_HISTORY_FILE, "r") as log:
            print("\n=== Run History ===")
            print(log.read())
    else:
        print("[INFO] No history found.")
    input("\nPress Enter to return to menu...")

def main_menu():
    while True:
        choice = inquirer.select(
            message="=== Ansible Runner ===",
            choices=[
                "Update repo from Git",
                "Run playbook",
                "Run role",
                "Run from saved custom command",
                "Add custom command",
                "View run history",
                "Exit"
            ],
        ).execute()

        if choice == "Update repo from Git":
            update_repo()
        elif choice == "Run playbook":
            run_from_playbooks()
        elif choice == "Run role":
            run_from_roles()
        elif choice == "Run from saved custom command":
            run_from_custom()
        elif choice == "Add custom command":
            add_custom_command()
        elif choice == "View run history":
            view_run_history()
        elif choice == "Exit":
            break

if __name__ == "__main__":
    main_menu()
