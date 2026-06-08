#!/usr/bin/env python3
"""
The Forensics Briefing - Terminal User Interface Cybersecurity Game
A production-ready, educational forensics investigation game
Author: Staff Software Engineer & Lead Cyber Security Architect
Version: 1.0.0
"""

import json
import hashlib
import time
from datetime import datetime, timedelta
from pathlib import Path
import random
import re
import base64
from typing import Dict, List, Optional, Any, Tuple
from dataclasses import dataclass, field, asdict
from enum import Enum

from textual import on
from textual.app import App, ComposeResult
from textual.containers import Container, Horizontal, Vertical, ScrollableContainer
from textual.widgets import Header, Footer, Static, Input, Button, DataTable, Label
from textual.widgets import ListView, ListItem, RichLog, Placeholder
from textual.screen import Screen, ModalScreen
from textual.reactive import reactive
from textual.message import Message
from textual.binding import Binding
from textual.worker import Worker, get_current_worker

# ================== Data Models & Enums ==================

class Difficulty(Enum):
    """Difficulty levels for chapters"""
    BEGINNER = "BEGINNER"
    INTERMEDIATE = "INTERMEDIATE"
    ADVANCED = "ADVANCED"
    EXPERT = "EXPERT"

class ThreatLevel(Enum):
    """Threat levels for security indicators"""
    SAFE = "SAFE"
    SUSPICIOUS = "SUSPICIOUS"
    MALICIOUS = "MALICIOUS"

@dataclass
class GameState:
    """Persistent game state structure"""
    tutorial_completed: bool = False
    highest_chapter_unlocked: int = 1
    total_score: int = 0
    tools_unlocked: Dict[str, bool] = field(default_factory=lambda: {
        "virustotal": False,
        "siem": False,
        "regex": False
    })
    achievements: List[str] = field(default_factory=list)
    high_scores: List[Dict[str, Any]] = field(default_factory=list)

@dataclass
class ChapterConfig:
    """Configuration for each chapter"""
    number: int
    title: str
    bulletin: str
    difficulty: Difficulty
    vulnerability_keyword: str
    target_port: int
    validation_hash: str
    time_limit: int  # seconds
    log_count: int
    malicious_ip_count: int
    
# ================== Chapter Configurations ==================

CHAPTERS = [
    ChapterConfig(
        number=1,
        title="OPERATION GHOST_IN_THE_FINGER",
        bulletin="An attacker has breached an old web server using a Linux command vulnerability. They are spawning rogue terminal channels to steal internal data. Your goal is to inspect the logs, find the external server managing this attack, look for clues hidden in the server's code, and decode the exploit name.",
        difficulty=Difficulty.BEGINNER,
        vulnerability_keyword="shellshock",
        target_port=80,
        validation_hash=hashlib.sha256(b"shellshock_bash_cve_2014_6271").hexdigest(),
        time_limit=600,  # 10 minutes
        log_count=15,
        malicious_ip_count=1
    ),
    ChapterConfig(
        number=2,
        title="OPERATION CORRUPTED_HEART",
        bulletin="Employees are opening a fake corporate email attachment that dropped a stealthy banking trojan onto our mail server. We need you to identify the malicious sender infrastructure, track down the active attack platform, and decode the name of this notorious malware family.",
        difficulty=Difficulty.BEGINNER,
        vulnerability_keyword="emotet",
        target_port=25,
        validation_hash=hashlib.sha256(b"emotet_trojan_banking").hexdigest(),
        time_limit=600,
        log_count=18,
        malicious_ip_count=1
    ),
    ChapterConfig(
        number=3,
        title="OPERATION OLYMPIC_GAMES",
        bulletin="Industrial telemetry reports indicate mechanical synchronization degradation within specialized infrastructure systems. Physical sensor registers show severe speed variances. Isolate rogue controller logic override packets.",
        difficulty=Difficulty.INTERMEDIATE,
        vulnerability_keyword="stuxnet",
        target_port=502,  # Modbus port
        validation_hash=hashlib.sha256(b"stuxnet_plc_natanz").hexdigest(),
        time_limit=420,  # 7 minutes
        log_count=20,
        malicious_ip_count=2
    ),
    ChapterConfig(
        number=4,
        title="OPERATION GOLDEN_TICKET",
        bulletin="Unauthorized adversary achieved domain administrative privilege inheritance across subnets without raising standard access tokens. Memory dump registers imply cleartext volatility. Hunt for credential extraction methodology.",
        difficulty=Difficulty.ADVANCED,
        vulnerability_keyword="mimikatz",
        target_port=88,  # Kerberos
        validation_hash=hashlib.sha256(b"mimikatz_kerberos_pth").hexdigest(),
        time_limit=420,
        log_count=25,
        malicious_ip_count=3
    ),
    ChapterConfig(
        number=5,
        title="OPERATION BLUE_SHIELD",
        bulletin="Automated file system locking mechanisms deploying simultaneously across global system nodes. Exploitations propagating laterally through legacy sharing loops. Locate the hardcoded domain kill-switch hook.",
        difficulty=Difficulty.EXPERT,
        vulnerability_keyword="wannacry",
        target_port=445,  # SMB
        validation_hash=hashlib.sha256(b"wannacry_eternalblue_ms17_010").hexdigest(),
        time_limit=300,  # 5 minutes
        log_count=30,
        malicious_ip_count=3
    )
]

# ================== Save/Load Functions ==================

SAVE_FILE = Path("save_file.json")

def load_game() -> GameState:
    """Load game state from file or create new if doesn't exist"""
    if SAVE_FILE.exists():
        try:
            with open(SAVE_FILE, 'r') as f:
                data = json.load(f)
                return GameState(**data)
        except (json.JSONDecodeError, TypeError):
            # Corrupted save file, create new
            pass
    
    # Create new save
    state = GameState()
    save_game(state)
    return state

def save_game(state: GameState) -> None:
    """Save game state to file"""
    with open(SAVE_FILE, 'w') as f:
        json.dump(asdict(state), f, indent=2)

# ================== Log Generation ==================

class LogGenerator:
    """Generates realistic network traffic logs"""
    
    BENIGN_DOMAINS = [
        "google.com", "microsoft.com", "amazon.com", "cloudflare.com",
        "github.com", "stackoverflow.com", "wikipedia.org", "office365.com"
    ]
    
    SUSPICIOUS_DOMAINS = [
        "temp-analytics.tk", "secure-update.ml", "system-check.ga",
        "windows-defender.cf", "chrome-extension.tk"
    ]
    
    USER_AGENTS = [
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) Chrome/91.0.4472.124",
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) Safari/605.1.15",
        "Mozilla/5.0 (X11; Linux x86_64) Firefox/89.0",
        "python-requests/2.25.1",
        "curl/7.68.0"
    ]
    
    @staticmethod
    def generate_ip(malicious: bool = False) -> str:
        """Generate a realistic IP address"""
        if malicious:
            # Generate suspicious IP ranges
            prefixes = ["185.220", "195.123", "162.247", "104.248"]
            prefix = random.choice(prefixes)
            return f"{prefix}.{random.randint(1, 254)}.{random.randint(1, 254)}"
        else:
            # Generate local/common IP ranges
            ranges = [
                (192, 168, random.randint(1, 10)),
                (10, 0, random.randint(1, 10)),
                (172, 16, random.randint(1, 10))
            ]
            r = random.choice(ranges)
            return f"{r[0]}.{r[1]}.{r[2]}.{random.randint(1, 254)}"
    
    @staticmethod
    def generate_logs(config: ChapterConfig) -> Tuple[List[Dict], List[str]]:
        """Generate logs for a chapter and return logs + malicious IPs"""
        logs = []
        malicious_ips = []
        
        # Generate malicious IPs
        for _ in range(config.malicious_ip_count):
            ip = LogGenerator.generate_ip(malicious=True)
            malicious_ips.append(ip)
        
        # Generate timestamp base
        base_time = datetime.now() - timedelta(minutes=30)
        
        # Generate logs
        for i in range(config.log_count):
            timestamp = base_time + timedelta(seconds=i * 60)
            
            # Determine if this log should be malicious
            is_malicious = i < config.malicious_ip_count * 3 and random.random() < 0.3
            
            if is_malicious and malicious_ips:
                src_ip = random.choice(malicious_ips)
                dst_port = config.target_port if random.random() < 0.5 else random.choice([443, 80, 22, 3389])
                protocol = "TCP"
                size = random.randint(5000, 50000)  # Larger sizes for exfiltration
                action = "ALERT" if random.random() < 0.7 else "ALLOW"
                domain = random.choice(LogGenerator.SUSPICIOUS_DOMAINS)
            else:
                src_ip = LogGenerator.generate_ip(malicious=False)
                dst_port = random.choice([80, 443, 22, 53, 445, 3389])
                protocol = random.choice(["TCP", "UDP", "ICMP"])
                size = random.randint(100, 5000)
                action = "ALLOW"
                domain = random.choice(LogGenerator.BENIGN_DOMAINS)
            
            log_entry = {
                "timestamp": timestamp.strftime("%Y-%m-%d %H:%M:%S"),
                "src_ip": src_ip,
                "dst_ip": LogGenerator.generate_ip(malicious=False),
                "src_port": random.randint(1024, 65535),
                "dst_port": dst_port,
                "protocol": protocol,
                "size": size,
                "action": action,
                "user_agent": random.choice(LogGenerator.USER_AGENTS),
                "domain": domain
            }
            
            logs.append(log_entry)
        
        # Shuffle logs
        random.shuffle(logs)
        
        return logs, malicious_ips

