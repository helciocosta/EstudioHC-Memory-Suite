#!/usr/bin/env python3
"""
EstudioHC Alert System - Contabo Server Version
Monitors Contabo services, memory API, and sends email alerts
"""
import os
import sys
import smtplib
import json
import subprocess
import socket
import ssl
import urllib.request
from datetime import datetime
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from pathlib import Path
from typing import List, Optional, Dict, Any
import logging

# Config paths
CONFIG_FILE = Path.home() / "Apps/EstudioHC-Memory-Suite/config/alerts_contabo.json"
LOG_FILE = Path.home() / "Apps/EstudioHC-Memory-Suite/logs/alerts_contabo.log"

# Setup logging
LOG_FILE.parent.mkdir(parents=True, exist_ok=True)
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(message)s',
    handlers=[
        logging.FileHandler(LOG_FILE),
        logging.StreamHandler(sys.stdout)
    ]
)
logger = logging.getLogger(__name__)

# Default config template for Contabo
DEFAULT_CONFIG = {
    "smtp": {
        "enabled": True,
        "host": "smtp.gmail.com",
        "port": 587,
        "username": "seu-email@gmail.com",
        "password": "sua-senha-de-app",
        "use_tls": True,
        "from_email": "seu-email@gmail.com",
        "from_name": "EstudioHC Contabo Alerts"
    },
    "recipients": {
        "critical": ["helciocosta@gmail.com"],
        "warning": ["helciocosta@gmail.com"],
        "info": []
    },
    "webhook": {
        "enabled": False,
        "url": "",
        "headers": {}
    },
    "thresholds": {
        "memory_percent": 85,
        "disk_percent": 90,
        "cpu_percent": 90,
        "swap_percent": 80,
        "backup_age_hours": 30,
        "sync_age_hours": 12,
        "llama_memory_gb": 10,
        "llama_cpu_percent": 80
    },
    "services_to_monitor": [
        "ollama.service",
        "estudiohc-api.service",
        "estudiohc-dashboard.service",
        "estudiohc-mcp-sse.service",
        "chromadb-mcp.service",
        "estudiohc-backup.timer",
        "estudiohc-monitor.timer",
        "tailscaled.service"
    ]
}


def load_config() -> Dict[str, Any]:
    if CONFIG_FILE.exists():
        try:
            with open(CONFIG_FILE) as f:
                config = json.load(f)
            for key, value in DEFAULT_CONFIG.items():
                if key not in config:
                    config[key] = value
                elif isinstance(value, dict):
                    for subkey, subvalue in value.items():
                        if subkey not in config[key]:
                            config[key][subkey] = subvalue
            return config
        except Exception as e:
            logger.error(f"Failed to load config: {e}, using defaults")
    else:
        CONFIG_FILE.parent.mkdir(parents=True, exist_ok=True)
        with open(CONFIG_FILE, 'w') as f:
            json.dump(DEFAULT_CONFIG, f, indent=2)
        logger.info(f"Created default config at {CONFIG_FILE}")
    return DEFAULT_CONFIG


def save_config(config: Dict[str, Any]) -> None:
    CONFIG_FILE.parent.mkdir(parents=True, exist_ok=True)
    with open(CONFIG_FILE, 'w') as f:
        json.dump(config, f, indent=2)


def send_email(config: Dict, subject: str, body: str, level: str = "info") -> bool:
    smtp_cfg = config.get("smtp", {})
    if not smtp_cfg.get("enabled"):
        return False
    
    recipients = config.get("recipients", {}).get(level, [])
    if not recipients:
        logger.warning(f"No recipients configured for level: {level}")
        return False
    
    try:
        msg = MIMEMultipart()
        msg['From'] = f"{smtp_cfg.get('from_name', 'EstudioHC Contabo')} <{smtp_cfg.get('from_email')}>"
        msg['To'] = ", ".join(recipients)
        msg['Subject'] = f"[EstudioHC-Contabo-{level.upper()}] {subject}"
        
        msg.attach(MIMEText(body, 'plain'))
        
        with smtplib.SMTP(smtp_cfg['host'], smtp_cfg['port']) as server:
            if smtp_cfg.get('use_tls', True):
                server.starttls()
            if smtp_cfg.get('username') and smtp_cfg.get('password'):
                server.login(smtp_cfg['username'], smtp_cfg['password'])
            server.send_message(msg)
        
        logger.info(f"Email sent to {len(recipients)} recipients: {subject}")
        return True
    except Exception as e:
        logger.error(f"Failed to send email: {e}")
        return False


