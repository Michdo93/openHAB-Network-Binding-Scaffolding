#!/usr/bin/env python3
import re
import sys

def generate_sitemap(things_file="network.things", output_file="network_monitoring.sitemap"):
    print(f"[*] Generating sitemap from {things_file}...")
    try:
        with open(things_file, "r") as f:
            content = f.read()
    except FileNotFoundError:
        print(f"[-] Error: {things_file} not found.")
        return

    devices = set()
    speedtest_found = False

    pattern = re.compile(r'Thing\s+(\S+):(\S+):(\S+)')
    for match in pattern.finditer(content):
        _, t_type, uid = match.groups()
        if t_type == "speedtest":
            speedtest_found = True
            continue
        dev_name = uid.split('_')[0]
        devices.add(dev_name)

    sitemap_content = 'sitemap network_monitoring label="Network Monitoring"\n{\n'
    
    # Devices Frame
    sitemap_content += '    Frame label="Labor Geräte & Dienste" {\n'
    for dev in sorted(devices):
        sitemap_content += f'        Text item=g_{dev} label="{dev.capitalize()} [MAP(en.map):%s]" {{\n'
        sitemap_content += f'            Frame label="Status & Metriken" {{\n'
        sitemap_content += f'                Default item={dev}_online\n'
        sitemap_content += f'                Text item={dev}_latency\n'
        sitemap_content += f'                Text item={dev}_lastseen\n'
        sitemap_content += f'            }}\n'
        sitemap_content += f'            Frame label="Erkannte Dienste"\n'
        # Include service items if they start with dev
        sitemap_content += f'        }}\n'
    sitemap_content += '    }\n\n'

    # Speedtest Frames as requested
    if speedtest_found:
        sitemap_content += '    Frame label="SpeedTest" {\n'
        sitemap_content += '        Text item=Speedtest_Start\n'
        sitemap_content += '        Switch item=Speedtest_Running\n'
        sitemap_content += '        Default item=Speedtest_Progress\n'
        sitemap_content += '        Text item=Speedtest_Running label="Speedtest [%s]" visibility=[Speedtest_Running != "-"]\n'
        sitemap_content += '    }\n\n'
        
        sitemap_content += '    Frame label="Down" {\n'
        sitemap_content += '        Text item=Speedtest_ResultDown\n'
        sitemap_content += '        Chart item=Speedtest_ResultDown period=D refresh=30000 service="influxdb" visibility=[sys_chart_period==0, sys_chart_period=="Non initialisé"]\n'
        sitemap_content += '        Chart item=Speedtest_ResultDown period=W refresh=30000 service="influxdb" visibility=[sys_chart_period==1]\n'
        sitemap_content += '        Chart item=Speedtest_ResultDown period=M refresh=30000 service="influxdb" visibility=[sys_chart_period==2]\n'
        sitemap_content += '        Chart item=Speedtest_ResultDown period=Y refresh=30000 service="influxdb" visibility=[sys_chart_period==3]\n'
        sitemap_content += '    }\n\n'

        sitemap_content += '    Frame label="Up" {\n'
        sitemap_content += '        Text item=Speedtest_ResultUp\n'
        sitemap_content += '        Chart item=Speedtest_ResultUp period=D refresh=30000 service="influxdb" visibility=[sys_chart_period==0, sys_chart_period=="Non initialisé"]\n'
        sitemap_content += '        Chart item=Speedtest_ResultUp period=W refresh=30000 service="influxdb" visibility=[sys_chart_period==1]\n'
        sitemap_content += '        Chart item=Speedtest_ResultUp period=M refresh=30000 service="influxdb" visibility=[sys_chart_period==2]\n'
        sitemap_content += '        Chart item=Speedtest_ResultUp period=Y refresh=30000 service="influxdb" visibility=[sys_chart_period==3]\n'
        sitemap_content += '    }\n'

    sitemap_content += '}\n'

    with open(output_file, "w") as f:
        f.write(sitemap_content)
    print(f"[+] Successfully generated {output_file}")

if __name__ == "__main__":
    generate_sitemap()