# ================== Forensic Tools Implementation ==================

class ForensicTools:
    """Implementation of forensic analysis tools"""
    
    @staticmethod
    def inspect_ip(ip: str, malicious_ips: List[str], keyword: str) -> Tuple[bool, str]:
        """Inspect an IP address - returns (is_trap, content)"""
        if ip in malicious_ips:
            return True, "TRAP: Direct connection to C2 server detected!"
        else:
            # Generate mock webpage with hidden keyword
            content = f"""
            <!DOCTYPE html>
            <html>
            <head><title>Corporate Portal</title></head>
            <body>
                <h1>Welcome to Internal Resources</h1>
                <p>Lorem ipsum dolor sit amet, consectetur adipiscing elit.</p>
                <p>System maintenance scheduled for next week.</p>
                <!-- Debug: {keyword.upper()} vulnerability assessment pending -->
                <p>Please update your credentials regularly.</p>
                <footer>© 2024 Corporate IT Department</footer>
            </body>
            </html>
            """
            return False, content
    
    @staticmethod
    def vtscan(target: str, malicious_ips: List[str]) -> Dict[str, Any]:
        """Simulate VirusTotal scan results"""
        is_malicious = target in malicious_ips
        
        if is_malicious:
            return {
                "threat_score": random.randint(75, 95),
                "detection_ratio": f"{random.randint(45, 65)}/70",
                "threat_level": ThreatLevel.MALICIOUS,
                "malware_families": ["Emotet", "TrickBot", "Cobalt Strike"],
                "geo_location": random.choice(["Russia", "China", "North Korea", "Unknown"]),
                "asn": f"AS{random.randint(10000, 99999)}",
                "first_seen": "2023-01-15",
                "ssl_cert": "Self-signed",
                "reputation": "MALICIOUS"
            }
        else:
            return {
                "threat_score": random.randint(0, 25),
                "detection_ratio": "0/70",
                "threat_level": ThreatLevel.SAFE,
                "malware_families": [],
                "geo_location": random.choice(["United States", "Germany", "United Kingdom"]),
                "asn": f"AS{random.randint(1000, 9999)}",
                "first_seen": "2020-06-10",
                "ssl_cert": "Valid",
                "reputation": "CLEAN"
            }
    
    @staticmethod
    def decode_string(encoded: str, expected: str) -> bool:
        """Check if decoded string matches expected vulnerability keyword"""
        decoded = encoded.lower().strip()
        expected = expected.lower().strip()
        
        # Accept multiple formats
        variations = [
            expected,
            expected.replace("_", ""),
            expected.replace("-", ""),
            expected.upper(),
            expected.capitalize()
        ]
        
        return decoded in variations

# ================== Tutorial Screen ==================

class TutorialScreen(Screen):
    """Interactive tutorial for new players"""
    
    CSS = """
    TutorialScreen {
        align: center middle;
    }
    
    .tutorial-container {
        width: 80%;
        height: 80%;
        border: thick $primary;
        padding: 2;
    }
    
    .tutorial-title {
        text-align: center;
        text-style: bold;
        color: $success;
        margin-bottom: 1;
    }
    
    .tutorial-content {
        height: 60%;
        border: solid $primary;
        padding: 1;
        margin: 1;
    }
    
    .tutorial-commands {
        height: 20%;
        border: solid $secondary;
        padding: 1;
        margin: 1;
    }
    
    .tutorial-input {
        dock: bottom;
        height: 3;
        margin: 1;
    }
    """
    
    def __init__(self, game_state: GameState):
        super().__init__()
        self.game_state = game_state
        self.current_module = 1
        self.max_modules = 4
        
    def compose(self) -> ComposeResult:
        yield Header(show_clock=True)
        
        with Container(classes="tutorial-container"):
            yield Static("🎓 SANDBOX TRAINING ENVIRONMENT 🎓", classes="tutorial-title")
            yield Static(self.get_module_content(), classes="tutorial-content", id="content")
            yield Static(self.get_available_commands(), classes="tutorial-commands", id="commands")
            yield Input(placeholder="Enter command...", classes="tutorial-input", id="tutorial-input")
            
        yield Footer()
    
    def get_module_content(self) -> str:
        """Get content for current tutorial module"""
        modules = {
            1: """MODULE 1: BASIC COMMANDS
            
Welcome to The Forensics Briefing training environment!

You've detected suspicious network activity. Let's learn the basic investigation tools:

Sample Logs:
[2024-01-15 10:23:45] 192.168.1.100 -> 10.0.0.5:443 (HTTPS) [1024 bytes]
[2024-01-15 10:23:46] 185.220.101.45 -> 192.168.1.100:445 (SMB) [ALERT]
[2024-01-15 10:23:47] 192.168.1.100 -> 8.8.8.8:53 (DNS) [256 bytes]

Try: inspect 192.168.1.100
Try: decode shellshock""",
            
            2: """MODULE 2: VIRUSTOTAL SCANNER

Excellent! Now let's learn about threat intelligence scanning.

The 'vtscan' command queries threat databases to identify malicious indicators:
- Green (0-30): Safe
- Yellow (31-70): Suspicious  
- Red (71-100): Malicious

New suspicious IP detected: 185.220.101.45

Try: vtscan 185.220.101.45""",
            
            3: """MODULE 3: SIEM FILTERING

Great work! Now let's filter the noise from our logs.

The 'filter' command helps you focus on specific traffic patterns:
- filter port=445 (Show only SMB traffic)
- filter action=ALERT (Show only alerts)
- filter size>1000 (Show large transfers)

Try: filter port=445
Try: filter action=ALERT""",
            
            4: """MODULE 4: PATTERN MATCHING

Almost done! Let's learn about pattern searching.

The 'search' command finds specific patterns in logs:
- search suspicious_ports (Find known bad ports)
- search data_exfil (Find large outbound transfers)
- search encoded (Find encoded strings)

Try: search suspicious_ports

After this module, you'll be ready for real investigations!"""
        }
        
        return modules.get(self.current_module, "Module complete!")
    
    def get_available_commands(self) -> str:
        """Get available commands for current module"""
        commands = {
            1: "Available: inspect <IP> | decode <string> | help",
            2: "Available: inspect | decode | vtscan <target> | help",
            3: "Available: inspect | decode | vtscan | filter <expression> | help",
            4: "Available: ALL COMMANDS UNLOCKED | Type 'help' for full list"
        }
        
        return f"📋 {commands.get(self.current_module, 'All commands available')}"
    
    @on(Input.Submitted)
    async def handle_command(self, event: Input.Submitted) -> None:
        """Process tutorial commands"""
        command = event.value.strip().lower()
        input_widget = self.query_one("#tutorial-input", Input)
        input_widget.clear()
        
        content_widget = self.query_one("#content", Static)
        
        # Process commands based on current module
        if command.startswith("inspect"):
            if self.current_module >= 1:
                content_widget.update("✅ Good! You inspected an IP. In real scenarios, be careful with malicious IPs!")
                if self.current_module == 1:
                    self.advance_module()
                    
        elif command.startswith("decode"):
            if self.current_module >= 1:
                if "shellshock" in command:
                    content_widget.update("✅ Correct! You decoded the vulnerability keyword!")
                    if self.current_module == 1:
                        self.advance_module()
                        
        elif command.startswith("vtscan"):
            if self.current_module >= 2:
                content_widget.update("✅ Excellent! You scanned for threats. Score: 85/100 - MALICIOUS!")
                if self.current_module == 2:
                    self.advance_module()
                    
        elif command.startswith("filter"):
            if self.current_module >= 3:
                content_widget.update("✅ Perfect! You filtered the logs. Found 3 matching entries.")
                if self.current_module == 3:
                    self.advance_module()
                    
        elif command.startswith("search"):
            if self.current_module >= 4:
                content_widget.update("✅ Outstanding! You mastered pattern searching!")
                await self.complete_tutorial()
                
        elif command == "help":
            content_widget.update(self.get_help_text())
            
        elif command == "skip":
            await self.complete_tutorial()
    
    def advance_module(self) -> None:
        """Advance to next tutorial module"""
        self.current_module += 1
        if self.current_module <= self.max_modules:
            content_widget = self.query_one("#content", Static)
            content_widget.update(self.get_module_content())
            commands_widget = self.query_one("#commands", Static)
            commands_widget.update(self.get_available_commands())
    
    def get_help_text(self) -> str:
        """Get help text for current module"""
        return """📚 HELP MENU
        
inspect <IP> - Examine an IP address for clues
decode <string> - Decode an encrypted string
vtscan <target> - Scan IP/hash/domain for threats
filter <expr> - Filter logs by criteria
search <pattern> - Search for patterns in logs
help - Show this menu
skip - Skip tutorial (not recommended for beginners)"""
    
    async def complete_tutorial(self) -> None:
        """Complete tutorial and unlock tools"""
        self.game_state.tutorial_completed = True
        self.game_state.tools_unlocked = {
            "virustotal": True,
            "siem": True,
            "regex": True
        }
        save_game(self.game_state)
        await self.app.push_screen(DashboardScreen(self.game_state))