def send_webhook(config: Dict, payload: Dict) -> bool:
    webhook_cfg = config.get("webhook", {})
    if not webhook_cfg.get("enabled") or not webhook_cfg.get("url"):
        return False
    
    try:
        headers = webhook_cfg.get("headers", {})
        headers.setdefault("Content-Type", "application/json")
        
        req = urllib.request.Request(
            webhook_cfg["url"],
            data=json.dumps(payload).encode(),
            headers=headers,
            method="POST"
        )
        
        with urllib.request.urlopen(req, timeout=10) as resp:
            if resp.status < 300:
                logger.info(f"Webhook sent successfully")
                return True
    except Exception as e:
        logger.error(f"Failed to send webhook: {e}")
    return False


def check_systemd_service(service: str) -> Dict[str, Any]:
    try:
        result = subprocess.run(
            ["systemctl", "is-active", service],
            capture_output=True, text=True, timeout=5
        )
        active = result.stdout.strip()
        
        result2 = subprocess.run(
            ["systemctl", "status", service, "--no-pager", "-n", "5"],
            capture_output=True, text=True, timeout=5
        )
        
        return {
            "service": service,
            "active": active,
            "healthy": active == "active",
            "details": result2.stdout.strip() if result2.returncode == 0 else result2.stderr.strip()
        }
    except Exception as e:
        return {
            "service": service,
            "active": "error",
            "healthy": False,
            "details": str(e)
        }


def check_disk_usage(path: str = "/") -> Dict[str, Any]:
    try:
        import shutil
        total, used, free = shutil.disk_usage(path)
        percent = (used / total) * 100
        return {
            "path": path,
            "total_gb": round(total / (1024**3), 2),
            "used_gb": round(used / (1024**3), 2),
            "free_gb": round(free / (1024**3), 2),
            "percent": round(percent, 1),
            "healthy": percent < 90
        }
    except Exception as e:
        return {"error": str(e), "healthy": False}


def check_memory() -> Dict[str, Any]:
    try:
        with open("/proc/meminfo") as f:
            lines = f.readlines()
        meminfo = {}
        for line in lines:
            if ":" in line:
                key, val = line.split(":", 1)
                meminfo[key.strip()] = int(val.strip().split()[0])
        
        total = meminfo.get("MemTotal", 0)
        available = meminfo.get("MemAvailable", 0)
        used = total - available
        percent = (used / total * 100) if total > 0 else 0
        
        swap_total = meminfo.get("SwapTotal", 0)
        swap_free = meminfo.get("SwapFree", 0)
        swap_used = swap_total - swap_free
        swap_percent = (swap_used / swap_total * 100) if swap_total > 0 else 0
        
        return {
            "total_gb": round(total / (1024**2), 2),
            "used_gb": round(used / (1024**2), 2),
            "available_gb": round(available / (1024**2), 2),
            "percent": round(percent, 1),
            "swap_total_gb": round(swap_total / (1024**2), 2),
            "swap_used_gb": round(swap_used / (1024**2), 2),
            "swap_percent": round(swap_percent, 1),
            "healthy": percent < 85 and swap_percent < 80
        }
    except Exception as e:
        return {"error": str(e), "healthy": False}


