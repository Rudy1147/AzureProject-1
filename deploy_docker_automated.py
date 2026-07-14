import subprocess
import os
import sys
from localDiagnostics import run_diagnostics

def run_az_command(command_list):
    """Utility function to safely execute an Azure CLI command array"""
    print(f"Executing: {' '.join(command_list)}")
    try:
        result = subprocess.run(command_list, check=True, text=True, capture_output=True)
        if result.stdout:
            print(result.stdout)
        return result.stdout
    except subprocess.CalledProcessError as e:
        print(f"\n[ERROR] Command failed with return code {e.returncode}!", file=sys.stderr)
        print(f"Details: {e.stderr}", file=sys.stderr)
        sys.exit(1)

def main():
    print("=== Azure SRE DOcker Compose Automated Deployment Pipeline using Python ===")

    # 1. Capture user inputs
    rg_name = input("Enter Resource Group [rg-compute-prod-01]: ").strip() or "rg-compute-prod-01"
    vm_name = input("Enter VM Name [vm-appserver-prod-01]: ").strip() or "vm-appserver-prod-01"
    location = input("Enter Region [canadaeast]: ").strip() or "canadaeast"
    port = "8081"

    print(f"\nConfiguration:")
    print(f"- Resource Group: {rg_name}")
    print(f"- VM Name: {vm_name}")
    print(f"- Location: {location}")
    print(f"- Exposed Port: {port}\n")

    # 2. Create Resource Group
    print("=== 2. Ensuring Resource Group Exists ===")
    create_rg_cmd = ["az", "group", "create", "--name", rg_name, "--location", location, "--output", "table"]
    run_az_command(create_rg_cmd)

    # 3. Create VM 

    check_vm_cmd = ["az", "vm", "list", "-g", rg_name, "--query", f"[?name=='{vm_name}'].name", "-o", "tsv"]
    vm_check_output = run_az_command(check_vm_cmd).strip()

    if not vm_check_output:
        print(f"VM {vm_name} not found. Provisioning now...")
        create_vm_cmd = [
            "az", "vm", "create", 
            "--resource-group", rg_name,
            "--name", vm_name,
            "--image", "Ubuntu2204",
            "--size", "Standard_B2ats_v2",
            "--storage-sku", "Standard_LRS",
            "--boot-diagnostics-storage", "",
            "--admin-username", "azureuser",
            "--generate-ssh-keys",
            "--location", location,
            "--output", "table"
        ]
        run_az_command(create_vm_cmd)
    else:
        print(f"VM {vm_name} already exists")
    
    # 4. Open Port 8081 Inbound
    print("=== 4. Opening NSG Port 8081 Inbound ===")
    create_nsg_cmd = [
        "az", "network", "nsg", "rule", "create",
        "--resource-group", rg_name,
        "--nsg-name", f"{vm_name}NSG",
        "--name", "Allow_8081_Inbound",
        "--priority", "1010",
        "--destination-port-ranges", port,
        "--direction", "Inbound",
        "--access", "Allow",
        "--protocol", "Tcp",
        "--description", "Allow FastAPI web traffic on port 8081",
        "--output", "table"
    ]
    run_az_command(create_nsg_cmd)

    # 5. Read Remote Bootstrap Script from file
    print("=== 5. Reading Remote Bootstrap Script ===")
    script_dir = os.path.dirname(os.path.abspath(__file__))
    source_bootstrap_path = os.path.join(script_dir, "bootstrap_docker_compose.sh")

    if not os.path.exists(source_bootstrap_path):
        print(f"Error, source bootstrap file not found at: {source_bootstrap_path}", file=sys.stderr)
        sys.exit(1)
    print(f"Reading configuration from: {source_bootstrap_path}")

    # 6. Execute Remote Boostrap using Run Command
    print("=== 6. Invoking Azure VM Run-Command (Zero-SSH Deploy) ===")
    run_cmd = [
        "az", "vm", "run-command", "invoke",
        "--command-id", "RunShellScript", 
        "--resource-group", rg_name,
        "--name", vm_name,
        "--scripts", f"@{source_bootstrap_path}",
        "--query", "value[0].message",
        "--output", "table"
    ]
    run_az_command(run_cmd)

    # 8. Resolve and Print Endpoint IP
    print("=== 8. Fetching VM Public IP Endpoint ===")
    get_ip_cmd = [
        "az", "vm", "list-ip-addresses",
        "-g", rg_name,
        "-n", vm_name,
        "--query", "[0].virtualMachine.network.publicIpAddresses[0].ipAddress",
        "-o", "tsv"
    ]
    vm_ip = run_az_command(get_ip_cmd).strip().replace("\r", "")
    print(f"Deployment Complete: API Endpoint - http://{vm_ip}:{port}")

    print("\n=== 9. How to End/Teardown VM (Cost Control) ===")
    print("To temporarily stop the VM and suspend compute billing (deallocate VM):")
    print(f"az vm deallocate --name {vm_name} --resource-group {rg_name} --no-wait")
    print("\nTo permanently delete the VM, disk, networks, and the resource group:")
    print(f"az group delete --name {rg_name} --no-wait --yes")

if __name__ == "__main__":
    main()