#!/usr/bin/env python3
"""
The Forensics Briefing - Terminal User Interface Cybersecurity Game
A production-ready, educational forensics investigation game
Author: Staff Software Engineer & Lead Cyber Security Architect
Version: 1.0.0
"""

import json
import hashlib
import time
from datetime import datetime, timedelta
from pathlib import Path
import random
import re
import base64
from typing import Dict, List, Optional, Any, Tuple
from dataclasses import dataclass, field, asdict
from enum import Enum

from textual import on
from textual.app import App, ComposeResult
from textual.containers import Container, Horizontal, Vertical, ScrollableContainer
from textual.widgets import Header, Footer, Static, Input, Button, DataTable, Label
from textual.widgets import ListView, ListItem, RichLog, Placeholder
from textual.screen import Screen, ModalScreen
from textual.reactive import reactive
from textual.message import Message
from textual.binding import Binding
from textual.worker import Worker, get_current_worker

# ================== Data Models & Enums ==================

class Difficulty(Enum):
    """Difficulty levels for chapters"""
    BEGINNER = "BEGINNER"
    INTERMEDIATE = "INTERMEDIATE"
    ADVANCED = "ADVANCED"
    EXPERT = "EXPERT"

class ThreatLevel(Enum):
    """Threat levels for security indicators"""
    SAFE = "SAFE"
    SUSPICIOUS = "SUSPICIOUS"
    MALICIOUS = "MALICIOUS"

@dataclass
class GameState:
    """Persistent game state structure"""
    tutorial_completed: bool = False
    highest_chapter_unlocked: int = 1
    total_score: int = 0
    tools_unlocked: Dict[str, bool] = field(default_factory=lambda: {
        "virustotal": False,
        "siem": False,
        "regex": False
    })
    achievements: List[str] = field(default_factory=list)
    high_scores: List[Dict[str, Any]] = field(default_factory=list)

@dataclass
class ChapterConfig:
    """Configuration for each chapter"""
    number: int
    title: str
    bulletin: str
    difficulty: Difficulty
    vulnerability_keyword: str
    target_port: int
    validation_hash: str
    time_limit: int  # seconds
    log_count: int
    malicious_ip_count: int
    
# ================== Chapter Configurations ==================

CHAPTERS = [
    ChapterConfig(
        number=1,
        title="OPERATION GHOST_IN_THE_FINGER",
        bulletin="An attacker has breached an old web server using a Linux command vulnerability. They are spawning rogue terminal channels to steal internal data. Your goal is to inspect the logs, find the external server managing this attack, look for clues hidden in the server's code, and decode the exploit name.",
        difficulty=Difficulty.BEGINNER,
        vulnerability_keyword="shellshock",
        target_port=80,
        validation_hash=hashlib.sha256(b"shellshock_bash_cve_2014_6271").hexdigest(),
        time_limit=600,  # 10 minutes
        log_count=15,
        malicious_ip_count=1
    ),
    ChapterConfig(
        number=2,
        title="OPERATION CORRUPTED_HEART",
        bulletin="Employees are opening a fake corporate email attachment that dropped a stealthy banking trojan onto our mail server. We need you to identify the malicious sender infrastructure, track down the active attack platform, and decode the name of this notorious malware family.",
        difficulty=Difficulty.BEGINNER,
        vulnerability_keyword="emotet",
        target_port=25,
        validation_hash=hashlib.sha256(b"emotet_trojan_banking").hexdigest(),
        time_limit=600,
        log_count=18,
        malicious_ip_count=1
    ),
    ChapterConfig(
        number=3,
        title="OPERATION OLYMPIC_GAMES",
        bulletin="Industrial telemetry reports indicate mechanical synchronization degradation within specialized infrastructure systems. Physical sensor registers show severe speed variances. Isolate rogue controller logic override packets.",
        difficulty=Difficulty.INTERMEDIATE,
        vulnerability_keyword="stuxnet",
        target_port=502,  # Modbus port
        validation_hash=hashlib.sha256(b"stuxnet_plc_natanz").hexdigest(),
        time_limit=420,  # 7 minutes
        log_count=20,
        malicious_ip_count=2
    ),
    ChapterConfig(
        number=4,
        title="OPERATION GOLDEN_TICKET",
        bulletin="Unauthorized adversary achieved domain administrative privilege inheritance across subnets without raising standard access tokens. Memory dump registers imply cleartext volatility. Hunt for credential extraction methodology.",
        difficulty=Difficulty.ADVANCED,
        vulnerability_keyword="mimikatz",
        target_port=88,  # Kerberos
        validation_hash=hashlib.sha256(b"mimikatz_kerberos_pth").hexdigest(),
        time_limit=420,
        log_count=25,
        malicious_ip_count=3
    ),
    ChapterConfig(
        number=5,
        title="OPERATION BLUE_SHIELD",
        bulletin="Automated file system locking mechanisms deploying simultaneously across global system nodes. Exploitations propagating laterally through legacy sharing loops. Locate the hardcoded domain kill-switch hook.",
        difficulty=Difficulty.EXPERT,
        vulnerability_keyword="wannacry",
        target_port=445,  # SMB
        validation_hash=hashlib.sha256(b"wannacry_eternalblue_ms17_010").hexdigest(),
        time_limit=300,  # 5 minutes
        log_count=30,
        malicious_ip_count=3
    )
]

# ================== Save/Load Functions ==================

SAVE_FILE = Path("save_file.json")

def load_game() -> GameState:
    """Load game state from file or create new if doesn't exist"""
    if SAVE_FILE.exists():
        try:
            with open(SAVE_FILE, 'r') as f:
                data = json.load(f)
                return GameState(**data)
        except (json.JSONDecodeError, TypeError):
            # Corrupted save file, create new
            pass
    
    # Create new save
    state = GameState()
    save_game(state)
    return state

