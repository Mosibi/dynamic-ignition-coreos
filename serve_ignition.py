#!/usr/bin/env python3

import pypureomapi
import json
import uuid
from flask import Flask, request, abort
app = Flask(__name__)

def add_node(node_data, mac):
    config = get_config()

    nodes = config.get('nodes', {})
    nodes[mac] = node_data
    config['nodes'] = nodes

    with open(node_file, 'w') as file:
        json.dump(config, file)

def get_config():
    config = {}

    try:
        config = json.load(open(node_file, "r"))
    except FileNotFoundError:
        print('ERROR: Could not open {}'.format(node_file))
        abort(500, 'Could not open node information file')

    return config

def get_node_data(mac):
    node_data = {}
    
    try:
        nodes = json.load(open(node_file, "r"))
        node_data = nodes['nodes'][mac]
    except FileNotFoundError:
        print('ERROR: Could not open {}'.format(node_file))
        abort(500, 'Could not open node information file')
    except KeyError:
        print('No entry found for {} in {}'.format(mac, node_file))

    return node_data


def get_function(node_data):
    node_function = None
    
    try:
        node_function = node_data['function']
    except KeyError as e:
        print('get_function {}'.format(node_data))

    return node_function

def generate_hostname():
    domainname = 'example.com'
    hostname_prefix = 'node'
    hostname_uuid = str(uuid.uuid4()).replace("-", "")[0:8]

    return '{}-{}.{}'.format(hostname_prefix, hostname_uuid, domainname).lower()

def get_hostname(node_data):
    node_hostname = None
    
    try:
        node_hostname = node_data['hostname']
    except KeyError:
        print('ERROR: No hostname record found')
    
    return node_hostname

def write_boot_file(mac):
    tftpdir = '/var/lib/tftpboot/pxelinux.cfg'
    filename = '01-{}'.format(mac.replace(':', '-'))

    fullpath = '{}/{}'.format(tftpdir, filename)

    file = open(fullpath,"w") 

    file.write("UI menu.c32\n")
    file.write("\n")
    file.write("LABEL localdisk\n")
    file.write("  MENU LABEL Boot from local disk\n")
    file.write("  MENU DEFAULT\n")
    file.write("  LOCALBOOT 0\n")
    file.write("  TIMEOUT 50\n")

    file.close() 


def generate_ignition(node_hostname, node_function):
    config = {}
    config_file = '/var/www/fedora-coreos-metal/config.ign'
    
    try:
        config = json.load(open(config_file, "r"))
        storage = config.get('storage', {})
        files = storage.get('files', [])
        files.append(
            {
                "path": "/etc/hostname", 
                "mode": 420,
                "overwrite": True,
                "contents": { "source": "data:,{}".format(node_hostname) }
            }
        )
        
        storage['files'] = files
        config['storage'] = storage
    except FileNotFoundError:
        print('ERROR: Could not open {}'.format(config_file))
        abort(500, 'Could not open ignition config file for node function {}'.format(node_function))
    
    return config

@app.route('/')
def app_root():
    return "Hello World\n"

@app.route('/get_ignition')
def app_get_ignition():
#    ip = '172.16.10.100'
    ip = request.remote_addr

    try:
        mac = omapi.lookup_mac(ip)
    except pypureomapi.OmapiErrorAttributeNotFound:
        print('No DHCP entry found for ip address {}\n'.format(ip))
        return {}
    except pypureomapi.OmapiErrorNotFound:
        print('No DHCP entry found for ip address {}\n'.format(ip))
        return {}

    node_data = get_node_data(mac)

    if len(node_data) == 0:
        print('New node found with mac address {}'.format(mac))
        node_hostname = generate_hostname()
        node_data = {'function': None, 'hostname': node_hostname}
        add_node(node_data, mac)
        write_boot_file(mac)

    node_function = get_function(node_data)
    node_hostname = get_hostname(node_data)
    
    print('ip address {}, mac address {}, node function {}, hostname {}\n'.format(ip, mac, node_function, node_hostname))

    ignition = generate_ignition(node_hostname, node_function)
    return ignition

if __name__ == '__main__':
    KEYNAME=b"defomapi"
    BASE64_ENCODED_KEY=b"s0nIEoYP74zdh9OuPXcW0A=="

    node_file = "nodes.json"
    
    dhcp_server_ip="127.0.0.1"
    port = 7911 # Port of the omapi service

    omapi = pypureomapi.Omapi(dhcp_server_ip, port, KEYNAME, BASE64_ENCODED_KEY)

    app.run(host='0.0.0.0')