def check_ollama_services(config: Dict) -> List[Dict]:
    """Check ollama service memory/CPU usage."""
    alerts = []
    thresholds = config.get("thresholds", {})
    max_mem_gb = thresholds.get("llama_memory_gb", 10)
    max_cpu = thresholds.get("llama_cpu_percent", 80)
    
    # Check ollama service
    try:
        pid_result = subprocess.run(
            ["pgrep", "-f", "ollama"],
            capture_output=True, text=True
        )
        
        if not pid_result.stdout.strip():
            alerts.append({
                "level": "critical",
                "type": "llama_down",
                "title": f"Ollama service not running",
                "message": f"No ollama process found",
                "service": "ollama.service",
                "host": socket.gethostname()
            })
        else:
            for pid in pid_result.stdout.strip().split():
                # Get RSS and CPU
                ps_result = subprocess.run(
                    ["ps", "-o", "rss=,pcpu=", "-p", pid],
                    capture_output=True, text=True
                )
                if ps_result.stdout.strip():
                    rss_kb, cpu_pct = ps_result.stdout.strip().split()
                    rss_gb = int(rss_kb) / (1024 * 1024)
                    cpu_pct = float(cpu_pct)
                    
                    if rss_gb > max_mem_gb:
                        alerts.append({
                            "level": "warning",
                            "type": "llama_high_memory",
                            "title": f"Ollama memory high: {rss_gb:.1f}GB",
                            "message": f"Ollama using {rss_gb:.1f}GB RSS (threshold: {max_mem_gb}GB)",
                            "service": "ollama.service",
                            "host": socket.gethostname()
                        })
                    
                    if cpu_pct > max_cpu:
                        alerts.append({
                            "level": "warning",
                            "type": "llama_high_cpu",
                            "title": f"Ollama CPU high: {cpu_pct:.1f}%",
                            "message": f"Ollama using {cpu_pct:.1f}% CPU (threshold: {max_cpu}%)",
                            "service": "ollama.service",
                            "host": socket.gethostname()
                        })
    except Exception as e:
        logger.error(f"Error checking ollama: {e}")
    
    return alerts


def check_backup_age(config: Dict) -> Dict[str, Any]:
    backup_dir = Path.home() / "Apps/EstudioHC-Memory-Suite/backups"
    max_age_hours = config.get("thresholds", {}).get("backup_age_hours", 30)
    
    try:
        backups = list(backup_dir.glob("memory-db.*"))
        if not backups:
            return {"healthy": False, "message": "No backups found", "age_hours": None}
        
        latest = max(backups, key=lambda p: p.stat().st_mtime)
        age_hours = (datetime.now().timestamp() - latest.stat().st_mtime) / 3600
        
        return {
            "healthy": age_hours < max_age_hours,
            "latest_backup": latest.name,
            "age_hours": round(age_hours, 1),
            "max_age_hours": max_age_hours
        }
    except Exception as e:
        return {"error": str(e), "healthy": False}


def check_memory_api_sync(config: Dict) -> Dict[str, Any]:
    """Check if memory API has recent data."""
    try:
        api_key = "7a2f4aed8ce8b4d6d5657686cbae94fb07882d598ae65f55320ca0afe82009b2"
        url = "https://localhost:5050/recall/EstudioHC?limit=1"
        
        req = urllib.request.Request(url, headers={"X-Api-Key": api_key})
        ctx = ssl.create_default_context()
        ctx.check_hostname = False
        ctx.verify_mode = ssl.CERT_NONE
        
        with urllib.request.urlopen(req, context=ctx, timeout=10) as resp:
            data = json.loads(resp.read())
            if data:
                latest_ts = data[0].get("timestamp", "")
                if latest_ts:
                    dt = datetime.fromisoformat(latest_ts.replace("Z", "+00:00"))
                    age_hours = (datetime.now(dt.tzinfo) - dt).total_seconds() / 3600
                    max_age = config.get("thresholds", {}).get("sync_age_hours", 12)
                    return {
                        "healthy": age_hours < max_age,
                        "latest_memory": latest_ts,
                        "age_hours": round(age_hours, 1),
                        "max_age_hours": max_age
                    }
    except Exception as e:
        return {"error": str(e), "healthy": False}
    
    return {"healthy": True, "message": "Could not check sync age"}