def save_game(state: GameState) -> None:
    """Save game state to file"""
    with open(SAVE_FILE, 'w') as f:
        json.dump(asdict(state), f, indent=2)

# ================== Log Generation ==================

class LogGenerator:
    """Generates realistic network traffic logs"""
    
    BENIGN_DOMAINS = [
        "google.com", "microsoft.com", "amazon.com", "cloudflare.com",
        "github.com", "stackoverflow.com", "wikipedia.org", "office365.com"
    ]
    
    SUSPICIOUS_DOMAINS = [
        "temp-analytics.tk", "secure-update.ml", "system-check.ga",
        "windows-defender.cf", "chrome-extension.tk"
    ]
    
    USER_AGENTS = [
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) Chrome/91.0.4472.124",
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) Safari/605.1.15",
        "Mozilla/5.0 (X11; Linux x86_64) Firefox/89.0",
        "python-requests/2.25.1",
        "curl/7.68.0"
    ]
    
    @staticmethod
    def generate_ip(malicious: bool = False) -> str:
        """Generate a realistic IP address"""
        if malicious:
            # Generate suspicious IP ranges
            prefixes = ["185.220", "195.123", "162.247", "104.248"]
            prefix = random.choice(prefixes)
            return f"{prefix}.{random.randint(1, 254)}.{random.randint(1, 254)}"
        else:
            # Generate local/common IP ranges
            ranges = [
                (192, 168, random.randint(1, 10)),
                (10, 0, random.randint(1, 10)),
                (172, 16, random.randint(1, 10))
            ]
            r = random.choice(ranges)
            return f"{r[0]}.{r[1]}.{r[2]}.{random.randint(1, 254)}"
    
    @staticmethod
    def generate_logs(config: ChapterConfig) -> Tuple[List[Dict], List[str]]:
        """Generate logs for a chapter and return logs + malicious IPs"""
        logs = []
        malicious_ips = []
        
        # Generate malicious IPs
        for _ in range(config.malicious_ip_count):
            ip = LogGenerator.generate_ip(malicious=True)
            malicious_ips.append(ip)
        
        # Generate timestamp base
        base_time = datetime.now() - timedelta(minutes=30)
        
        # Generate logs
        for i in range(config.log_count):
            timestamp = base_time + timedelta(seconds=i * 60)
            
            # Determine if this log should be malicious
            is_malicious = i < config.malicious_ip_count * 3 and random.random() < 0.3
            
            if is_malicious and malicious_ips:
                src_ip = random.choice(malicious_ips)
                dst_port = config.target_port if random.random() < 0.5 else random.choice([443, 80, 22, 3389])
                protocol = "TCP"
                size = random.randint(5000, 50000)  # Larger sizes for exfiltration
                action = "ALERT" if random.random() < 0.7 else "ALLOW"
                domain = random.choice(LogGenerator.SUSPICIOUS_DOMAINS)
            else:
                src_ip = LogGenerator.generate_ip(malicious=False)
                dst_port = random.choice([80, 443, 22, 53, 445, 3389])
                protocol = random.choice(["TCP", "UDP", "ICMP"])
                size = random.randint(100, 5000)
                action = "ALLOW"
                domain = random.choice(LogGenerator.BENIGN_DOMAINS)
            
            log_entry = {
                "timestamp": timestamp.strftime("%Y-%m-%d %H:%M:%S"),
                "src_ip": src_ip,
                "dst_ip": LogGenerator.generate_ip(malicious=False),
                "src_port": random.randint(1024, 65535),
                "dst_port": dst_port,
                "protocol": protocol,
                "size": size,
                "action": action,
                "user_agent": random.choice(LogGenerator.USER_AGENTS),
                "domain": domain
            }
            
            logs.append(log_entry)
        
        # Shuffle logs
        random.shuffle(logs)
        
        return logs, malicious_ips

# ================== Forensic Tools Implementation ==================

class ForensicTools:
    """Implementation of forensic analysis tools"""
    
    @staticmethod
    def inspect_ip(ip: str, malicious_ips: List[str], keyword: str) -> Tuple[bool, str]:
        """Inspect an IP address - returns (is_trap, content)"""
        if ip in malicious_ips:
            return True, "TRAP: Direct connection to C2 server detected!"
        else:
            # Generate mock webpage with hidden keyword
            content = f"""
            <!DOCTYPE html>
            <html>
            <head><title>Corporate Portal</title></head>
            <body>
                <h1>Welcome to Internal Resources</h1>
                <p>Lorem ipsum dolor sit amet, consectetur adipiscing elit.</p>
                <p>System maintenance scheduled for next week.</p>
                <p>Please update your credentials regularly.</p>
                <footer>© 2024 Corporate IT Department</footer>
            </body>
            </html>
            """
            return False, content
    
    @staticmethod
    def vtscan(target: str, malicious_ips: List[str]) -> Dict[str, Any]:
        """Simulate VirusTotal scan results"""
        is_malicious = target in malicious_ips
        
        if is_malicious:
            return {
                "threat_score": random.randint(75, 95),
                "detection_ratio": f"{random.randint(45, 65)}/70",
                "threat_level": ThreatLevel.MALICIOUS,
                "malware_families": ["Emotet", "TrickBot", "Cobalt Strike"],
                "geo_location": random.choice(["Russia", "China", "North Korea", "Unknown"]),
                "asn": f"AS{random.randint(10000, 99999)}",
                "first_seen": "2023-01-15",
                "ssl_cert": "Self-signed",
                "reputation": "MALICIOUS"
            }
        else:
            return {
                "threat_score": random.randint(0, 25),
                "detection_ratio": "0/70",
                "threat_level": ThreatLevel.SAFE,
                "malware_families": [],
                "geo_location": random.choice(["United States", "Germany", "United Kingdom"]),
                "asn": f"AS{random.randint(1000, 9999)}",
                "first_seen": "2020-06-10",
                "ssl_cert": "Valid",
                "reputation": "CLEAN"
            }
    
    @staticmethod
    def decode_string(encoded: str, expected: str) -> bool:
        """Check if decoded string matches expected vulnerability keyword"""
        decoded = encoded.lower().strip()
        expected = expected.lower().strip()
        
        # Accept multiple formats
        variations = [
            expected,
            expected.replace("_", ""),
            expected.replace("-", ""),
            expected.upper(),
            expected.capitalize()
        ]
        
        return decoded in variations

# ================== Tutorial Screen ==================

