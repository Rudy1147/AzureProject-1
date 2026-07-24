import subprocess
import os
import sys

def run_az_command(command_list):
    """Utility function to safely execute an Azure CLI command array"""
    print(f"Executing: {' '.join(command_list)}")
    try:
        # Edited to include encoding and errors parameters to handle potential encoding issues
        result = subprocess.run(command_list, check=True, text=True, capture_output=True, encoding="utf-8", errors="replace",)
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
    # Added new variables for VNet, Subnet, Workspace, DCR, and NSG names
    vnet_name = f"{vm_name}-vnet"
    subnet_name = "backend-subnet"
    nsg_name = f"{vm_name}-nsg"
    workspace_name = f"{vm_name}-logs"
    dcr_name = f"{vm_name}-dcr"


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

        # This is part of Requirement 2
        print("=== 3. Creating Virtual Network ===")

        create_vnet_cmd = [
            "az", "network", "vnet", "create",
            "--resource-group", rg_name,
            "--name", vnet_name,
            "--location", location,
            "--address-prefix", "10.0.0.0/16",
            "--subnet-name", subnet_name,
            "--subnet-prefix", "10.0.1.0/24",
            "--output", "table"
        ]
        run_az_command(create_vnet_cmd)

        create_nsg_cmd = [
            "az", "network", "nsg", "create",
            "--resource-group", rg_name,
            "--name", nsg_name,
            "--location", location,
            "--output", "table"
        ]
        run_az_command(create_nsg_cmd)


        create_vm_cmd = [
            "az", "vm", "create", 
            "--resource-group", rg_name,
            "--name", vm_name,
            "--image", "Ubuntu2204",
            "--size", "Standard_B2ats_v2",
            "--storage-sku", "Standard_LRS",
            "--boot-diagnostics-storage", "",
            "--vnet-name", vnet_name,
            "--subnet", subnet_name,
            "--nsg", nsg_name,
            "--admin-username", "azureuser",
            "--generate-ssh-keys",
            "--location", location,
            "--output", "table"
        ]
        run_az_command(create_vm_cmd)
    else:
        print(f"VM {vm_name} already exists")
    # Moved script_dir to avoid redundancy
    script_dir = os.path.dirname(os.path.abspath(__file__))

    # 3.1 Assign Managed Identity to the VM
    # Very important to make dcr work.
    assign_identity_cmd = [
        "az", "vm", "identity", "assign",
        "--resource-group", rg_name,
        "--name", vm_name
    ]
    run_az_command(assign_identity_cmd)

    # ---------------------------------------------------------------------------------------------------
    # Added for Requirement 3: Create Log Analytics Workspace and DCR, and install Azure Monitor Agent
    print("=== Creating Log Analytics Workspace ===")
    create_workspace_cmd = [
        "az", "monitor", "log-analytics", "workspace", "create",
        "--resource-group", rg_name,
        "--workspace-name", workspace_name,
        "--location", location,
        "--output", "table"
    ]
    run_az_command(create_workspace_cmd)

    # Retrieve the Workspace ID for later use in the DCR creation
    workspace_id_cmd = [
        "az", "monitor", "log-analytics", "workspace", "show",
        "--resource-group", rg_name,
        "--workspace-name", workspace_name,
        "--query", "id", "-o", "tsv"
    ]
    workspace_id = run_az_command(workspace_id_cmd).strip()

    # Install Azure Monitor Agent on the VM
    print("=== Installing Azure Monitor Agent ===")
    A_Monitor_Agent_cmd = [
        "az", "vm", "extension", "set",
        "--resource-group", rg_name,
        "--vm-name", vm_name,
        "--publisher", "Microsoft.Azure.Monitor",
        "--name", "AzureMonitorLinuxAgent"
    ]
    run_az_command(A_Monitor_Agent_cmd)

    print("=== Creating Data Collection Rule ===")
    # Create Data Collection Rule (DCR) to collect custom container log files
    # -------------------------------------------------------------------
    # This code snippet reads the DCR template file, replaces placeholders with actual values, and writes the modified content to a new DCR file.
    dcr_file = "dcr.json"
    template_file = "dcr_template.json"
    with open(template_file, "r") as f:
        dcr_contents = f.read()
    dcr_contents = dcr_contents.replace("__WORKSPACE_ID__", workspace_id).replace("__LOCATION__", location)
    with open(dcr_file, "w") as f:
        f.write(dcr_contents)
    # -------------------------------------------------------------------
    create_dcr_cmd = [
        "az", "monitor", "data-collection", "rule", "create",
        "--resource-group", rg_name,
        "--name", dcr_name,
        "--location", location,
        "--rule-file", dcr_file
    ]
    run_az_command(create_dcr_cmd)

    # Retrieve the DCR ID for later use in the Run Command script
    print("=== Retrieving DCR ID ===")
    dcr_id_cmd = [
        "az", "monitor", "data-collection", "rule", "show",
        "--resource-group", rg_name,
        "--name", dcr_name,
        "--query", "id", "-o", "tsv"
    ]
    dcr_id = run_az_command(dcr_id_cmd).strip()

    # Retrieve the VM Resource ID for later use in the Run Command script
    print("=== Retrieving VM Resource ID ===")
    vm_id_cmd = [
        "az", "vm", "show",
        "--resource-group", rg_name,
        "--name", vm_name,
        "--query", "id", "-o", "tsv"
    ]
    vm_id = run_az_command(vm_id_cmd).strip()

    # Associate the VM with the Data Collection Rule (DCR) to collect custom container log files
    print("=== Associating VM with Data Collection Rule ===")
    associate_cmd = [
        "az", "monitor", "data-collection", "rule", "association", "create",
        "--association-name", "default",
        "--rule-id", dcr_id,
        "--resource", vm_id
    ]
    run_az_command(associate_cmd)

    # Verify the association of the VM with the Data Collection Rule (DCR)
    print("=== Verifying DCR Association ===")
    verify_cmd = [
        "az", "monitor", "data-collection", "rule", "association", "list",
        "--resource", vm_id,
        "--output", "table"
    ]
    run_az_command(verify_cmd)

    # ----------------------------------------------------------------------------------------------------
    
    # 4. Open Port 8081 Inbound
    print("=== 4. Opening NSG Port 8081 Inbound ===")
    create_nsg_cmd = [
        "az", "network", "nsg", "rule", "create",
        "--resource-group", rg_name,
        "--nsg-name", nsg_name,
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
    print("\nAzure Monitor Configuration")
    print(f"Log Analytics Workspace: {workspace_name}")
    print(f"Data Collection Rule: {dcr_name}")
    print("Container logs are being forwarded to Azure Monitor.")

    print("\n=== 9. How to End/Teardown VM (Cost Control) ===")
    print("To temporarily stop the VM and suspend compute billing (deallocate VM):")
    print(f"az vm deallocate --name {vm_name} --resource-group {rg_name} --no-wait")
    print("\nTo permanently delete the VM, disk, networks, and the resource group:")
    print(f"az group delete --name {rg_name} --no-wait --yes")

if __name__ == "__main__":
    main()