def run_health_checks(config: Dict) -> List[Dict]:
    alerts = []
    hostname = socket.gethostname()
    
    # Service checks
    for service in config.get("services_to_monitor", []):
        result = check_systemd_service(service)
        if not result["healthy"]:
            alerts.append({
                "level": "critical",
                "type": "service_down",
                "title": f"Service {service} is {result['active']}",
                "message": f"Service {service} on {hostname} is not active.\nDetails:\n{result['details']}",
                "service": service,
                "host": hostname
            })
    
    # Disk check
    disk = check_disk_usage("/")
    if not disk.get("healthy", True):
        alerts.append({
            "level": "critical",
            "type": "disk_full",
            "title": f"Disk usage critical: {disk.get('percent', 0)}%",
            "message": f"Disk / on {hostname}: {disk.get('used_gb', 0)}/{disk.get('total_gb', 0)} GB ({disk.get('percent', 0)}%)",
            "host": hostname
        })
    
    # Memory check
    mem = check_memory()
    if not mem.get("healthy", True):
        level = "critical" if mem.get("percent", 0) > 90 else "warning"
        alerts.append({
            "level": level,
            "type": "memory_high",
            "title": f"Memory usage high: {mem.get('percent', 0)}%",
            "message": f"RAM: {mem.get('used_gb', 0)}/{mem.get('total_gb', 0)} GB ({mem.get('percent', 0)}%)\nSwap: {mem.get('swap_used_gb', 0)}/{mem.get('swap_total_gb', 0)} GB ({mem.get('swap_percent', 0)}%)",
            "host": hostname
        })
    
    # Ollama services check
    llama_alerts = check_ollama_services(config)
    alerts.extend(llama_alerts)
    
    # Backup check
    backup = check_backup_age(config)
    if not backup.get("healthy", True):
        alerts.append({
            "level": "warning",
            "type": "backup_stale",
            "title": f"Backup older than {backup.get('max_age_hours', 30)} hours",
            "message": f"Latest backup: {backup.get('latest_backup', 'none')} ({backup.get('age_hours', 0)}h ago)",
            "host": hostname
        })
    
    # Memory API sync check
    sync = check_memory_api_sync(config)
    if not sync.get("healthy", True):
        alerts.append({
            "level": "warning",
            "type": "sync_stale",
            "title": f"Memory API sync older than {sync.get('max_age_hours', 12)} hours",
            "message": f"Latest memory sync: {sync.get('latest_memory', 'unknown')} ({sync.get('age_hours', 0)}h ago)",
            "host": hostname
        })
    
    return alerts


def format_alert_email(alert: Dict) -> tuple:
    subject = f"{alert['level'].upper()}: {alert['title']}"
    body = f"""EstudioHC Contabo Alert - {alert['level'].upper()}

Host: {alert.get('host', 'unknown')}
Type: {alert.get('type', 'unknown')}
Time: {datetime.now().isoformat()}

{alert['message']}

---
This is an automated alert from EstudioHC Contabo monitoring system.
"""
    return subject, body


def main():
    import argparse
    parser = argparse.ArgumentParser(description="EstudioHC Contabo Alert System")
    parser.add_argument("--check", action="store_true", help="Run health checks and send alerts")
    parser.add_argument("--config", action="store_true", help="Show config")
    parser.add_argument("--test-email", help="Send test email to address")
    parser.add_argument("--daemon", action="store_true", help="Run as daemon (check every 10 min)")
    args = parser.parse_args()
    
    config = load_config()
    
    if args.config:
        print(f"Config file: {CONFIG_FILE}")
        print(json.dumps(config, indent=2))
        return
    
    if args.test_email:
        config["smtp"]["enabled"] = True
        config["recipients"]["critical"] = [args.test_email]
        subject, body = format_alert_email({
            "level": "info",
            "title": "Test Alert",
            "message": "This is a test email from EstudioHC Contabo Alert System",
            "host": socket.gethostname()
        })
        send_email(config, subject, body, "info")
        print(f"Test email sent to {args.test_email}")
        return
    
    if args.daemon:
        import time
        logger.info("Starting Contabo alert daemon (check every 10 minutes)")
        while True:
            try:
                alerts = run_health_checks(config)
                for alert in alerts:
                    subject, body = format_alert_email(alert)
                    send_email(config, subject, body, alert["level"])
                    send_webhook(config, alert)
                time.sleep(600)  # 10 minutes
            except KeyboardInterrupt:
                break
            except Exception as e:
                logger.error(f"Daemon error: {e}")
                time.sleep(60)
        return
    
    if args.check:
        alerts = run_health_checks(config)
        if alerts:
            for alert in alerts:
                subject, body = format_alert_email(alert)
                send_email(config, subject, body, alert["level"])
                send_webhook(config, alert)
                logger.warning(f"ALERT [{alert['level']}]: {alert['title']}")
        else:
            logger.info("All health checks passed")
        return
    
    print(json.dumps(config, indent=2))


if __name__ == "__main__":
    main()