class TutorialScreen(Screen):
    """Interactive tutorial for new players"""
    
    CSS = """
    TutorialScreen {
        align: center middle;
    }
    
    .tutorial-container {
        width: 80%;
        height: 80%;
        border: thick $primary;
        padding: 2;
    }
    
    .tutorial-title {
        text-align: center;
        text-style: bold;
        color: $success;
        margin-bottom: 1;
    }
    
    .tutorial-content {
        height: 60%;
        border: solid $primary;
        padding: 1;
        margin: 1;
    }
    
    .tutorial-commands {
        height: 20%;
        border: solid $secondary;
        padding: 1;
        margin: 1;
    }
    
    .tutorial-input {
        dock: bottom;
        height: 3;
        margin: 1;
    }
    """
    
    def __init__(self, game_state: GameState):
        super().__init__()
        self.game_state = game_state
        self.current_module = 1
        self.max_modules = 4
        
    def compose(self) -> ComposeResult:
        yield Header(show_clock=True)
        
        with Container(classes="tutorial-container"):
            yield Static("🎓 SANDBOX TRAINING ENVIRONMENT 🎓", classes="tutorial-title")
            yield Static(self.get_module_content(), classes="tutorial-content", id="content")
            yield Static(self.get_available_commands(), classes="tutorial-commands", id="commands")
            yield Input(placeholder="Enter command...", classes="tutorial-input", id="tutorial-input")
            
        yield Footer()
    
    def get_module_content(self) -> str:
        """Get content for current tutorial module"""
        modules = {
            1: """MODULE 1: BASIC COMMANDS
            
Welcome to The Forensics Briefing training environment!

You've detected suspicious network activity. Let's learn the basic investigation tools:

Sample Logs:
[2024-01-15 10:23:45] 192.168.1.100 -> 10.0.0.5:443 (HTTPS) [1024 bytes]
[2024-01-15 10:23:46] 185.220.101.45 -> 192.168.1.100:445 (SMB) [ALERT]
[2024-01-15 10:23:47] 192.168.1.100 -> 8.8.8.8:53 (DNS) [256 bytes]

Try: inspect 192.168.1.100
Try: decode shellshock""",
            
            2: """MODULE 2: VIRUSTOTAL SCANNER

Excellent! Now let's learn about threat intelligence scanning.

The 'vtscan' command queries threat databases to identify malicious indicators:
- Green (0-30): Safe
- Yellow (31-70): Suspicious  
- Red (71-100): Malicious

New suspicious IP detected: 185.220.101.45

Try: vtscan 185.220.101.45""",
            
            3: """MODULE 3: SIEM FILTERING

Great work! Now let's filter the noise from our logs.

The 'filter' command helps you focus on specific traffic patterns:
- filter port=445 (Show only SMB traffic)
- filter action=ALERT (Show only alerts)
- filter size>1000 (Show large transfers)

Try: filter port=445
Try: filter action=ALERT""",
            
            4: """MODULE 4: PATTERN MATCHING

Almost done! Let's learn about pattern searching.

The 'search' command finds specific patterns in logs:
- search suspicious_ports (Find known bad ports)
- search data_exfil (Find large outbound transfers)
- search encoded (Find encoded strings)

Try: search suspicious_ports

After this module, you'll be ready for real investigations!"""
        }
        
        return modules.get(self.current_module, "Module complete!")
    
    def get_available_commands(self) -> str:
        """Get available commands for current module"""
        commands = {
            1: "Available: inspect <IP> | decode <string> | help",
            2: "Available: inspect | decode | vtscan <target> | help",
            3: "Available: inspect | decode | vtscan | filter <expression> | help",
            4: "Available: ALL COMMANDS UNLOCKED | Type 'help' for full list"
        }
        
        return f"📋 {commands.get(self.current_module, 'All commands available')}"
    
    @on(Input.Submitted)
    async def handle_command(self, event: Input.Submitted) -> None:
        """Process tutorial commands"""
        command = event.value.strip().lower()
        input_widget = self.query_one("#tutorial-input", Input)
        input_widget.clear()
        
        content_widget = self.query_one("#content", Static)
        
        # Process commands based on current module
        if command.startswith("inspect"):
            if self.current_module >= 1:
                content_widget.update("✅ Good! You inspected an IP. In real scenarios, be careful with malicious IPs!")
                if self.current_module == 1:
                    self.advance_module()
                    
        elif command.startswith("decode"):
            if self.current_module >= 1:
                if "shellshock" in command:
                    content_widget.update("✅ Correct! You decoded the vulnerability keyword!")
                    if self.current_module == 1:
                        self.advance_module()
                        
        elif command.startswith("vtscan"):
            if self.current_module >= 2:
                content_widget.update("✅ Excellent! You scanned for threats. Score: 85/100 - MALICIOUS!")
                if self.current_module == 2:
                    self.advance_module()
                    
        elif command.startswith("filter"):
            if self.current_module >= 3:
                content_widget.update("✅ Perfect! You filtered the logs. Found 3 matching entries.")
                if self.current_module == 3:
                    self.advance_module()
                    
        elif command.startswith("search"):
            if self.current_module >= 4:
                content_widget.update("✅ Outstanding! You mastered pattern searching!")
                await self.complete_tutorial()
                
        elif command == "help":
            content_widget.update(self.get_help_text())
            
        elif command == "skip":
            await self.complete_tutorial()
    
    def advance_module(self) -> None:
        """Advance to next tutorial module"""
        self.current_module += 1
        if self.current_module <= self.max_modules:
            content_widget = self.query_one("#content", Static)
            content_widget.update(self.get_module_content())
            commands_widget = self.query_one("#commands", Static)
            commands_widget.update(self.get_available_commands())
    
    def get_help_text(self) -> str:
        """Get help text for current module"""
        return """📚 HELP MENU
        
inspect <IP> - Examine an IP address for clues
decode <string> - Decode an encrypted string
vtscan <target> - Scan IP/hash/domain for threats
filter <expr> - Filter logs by criteria
search <pattern> - Search for patterns in logs
help - Show this menu
skip - Skip tutorial (not recommended for beginners)"""
    
    async def complete_tutorial(self) -> None:
        """Complete tutorial and unlock tools"""
        self.game_state.tutorial_completed = True
        self.game_state.tools_unlocked = {
            "virustotal": True,
            "siem": True,
            "regex": True
        }
        save_game(self.game_state)
        await self.app.push_screen(DashboardScreen(self.game_state))

# ================== Main Dashboard Screen ==================

class DashboardScreen(Screen):
    """Main threat intelligence dashboard"""
    
    CSS = """
    DashboardScreen {
        align: center middle;
    }
    
    .dashboard-container {
        width: 90%;
        height: 90%;
        border: thick $primary;
        background: $surface;
    }
    
    .dashboard-title {
        text-align: center;
        text-style: bold;
        color: #ff5555;
        padding: 1;
        border-bottom: solid $primary;
    }
    
    .chapter-list {
        height: 70%;
        overflow-y: scroll;
        padding: 1;
    }
    
    .chapter-item {
        border: solid $secondary;
        padding: 1;
        margin: 1;
        height: auto;
        background: $boost;
    }
    
    .chapter-locked {
        opacity: 60%;
        border: dashed #555555;
        background: $surface;
    }
    
    .chapter-title {
        text-style: bold;
        color: #ffb86c;
    }
    
    .chapter-bulletin {
        color: #f8f8f2;
        margin-top: 1;
        height: auto;
    }
    
    .chapter-difficulty {
        color: #50fa7b;
        margin-top: 1;
    }
    
    .dashboard-stats {
        height: 20%;
        border-top: solid $primary;
        padding: 1;
        background: $surface;
    }
    """
    
    def __init__(self, game_state: GameState):
        super().__init__()
        self.game_state = game_state
        
    def compose(self) -> ComposeResult:
        yield Header(show_clock=True)
        
        with Container(classes="dashboard-container"):
            yield Static("🔒 CLASSIFIED: THREAT INTELLIGENCE DASHBOARD 🔒", classes="dashboard-title")
            
            with ScrollableContainer(classes="chapter-list"):
                for chapter in CHAPTERS:
                    is_locked = chapter.number > self.game_state.highest_chapter_unlocked
                    
                    with Container(classes="chapter-item chapter-locked" if is_locked else "chapter-item"):
                        status = "🔒 LOCKED" if is_locked else "🔓 AVAILABLE"
                        yield Static(f"{status} | CHAPTER {chapter.number}: {chapter.title}", 
                                   classes="chapter-title")
                        yield Static(f"📋 {chapter.bulletin}", classes="chapter-bulletin")
                        yield Static(f"⚡ Difficulty: {chapter.difficulty.value}", 
                                   classes="chapter-difficulty")
                        
                        if not is_locked:
                            yield Button(f"Launch Chapter {chapter.number}", 
                                       id=f"launch-{chapter.number}",
                                       variant="success")
            
            with Container(classes="dashboard-stats"):
                yield Static(self.get_stats_display())
                
        yield Footer()
    
    def get_stats_display(self) -> str:
        """Get player statistics display"""
        return f"""📊 AGENT STATISTICS
Total Score: {self.game_state.total_score} | Chapters Unlocked: {self.game_state.highest_chapter_unlocked}/5
Tools: {'✅' if self.game_state.tools_unlocked['virustotal'] else '❌'} VirusTotal | {'✅' if self.game_state.tools_unlocked['siem'] else '❌'} SIEM | {'✅' if self.game_state.tools_unlocked['regex'] else '❌'} Regex
Achievements: {len(self.game_state.achievements)} unlocked"""
    
    @on(Button.Pressed)
    async def handle_launch(self, event: Button.Pressed) -> None:
        """Handle chapter launch"""
        if event.button.id and event.button.id.startswith("launch-"):
            chapter_num = int(event.button.id.split("-")[1])
            chapter = CHAPTERS[chapter_num - 1]
            await self.app.push_screen(GameScreen(self.game_state, chapter))

