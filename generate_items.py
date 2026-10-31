#!/usr/bin/env python3
import re
import sys

def generate_items(things_file="network.things", output_file="network.items"):
    print(f"[*] Reading things from {things_file}...")
    try:
        with open(things_file, "r") as f:
            content = f.read()
    except FileNotFoundError:
        print(f"[-] Error: {things_file} not found.")
        return

    items_content = "// Automatically generated network.items\n\n"
    
    # Track devices to create groups
    devices = {}
    speedtest_found = False

    # Regex to match Thing definitions
    # Format: Thing binding:type:UID "Label" @ "Location" [...]
    pattern = re.compile(r'Thing\s+(\S+):(\S+):(\S+)\s+"([^"]+)"')
    
    for match in pattern.finditer(content):
        b_type, t_type, uid, label = match.groups()
        
        if t_type == "speedtest":
            speedtest_found = True
            continue
            
        parts = uid.split('_')
        dev_name = parts[0]
        
        if dev_name not in devices:
            devices[dev_name] = {
                "label": label.split(":")[-1].strip(),
                "things": []
            }
        devices[dev_name]["things"].append((t_type, uid, label))

    # Build Group and Items per device
    for dev, data in devices.items():
        group_label = f"Device: {dev.capitalize()}"
        items_content += f'Group g_{dev} "{group_label}" <computer> (Network)\n'
        
        for t_type, uid, label in data["things"]:
            if t_type == "pingdevice":
                items_content += f'Switch    {uid}_online       "Online Status [%s]"        <switch>    (g_{dev})  {{ channel="network:pingdevice:{uid}:online" }}\n'
                items_content += f'Number:Time {uid}_latency     "Ping Latenz [%.1f ms]"     <time>      (g_{dev})  {{ channel="network:pingdevice:{uid}:latency" }}\n'
                items_content += f'DateTime  {uid}_lastseen    "Zuletzt gesehen [%1$tH:%1$tM]" <time>    (g_{dev})  {{ channel="network:pingdevice:{uid}:lastseen" }}\n'
            elif t_type == "servicedevice":
                items_content += f'Switch    {uid}_open        "Service Open [%s]"         <shield>    (g_{dev})  {{ channel="network:servicedevice:{uid}:open" }}\n'
                items_content += f'Number:Time {uid}_time        "Connect Zeit [%.1f ms]"    <time>      (g_{dev})  {{ channel="network:servicedevice:{uid}:time" }}\n'
        
        items_content += "\n"

    # Speedtest items if present
    if speedtest_found:
        items_content += '// Speedtest Items\n'
        items_content += 'Group gSpeedtest "Speedtest" <speedtest> (Network)\n'
        items_content += 'Switch    Speedtest_Start         "Speedtest starten"             <play>      (gSpeedtest) { channel="network:speedtest:local:run" }\n'
        items_content += 'Switch    Speedtest_Running       "Speedtest läuft [%s]"          <activity>  (gSpeedtest) { channel="network:speedtest:local:running" }\n'
        items_content += 'Number    Speedtest_Progress      "Fortschritt [%d %%]"           <climate>   (gSpeedtest) { channel="network:speedtest:local:progress" }\n'
        items_content += 'Number:DataRate Speedtest_ResultDown  "Download [%.2f Mbit/s]"    <download>  (gSpeedtest) { channel="network:speedtest:local:download" }\n'
        items_content += 'Number:DataRate Speedtest_ResultUp    "Upload [%.2f Mbit/s]"      <upload>    (gSpeedtest) { channel="network:speedtest:local:upload" }\n'
        items_content += 'Number:Time     Speedtest_Ping      "Ping [%.1f ms]"            <time>      (gSpeedtest) { channel="network:speedtest:local:ping" }\n'

    with open(output_file, "w") as f:
        f.write(items_content)
    print(f"[+] Successfully generated {output_file}")

if __name__ == "__main__":
    generate_items()