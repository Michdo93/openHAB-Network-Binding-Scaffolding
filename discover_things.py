#!/usr/bin/env python3
import subprocess
import ipaddress
import re
import socket
import sys
import os

def run_cmd(cmd):
    try:
        res = subprocess.run(cmd, shell=True, capture_output=True, text=True, timeout=120)
        return res.stdout.strip()
    except Exception:
        return ""

def sanitize_hostname(name):
    # Convert to lowercase, replace hyphens and dots with underscores, remove invalid chars
    clean = re.sub(r'[^a-zA-Z0-9_-]', '', name).lower()
    clean = clean.replace('-', '_').replace('.', '_')
    if not clean or clean[0].isdigit():
        clean = "host_" + clean
    return clean

def get_mac_address(ip):
    # Try arp table lookup
    arp_out = run_cmd(f"arp -n {ip}")
    match = re.search(r'([0-9a-fA-F]{2}(?::[0-9a-fA-F]{2}){5})', arp_out)
    if match:
        return match.group(1)
    return None

def get_hostname(ip):
    try:
        host, _, _ = socket.gethostbyaddr(ip)
        return host.split('.')[0]
    except Exception:
        return f"ip_{ip.replace('.', '_')}"

def test_port_nc(ip, port):
    res = run_cmd(f"nc -z -w 1 {ip} {port}")
    return "succeeded" in run_cmd(f"nc -v -z -w 1 {ip} {port} 2>&1") or res == "" and subprocess.run(f"nc -z -w 1 {ip} {port}", shell=True).returncode == 0

def classify_port(port):
    mapping = {
        22: "ssh",
        80: "http",
        443: "https",
        1883: "mqtt",
        8080: "http_alt",
        8083: "websockets",
        5000: "flask",
        5985: "winrm",
        5986: "winrm_s",
        445: "smb",
        3389: "rdp"
    }
    return mapping.get(int(port), f"port_{port}")

def discover_network(network_range, output_file="network.things"):
    print(f"[*] Scanning network range: {network_range} for live hosts...")
    nmap_ping = run_cmd(f"nmap -sn {network_range} -oG -")
    
    live_hosts = []
    for line in nmap_ping.splitlines():
        if "Status: Up" in line:
            parts = line.split()
            for p in parts:
                if ipaddress.ip_address(p) rescue: # simple check
                    pass
                try:
                    ipaddress.ip_address(p)
                    live_hosts.append(p)
                except ValueError:
                    continue
                    
    # Fallback if nmap didn't return via grep format
    if not live_hosts:
        print("[*] Fallback: parsing standard nmap host output...")
        nmap_normal = run_cmd(f"nmap -sn {network_range}")
        for line in nmap_normal.splitlines():
            if "Nmap scan report for" in line:
                ip = line.split()[-1].strip("()")
                live_hosts.append(ip)

    print(f"[+] Found {len(live_hosts)} live hosts: {live_hosts}")

    things_content = "// Automatically generated network.things\n\n"
    
    for ip in live_hosts:
        raw_host = get_hostname(ip)
        clean_host = sanitize_hostname(raw_host)
        mac = get_mac_address(ip)
        
        # PingDevice Thing
        mac_param = f', macAddress="{mac}"' if mac else ''
        things_content += f'Thing network:pingdevice:{clean_host} "Ping: {raw_host}" @ "Network" [ hostname="{ip}"{mac_param}, refreshInterval=60000 ]\n'
        
        print(f"[*] Scanning ports for host {ip} ({clean_host})...")
        port_scan = run_cmd(f"nmap -p- --min-rate=1000 -T4 {ip}")
        open_ports = []
        for line in port_scan.splitlines():
            if "/tcp" in line and "open" in line:
                p_num = line.split('/')[0].strip()
                open_ports.append(p_num)
                
        print(f"[+] Open ports on {ip}: {open_ports}")
        
        for p in open_ports:
            service_name = classify_port(p)
            # Check with nc first
            nc_ok = test_port_nc(ip, p)
            if not nc_ok:
                # Fallback to nmap service check if nc fails
                run_cmd(f"nmap -sV -p {p} {ip}")
                
            thing_line = f'Thing network:servicedevice:{clean_host}_{service_name} "Service {service_name.upper()} ({p}) on {raw_host}" @ "Network" [ hostname="{ip}", port={p}, refreshInterval=60000 ]\n'
            
            # If port is standard/recognized, uncommented. Else commented out for manual review.
            if int(p) in [22, 80, 443, 1883, 8080, 8083, 5000, 5985, 3389]:
                things_content += thing_line
            else:
                things_content += f"// UNKNOWN SERVICE / MANUAL REVIEW:\n// {thing_line}"
                
        things_content += "\n"

    # Add Speedtest Thing (Local or general)
    things_content += 'Thing network:speedtest:local "Speedtest" @ "Internet" [ refreshInterval=3600000 ]\n'

    with open(output_file, "w") as f:
        f.write(things_content)
    print(f"[+] Successfully generated {output_file}")

if __name__ == "__main__":
    net = sys.argv[1] if len(sys.argv) > 1 else "192.168.0.0/24"
    discover_network(net)