# ================== Pause Menu Modal Screen ==================

class PauseMenuModal(ModalScreen):
    """Pause Menu providing game and system lifecycle commands"""
    
    CSS = """
    PauseMenuModal {
        align: center middle;
        background: rgba(0, 0, 0, 0.65);
    }
    
    .menu-container {
        width: 40;
        height: auto;
        border: thick $primary;
        background: $surface;
        padding: 1 2;
    }
    
    .menu-title {
        text-align: center;
        text-style: bold;
        color: #ffb86c;
        margin-bottom: 1;
    }
    
    .menu-container Button {
        width: 100%;
        margin-bottom: 1;
    }
    """
    
    def compose(self) -> ComposeResult:
        with Container(classes="menu-container"):
            yield Static("⏸️ SYSTEM PAUSED", classes="menu-title")
            yield Button("Back to Investigation", id="menu-back", variant="primary")
            yield Button("Save Current Progress", id="menu-save")
            yield Button("Reload Current System Data", id="menu-reload")
            yield Button("Restart Level", id="menu-restart", variant="warning")
            yield Button("Quit to Main Menu", id="menu-main-menu", variant="error")
            yield Button("Quit to Desktop", id="menu-desktop", variant="error")

    @on(Button.Pressed)
    def handle_button_press(self, event: Button.Pressed) -> None:
        """Dismiss menu sending selected action string back to parent screen"""
        action_map = {
            "menu-back": "back",
            "menu-save": "save",
            "menu-reload": "reload",
            "menu-restart": "restart",
            "menu-main-menu": "main-menu",
            "menu-desktop": "desktop"
        }
        if event.button.id in action_map:
            self.dismiss(action_map[event.button.id])

# ================== Main Game Screen ==================

class GameScreen(Screen):
    """Main game investigation screen"""
    
    BINDINGS = [
        Binding("escape", "toggle_menu", "Pause System Menu", show=True, priority=True)
    ]
    
    CSS = """
        GameScreen {
            layout: vertical;
        }
        
        .game-header {
            height: 3;
            background: $boost;
            padding: 1;
            layout: horizontal;
        }
        
        .header-title {
            width: 50%;
            text-style: bold;
        }
        
        .header-stats {
            width: 50%;
            text-align: right;
        }
        
        .timer-critical { color: $error; text-style: bold blink; }
        .timer-warning { color: $warning; }
        .timer-good { color: $success; }
        
        .game-panels {
            height: 100%;
            layout: vertical;
        }
        
        .briefing-panel {
            height: 25%;
            border: solid #ffb86c;
            padding: 1;
            background: $boost;
            overflow-y: auto;
        }
        
        .log-panel {
            height: 30%;
            border: solid $primary;
            padding: 1;
            overflow-y: auto;
        }
        
        .output-panel {
            height: 25%;
            border: solid $secondary;
            padding: 1;
            overflow-y: auto;
        }
        
        .command-panel {
            height: 20%;
            border: solid $primary;
            padding: 1;
        }
        
        .command-input {
            dock: bottom;
            height: 3;
        }
        """
    
    def __init__(self, game_state: GameState, chapter: ChapterConfig):
        super().__init__()
        self.game_state = game_state
        self.chapter = chapter
        self.logs, self.malicious_ips = LogGenerator.generate_logs(chapter)
        self.start_time = time.time()
        self.time_remaining = chapter.time_limit
        self.score = 100  # Base score
        self.attempts = 0
        self.tools_used = set()
        self.trapped = False
        self.active_filters = []
        self.timer_handle = None
        self.is_paused = False
        
    def compose(self) -> ComposeResult:
        yield Header(show_clock=False)
        
        with Container(classes="game-header"):
            yield Static(f"🎯 {self.chapter.title} | {self.chapter.difficulty.value}", classes="header-title")
            yield Static(f"🏆 Score: {self.score}  |  ⏱️ {self.format_time(self.time_remaining)}", 
                        classes="timer-good", 
                        id="timer-stats")
        
        with Container(classes="game-panels"):
            with ScrollableContainer(classes="briefing-panel"):
                yield Static("", id="top-briefing-text")
                
            with ScrollableContainer(classes="log-panel", id="log-panel"):
                yield Static(self.format_logs())
            
            with ScrollableContainer(classes="output-panel", id="output-panel"):
                yield RichLog(id="analysis-output-text", highlight=True, markup=True)
            
            with Container(classes="command-panel"):
                with ScrollableContainer(classes="help-text"):
                    yield Static(self.get_command_help())
                yield Input(placeholder="Enter forensic command...", 
                        classes="command-input", 
                        id="command-input")
        
        yield Footer()
    
    def on_mount(self) -> None:
        """Initialize game text and start timers"""
        self.set_interval(1, self.update_timer)
        
        briefing_widget = self.query_one("#top-briefing-text", Static)
        story = (
            f"[bold #ffb86c]OPERATIONAL SITUATION BRIEFING FOR NEW RECRUITS:[/]\n"
            f"{self.chapter.bulletin}\n\n"
            f"[bold #50fa7b]YOUR OBJECTIVES TO WIN:[/]\n"
            f" 1. [bold #f1fa8c]Scan External IPs:[/] Type [b]vtscan <IP>[/] using an external address from the packet log rows to flag malicious servers.\n"
            f" 2. [bold #f1fa8c]Examine Files:[/] Type [b]inspect <IP>[/] on suspected systems to uncover code comments or backdoors.\n"
            f" 3. [bold #f1fa8c]Submit Core Verdict:[/] Once you trace the vulnerability, clear the chapter by typing [b]decode <exploit_name>[/]."
        )
        briefing_widget.update(story)
        
        output_log = self.query_one("#analysis-output-text", RichLog)
        output_log.write("🔍 [bold #8be9fd]Forensic Engine initialized.[/] Awaiting target command sequences...")

    def action_toggle_menu(self) -> None:
        """Handle escape hotkey to launch or pop the pause menu interface"""
        # If already paused, check if the top screen is our Modal and dismiss it to return
        if self.is_paused:
            if isinstance(self.app.screen, PauseMenuModal):
                self.app.screen.dismiss("back")
        else:
            self.is_paused = True
            self.app.push_screen(PauseMenuModal(), callback=self.handle_menu_action)

    async def handle_menu_action(self, action: Optional[str]) -> None:
        """Process execution logic returned from our pause menu interface modal"""
        self.is_paused = False
        output_log = self.query_one("#analysis-output-text", RichLog)
        
        if not action or action == "back":
            output_log.write("▶️ [bold #50fa7b]System Resumed.[/] Operational workflow online.")
            return
            
        if action == "save":
            save_game(self.game_state)
            output_log.write("💾 [bold #50fa7b]Progress Saved Successfully.[/]")
            
        elif action == "reload":
            self.logs, self.malicious_ips = LogGenerator.generate_logs(self.chapter)
            # Change Static to ScrollableContainer
            log_panel = self.query_one("#log-panel", ScrollableContainer)
            # Clear the container's old content and replace it with the new logs
            log_panel.remove_children()
            log_panel.mount(Static(self.format_logs()))
            
        elif action == "restart":
            self.time_remaining = self.chapter.time_limit
            self.score = 100
            self.attempts = 0
            self.tools_used.clear()
            self.trapped = False
            self.active_filters.clear()
            self.logs, self.malicious_ips = LogGenerator.generate_logs(self.chapter)
            
            log_panel = self.query_one("#log-panel", Static)
            log_panel.update(self.format_logs())
            output_log.clear()
            output_log.write("🔄 [bold #ff5555]Level Reset Complete.[/] Investigative matrix restored.")
            
        elif action == "main-menu":
            await self.app.push_screen(DashboardScreen(self.game_state))
            
        elif action == "desktop":
            self.app.exit()

    async def update_timer(self) -> None:
        """Update live countdown clock and tracking stats simultaneously"""
        if self.is_paused:
            return
            
        self.time_remaining -= 1
        stats_widget = self.query_one("#timer-stats", Static)
        
        if self.time_remaining <= 0:
            stats_widget.update(f"🏆 Score: {self.score}  |  ⏱️ TIME UP!")
            stats_widget.set_class(True, "timer-critical")
            stats_widget.set_class(False, "timer-warning")
            stats_widget.set_class(False, "timer-good")
            await self.game_over(False)
        else:
            stats_widget.update(f"🏆 Score: {self.score}  |  ⏱️ {self.format_time(self.time_remaining)}")
            
            if self.time_remaining < 60:
                stats_widget.set_class(True, "timer-critical")
                stats_widget.set_class(False, "timer-warning")
                stats_widget.set_class(False, "timer-good")
            elif self.time_remaining < 180:
                stats_widget.set_class(False, "timer-critical")
                stats_widget.set_class(True, "timer-warning")
                stats_widget.set_class(False, "timer-good")
            else:
                stats_widget.set_class(False, "timer-critical")
                stats_widget.set_class(False, "timer-warning")
                stats_widget.set_class(True, "timer-good")
    
    def format_time(self, seconds: int) -> str:
        """Format seconds as MM:SS"""
        minutes = seconds // 60
        seconds = seconds % 60
        return f"{minutes:02d}:{seconds:02d}"
    
    def format_logs(self) -> str:
        """Format logs for display"""
        output = "📜 NETWORK TRAFFIC LOGS\n" + "="*50 + "\n\n"
        
        for log in self.logs:
            if self.active_filters:
                skip = False
                for filter_expr in self.active_filters:
                    if "=" in filter_expr:
                        field, value = filter_expr.split("=")
                        if field == "port" and str(log["dst_port"]) != value:
                            skip = True
                        elif field == "action" and log["action"] != value.upper():
                            skip = True
                    elif ">" in filter_expr:
                        field, value = filter_expr.split(">")
                        if field == "size" and log["size"] <= int(value):
                            skip = True
                
                if skip:
                    continue
            
            entry = f"[{log['timestamp']}] "
            entry += f"{log['src_ip']}:{log['src_port']} -> "
            entry += f"{log['dst_ip']}:{log['dst_port']} "
            entry += f"({log['protocol']}) "
            entry += f"[{log['size']} bytes] "
            
            if log['action'] == 'ALERT':
                entry += "⚠️ ALERT"
            
            output += entry + "\n"
        
        return output
    
    def get_command_help(self) -> str:
        """Get command help text"""
        help_text = "📚 AVAILABLE COMMANDS:\n"
        help_text += "• inspect <IP> - Examine IP for clues\n"
        help_text += "• decode <string> - Decode vulnerability keyword\n"
        
        if self.game_state.tools_unlocked.get("virustotal"):
            help_text += "• vtscan <IP> - Scan for threats\n"
        
        if self.game_state.tools_unlocked.get("siem"):
            help_text += "• filter <expr> - Filter logs (port=X, action=X, size>X)\n"
            help_text += "• clear - Clear all filters\n"
        
        if self.game_state.tools_unlocked.get("regex"):
            help_text += "• search <pattern> - Search patterns\n"
        
        help_text += "• hint - Get a hint (-10 points)\n"
        help_text += "• help - Show detailed help\n"
        
        return help_text
    
    @on(Input.Submitted)
    async def handle_command(self, event: Input.Submitted) -> None:
        """Process forensic commands"""
        if self.is_paused:
            return
            
        command = event.value.strip()
        input_widget = self.query_one("#command-input", Input)
        input_widget.clear()
        
        output_widget = self.query_one("#analysis-output-text", RichLog)
        
        parts = command.split(maxsplit=1)
        if not parts:
            return
        
        cmd = parts[0].lower()
        args = parts[1] if len(parts) > 1 else ""
        
        output = ""
        
        if cmd == "inspect":
            if not args:
                output = "❌ Usage: inspect <IP>"
            else:
                is_trap, content = ForensicTools.inspect_ip(
                    args, 
                    self.malicious_ips, 
                    self.chapter.vulnerability_keyword
                )
                
                if is_trap:
                    self.trapped = True
                    self.score -= 50
                    output = "🚨 TRAP TRIGGERED! 🚨\n\n"
                    output += content + "\n\n"
                    output += "💡 LEARNING MOMENT: Always use sandboxed tools first!\n"
                    output += f"Score penalty: -50 (Current: {self.score})"
                    
                    if not self.game_state.tutorial_completed:
                        output += "\n\n⚠️ TIP: Use 'vtscan' to check IPs safely first!"
                else:
                    self.tools_used.add("inspect")
                    output = f"📄 Inspecting {args}...\n\n{content}"
        
        elif cmd == "vtscan" and self.game_state.tools_unlocked.get("virustotal"):
            if not args:
                output = "❌ Usage: vtscan <IP>"
            else:
                self.tools_used.add("vtscan")
                results = ForensicTools.vtscan(args, self.malicious_ips)
                
                output = f"🔍 VirusTotal Scan Results for {args}\n"
                output += "="*50 + "\n"
                
                if results["threat_level"] == ThreatLevel.MALICIOUS:
                    output += f"⚠️ THREAT LEVEL: MALICIOUS (Score: {results['threat_score']})\n"
                elif results["threat_level"] == ThreatLevel.SUSPICIOUS:
                    output += f"⚠️ THREAT LEVEL: SUSPICIOUS (Score: {results['threat_score']})\n"
                else:
                    output += f"✅ THREAT LEVEL: SAFE (Score: {results['threat_score']})\n"
                
                output += f"Detection Ratio: {results['detection_ratio']}\n"
                output += f"Location: {results['geo_location']} ({results['asn']})\n"
                output += f"First Seen: {results['first_seen']}\n"
                output += f"SSL Certificate: {results['ssl_cert']}\n"
                
                if results["malware_families"]:
                    output += f"Malware Families: {', '.join(results['malware_families'])}\n"
        
        elif cmd == "filter" and self.game_state.tools_unlocked.get("siem"):
            if not args:
                output = "❌ Usage: filter <field>=<value> or filter <field>><value>"
            else:
                self.tools_used.add("filter")
                self.active_filters.append(args)
                
                log_panel = self.query_one("#log-panel", Static)
                log_panel.update(self.format_logs())
                
                output = f"✅ Filter applied: {args}\n"
                output += f"Active filters: {', '.join(self.active_filters)}"
        
        elif cmd == "clear":
            self.active_filters = []
            log_panel = self.query_one("#log-panel", Static)
            log_panel.update(self.format_logs())
            output = "✅ All filters cleared"
        
        elif cmd == "search" and self.game_state.tools_unlocked.get("regex"):
            if not args:
                output = "❌ Usage: search <pattern>"
            else:
                self.tools_used.add("search")
                
                if args == "suspicious_ports":
                    suspicious_ports = [445, 3389, 22, 139, 135, 1433]
                    found = []
                    for log in self.logs:
                        if log["dst_port"] in suspicious_ports:
                            found.append(f"{log['src_ip']} -> port {log['dst_port']}")
                    
                    if found:
                        output = f"🔍 Found {len(found)} suspicious port connections:\n"
                        output += "\n".join(found[:10])
                    else:
                        output = "No suspicious ports found"
                
                elif args == "data_exfil":
                    found = []
                    for log in self.logs:
                        if log["size"] > 10000:
                            found.append(f"{log['src_ip']} -> {log['dst_ip']} ({log['size']} bytes)")
                    
                    if found:
                        output = f"🔍 Found {len(found)} potential data exfiltration attempts:\n"
                        output += "\n".join(found[:10])
                    else:
                        output = "No large data transfers found"
                
                else:
                    output = f"Searching for pattern: {args}\n"
                    output += "Pattern search executed successfully"
        
        elif cmd == "decode":
            if not args:
                output = "❌ Usage: decode <string>"
            else:
                self.attempts += 1
                
                if ForensicTools.decode_string(args, self.chapter.vulnerability_keyword):
                    self.score += (self.time_remaining // 10)
                    self.score += len(self.tools_used) * 10
                    
                    output = "🎉 SUCCESS! 🎉\n\n"
                    output += f"✅ Correct vulnerability identified: {self.chapter.vulnerability_keyword.upper()}\n"
                    output += f"✅ Target port confirmed: {self.chapter.target_port}\n\n"
                    output += f"📊 MISSION COMPLETE\n"
                    output += f"Base Score: 100\n"
                    output += f"Time Bonus: {self.time_remaining // 10}\n"
                    output += f"Tools Used: {len(self.tools_used) * 10}\n"
                    output += f"Penalties: {'-50' if self.trapped else '0'}\n"
                    output += f"TOTAL SCORE: {self.score}"
                    
                    await self.game_over(True)
                else:
                    self.score -= 10
                    output = f"❌ Incorrect decode attempt #{self.attempts}\n"
                    output += f"Score penalty: -10 (Current: {self.score})\n"
                    
                    if self.attempts >= 2:
                        output += f"\n💡 Hint: The vulnerability is related to {self.chapter.difficulty.value.lower()} level threats"
        
        elif cmd == "hint":
            self.score -= 10
            self.tools_used.add("hint")
            
            hints = {
                1: "💡 Look for comments in HTML source code when inspecting IPs",
                2: "💡 The malicious IP will have a high threat score in vtscan",
                3: f"💡 The target port is commonly used for {self.get_port_hint()}",
                4: f"💡 The vulnerability keyword contains {len(self.chapter.vulnerability_keyword)} characters"
            }
            
            hint_num = min(self.attempts + 1, 4)
            output = hints[hint_num]
            output += f"\nScore penalty: -10 (Current: {self.score})"
        
        elif cmd == "help":
            output = self.get_detailed_help()
        
        else:
            output = f"❌ Unknown command: {cmd}\n"
            output += "Type 'help' for available commands"
        
        output_widget.write(f"\n{'='*50}\n{output}")
    
    def get_port_hint(self) -> str:
        """Get hint about port usage"""
        port_hints = {
            80: "HTTP web traffic",
            443: "HTTPS secure web traffic",
            445: "SMB/CIFS file sharing",
            22: "SSH remote access",
            3389: "RDP Windows remote desktop",
            88: "Kerberos authentication",
            502: "Modbus industrial control",
            25: "SMTP email"
        }
        return port_hints.get(self.chapter.target_port, "network services")
    
    def get_detailed_help(self) -> str:
        """Get detailed help text"""
        help_text = "📚 DETAILED FORENSICS MANUAL\n"
        help_text += "="*50 + "\n\n"
        
        help_text += "🔍 INVESTIGATION COMMANDS:\n\n"
        
        help_text += "inspect <IP>\n"
        help_text += "  Directly connect to an IP address to examine its content.\n"
        help_text += "  ⚠️ WARNING: Connecting to malicious IPs will trigger traps!\n"
        help_text += "  Example: inspect 192.168.1.100\n\n"
        
        help_text += "decode <string>\n"
        help_text += "  Attempt to decode the vulnerability keyword.\n"
        help_text += "  Multiple formats accepted (uppercase/lowercase/etc)\n"
        help_text += "  Example: decode wannacry\n\n"
        
        if self.game_state.tools_unlocked.get("virustotal"):
            help_text += "vtscan <IP>\n"
            help_text += "  Safely scan an IP for threats using VirusTotal database.\n"
            help_text += "  Returns threat score, malware families, and reputation.\n"
            help_text += "  Example: vtscan 185.220.101.45\n\n"
        
        if self.game_state.tools_unlocked.get("siem"):
            help_text += "filter <expression>\n"
            help_text += "  Apply SIEM filters to reduce log noise.\n"
            help_text += "  Supported: port=X, action=ALERT, size>X\n"
            help_text += "  Example: filter port=445\n\n"
            
            help_text += "clear\n"
            help_text += "  Remove all active filters\n\n"
        
        if self.game_state.tools_unlocked.get("regex"):
            help_text += "search <pattern>\n"
            help_text += "  Search for patterns in logs.\n"
            help_text += "  Presets: suspicious_ports, data_exfil, encoded\n"
            help_text += "  Example: search suspicious_ports\n\n"
        
        help_text += "hint\n"
        help_text += "  Get a contextual hint (-10 points)\n\n"
        
        return help_text
    
    async def game_over(self, success: bool) -> None:
        """Handle game over state"""
        if success:
            self.game_state.total_score += self.score
            
            if self.chapter.number >= self.game_state.highest_chapter_unlocked:
                self.game_state.highest_chapter_unlocked = min(self.chapter.number + 1, 5)
            
            if "First Blood" not in self.game_state.achievements and self.chapter.number == 1:
                self.game_state.achievements.append("First Blood")
            
            if len(self.tools_used) >= 3 and "Tool Master" not in self.game_state.achievements:
                self.game_state.achievements.append("Tool Master")
            
            if self.time_remaining > 480 and "Speed Demon" not in self.game_state.achievements:
                self.game_state.achievements.append("Speed Demon")
            
            if not self.trapped and self.attempts == 1 and "Perfect Investigation" not in self.game_state.achievements:
                self.game_state.achievements.append("Perfect Investigation")
            
            score_entry = {
                "chapter": self.chapter.number,
                "score": self.score,
                "timestamp": datetime.now().isoformat()
            }
            self.game_state.high_scores.append(score_entry)
            self.game_state.high_scores = sorted(
                self.game_state.high_scores, 
                key=lambda x: x["score"], 
                reverse=True
            )[:10]
            
            save_game(self.game_state)
        
        await self.app.push_screen(DashboardScreen(self.game_state))

# ================== Welcome Modal ==================

class WelcomeModal(ModalScreen):
    """Initial welcome screen asking about tutorial"""
    
    CSS = """
    WelcomeModal {
        align: center middle;
    }
    
    .welcome-container {
        width: 60;
        height: 20;
        border: thick $primary;
        background: $surface;
        padding: 2;
    }
    
    .welcome-title {
        text-align: center;
        text-style: bold;
        color: $success;
        margin-bottom: 2;
    }
    
    .welcome-text {
        text-align: center;
        margin-bottom: 2;
    }
    
    .welcome-buttons {
        layout: horizontal;
        align: center middle;
        height: 3;
    }
    
    .welcome-buttons Button {
        margin: 0 2;
    }
    """
    
    def compose(self) -> ComposeResult:
        with Container(classes="welcome-container"):
            yield Static("🕵️ THE FORENSICS BRIEFING 🕵️", classes="welcome-title")
            yield Static(
                "Welcome, Agent.\n\n"
                "This is your first mission briefing.\n"
                "Execute Sandbox Training Tutorial?",
                classes="welcome-text"
            )
            with Horizontal(classes="welcome-buttons"):
                yield Button("Yes", id="tutorial-yes", variant="success")
                yield Button("No", id="tutorial-no", variant="error")
    
    @on(Button.Pressed, "#tutorial-yes")
    async def start_tutorial(self) -> None:
        """Start the tutorial"""
        self.dismiss(True)
    
    @on(Button.Pressed, "#tutorial-no")
    async def skip_tutorial(self) -> None:
        """Skip the tutorial"""
        self.dismiss(False)

# ================== Main Application ==================

class ForensicsBriefingApp(App):
    """The main Forensics Briefing TUI application"""
    
    CSS = """
    Screen {
        background: $surface;
    }
    """
    
    TITLE = "The Forensics Briefing - Cyber Investigation Terminal"
    SUB_TITLE = "Version 1.0.0 | CLASSIFIED"
    
    def __init__(self):
        super().__init__()
        self.game_state = load_game()
    
    async def on_mount(self) -> None:
        """Initialize the application"""
        if not self.game_state.tutorial_completed:
            # Show welcome modal
            self.push_screen(WelcomeModal(), callback=self.handle_welcome_response)
        else:
            # Go straight to dashboard
            self.push_screen(DashboardScreen(self.game_state))
    
    def handle_welcome_response(self, start_tutorial: bool) -> None:
        """Handle the response from welcome modal"""
        if start_tutorial:
            self.push_screen(TutorialScreen(self.game_state))
        else:
            # Mark tutorial as completed and go to dashboard
            self.game_state.tutorial_completed = True
            self.game_state.tools_unlocked = {
                "virustotal": True,
                "siem": True,
                "regex": True
            }
            save_game(self.game_state)
            self.push_screen(DashboardScreen(self.game_state))

# ================== Entry Point ==================

def main():
    """Main entry point for the application"""
    app = ForensicsBriefingApp()
    app.run()

if __name__ == "__main__":
    main()