#!/usr/bin/env python3
"""
GameBot desktop app.

When packaged with PyInstaller, this single EXE installs the bundled app files
into the user's local app folder, creates Windows shortcuts, starts the local
server, and runs the button-based game UI.
"""

import json
import importlib.util
import os
import shutil
import subprocess
import sys
import threading
import time
import tkinter as tk
import urllib.error
import urllib.parse
import urllib.request
import webbrowser
from pathlib import Path
from tkinter import messagebox, ttk


APP_NAME = "GameBot"
SERVER_PORT = int(os.getenv("GAMEBOT_PORT", "5000"))
SERVER_URL = os.getenv("GAMEBOT_SERVER_URL", f"http://127.0.0.1:{SERVER_PORT}")
API_URL = f"{SERVER_URL}/api/v3"
ASSET_FILES = [
    "gamebot_multiplayer_server.py",
    "master.html",
    "login.html",
    "dashboard.html",
    "requirements.txt",
    ".env.example",
]

THEMES = {
    "Nebula": {
        "bg": "#090b1f",
        "panel": "#111735",
        "panel_alt": "#182044",
        "text": "#f5f7ff",
        "muted": "#9aa7d9",
        "accent": "#7c5cff",
        "accent_2": "#00d4ff",
        "success": "#37d67a",
        "danger": "#ff5f7a",
        "button_text": "#ffffff",
    },
    "Solar": {
        "bg": "#fff8eb",
        "panel": "#fffdf7",
        "panel_alt": "#ffe6b8",
        "text": "#261b12",
        "muted": "#7a5d44",
        "accent": "#ff7a1a",
        "accent_2": "#0b9f8a",
        "success": "#1a9f56",
        "danger": "#c93434",
        "button_text": "#ffffff",
    },
    "Cyber Mint": {
        "bg": "#061414",
        "panel": "#0b2523",
        "panel_alt": "#103631",
        "text": "#eafff8",
        "muted": "#8cc9b9",
        "accent": "#22e6a8",
        "accent_2": "#ffcf5a",
        "success": "#54e37e",
        "danger": "#ff6b6b",
        "button_text": "#04100d",
    },
}

GAME_BUTTONS = {
    "rps": ("Rock Paper Scissors", ["rock", "paper", "scissors"]),
    "dice": ("Dice Duel", ["low", "seven", "high"]),
    "slots": ("Neon Slots", ["spin"]),
    "trivia": ("Trivia Pulse", ["Mars", "Venus", "Jupiter"]),
    "math": ("Math Blitz", ["48", "54", "56"]),
    "blackjack": ("Blackjack Snap", ["deal"]),
}


def app_data_dir() -> Path:
    base = os.getenv("LOCALAPPDATA") or str(Path.home())
    return Path(base) / APP_NAME


def source_dir() -> Path:
    if getattr(sys, "frozen", False):
        return Path(getattr(sys, "_MEIPASS"))
    return Path(__file__).resolve().parent


def install_bundled_assets() -> Path:
    """Copy bundled assets to a stable folder when running from an EXE."""
    if not getattr(sys, "frozen", False):
        return Path(__file__).resolve().parent

    target_dir = app_data_dir()
    target_dir.mkdir(parents=True, exist_ok=True)
    bundle_dir = source_dir()

    for asset_name in ASSET_FILES:
        source = bundle_dir / asset_name
        target = target_dir / asset_name
        if source.exists():
            shutil.copy2(source, target)

    create_windows_shortcuts()
    return target_dir


def create_windows_shortcuts():
    """Create Start Menu and Desktop shortcuts for packaged Windows builds."""
    if os.name != "nt" or not getattr(sys, "frozen", False):
        return

    exe_path = Path(sys.executable)
    start_menu = Path(os.getenv("APPDATA", str(Path.home()))) / "Microsoft" / "Windows" / "Start Menu" / "Programs" / APP_NAME
    desktop = Path.home() / "Desktop"
    start_menu.mkdir(parents=True, exist_ok=True)

    shortcuts = [start_menu / f"{APP_NAME}.lnk", desktop / f"{APP_NAME}.lnk"]
    for shortcut_path in shortcuts:
        script = (
            "$shell = New-Object -ComObject WScript.Shell; "
            f"$shortcut = $shell.CreateShortcut('{shortcut_path}'); "
            f"$shortcut.TargetPath = '{exe_path}'; "
            f"$shortcut.WorkingDirectory = '{exe_path.parent}'; "
            "$shortcut.Save()"
        )
        try:
            subprocess.run(
                ["powershell", "-NoProfile", "-ExecutionPolicy", "Bypass", "-Command", script],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                check=False,
                creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
            )
        except Exception:
            pass


class GameBotApp:
    def __init__(self, root):
        self.root = root
        self.root.title("GameBot")
        self.root.geometry("1120x720")
        self.root.minsize(980, 640)

        self.runtime_dir = install_bundled_assets()
        self.session_file = app_data_dir() / "session.json"
        self.server_process = None
        self.server_thread = None
        self.server_ready = False
        self.token = None
        self.current_user = None
        self.current_friend = None
        self.theme_name = "Nebula"
        self.frames = {}
        self.status_var = tk.StringVar(value="Starting local server...")
        self.result_var = tk.StringVar(value="Pick a game and press a button.")

        self.load_session()
        self.build_shell()
        self.apply_theme()
        self.show_page("games")
        self.start_server()

    @property
    def theme(self):
        return THEMES[self.theme_name]

    def load_session(self):
        try:
            data = json.loads(self.session_file.read_text(encoding="utf-8"))
        except Exception:
            return
        self.token = data.get("token")
        self.current_user = data.get("user")

    def save_session(self):
        app_data_dir().mkdir(parents=True, exist_ok=True)
        self.session_file.write_text(
            json.dumps({"token": self.token, "user": self.current_user}, indent=2),
            encoding="utf-8",
        )

    def clear_session(self):
        self.token = None
        self.current_user = None
        try:
            self.session_file.unlink()
        except FileNotFoundError:
            pass

    def build_shell(self):
        self.root.columnconfigure(1, weight=1)
        self.root.rowconfigure(1, weight=1)

        self.header = tk.Frame(self.root, height=74)
        self.header.grid(row=0, column=0, columnspan=2, sticky="nsew")
        self.header.grid_columnconfigure(1, weight=1)

        self.title_label = tk.Label(self.header, text="GAMEBOT", font=("Segoe UI", 28, "bold"))
        self.title_label.grid(row=0, column=0, padx=24, pady=16, sticky="w")

        self.status_label = tk.Label(self.header, textvariable=self.status_var, font=("Segoe UI", 10))
        self.status_label.grid(row=0, column=1, sticky="e")

        self.theme_picker = ttk.Combobox(self.header, values=list(THEMES.keys()), state="readonly", width=14)
        self.theme_picker.set(self.theme_name)
        self.theme_picker.bind("<<ComboboxSelected>>", self.change_theme)
        self.theme_picker.grid(row=0, column=2, padx=20, sticky="e")

        self.sidebar = tk.Frame(self.root, width=184)
        self.sidebar.grid(row=1, column=0, sticky="nsew")
        self.sidebar.grid_propagate(False)

        self.nav_buttons = {}
        nav_items = [
            ("games", "Games"),
            ("friends", "Friends"),
            ("chat", "Chat"),
            ("account", "Account"),
        ]
        for index, (page, label) in enumerate(nav_items):
            button = tk.Button(self.sidebar, text=label, command=lambda p=page: self.show_page(p), anchor="w")
            button.grid(row=index, column=0, sticky="ew", padx=14, pady=(16 if index == 0 else 8, 0), ipady=10)
            self.nav_buttons[page] = button
        self.sidebar.grid_columnconfigure(0, weight=1)

        self.content = tk.Frame(self.root)
        self.content.grid(row=1, column=1, sticky="nsew")
        self.content.grid_rowconfigure(0, weight=1)
        self.content.grid_columnconfigure(0, weight=1)

        self.frames["games"] = self.build_games_page()
        self.frames["friends"] = self.build_friends_page()
        self.frames["chat"] = self.build_chat_page()
        self.frames["account"] = self.build_account_page()

    def build_games_page(self):
        frame = tk.Frame(self.content)
        frame.grid_rowconfigure(1, weight=1)
        frame.grid_columnconfigure(0, weight=1)

        headline = tk.Label(frame, text="Button Arena", font=("Segoe UI", 24, "bold"))
        headline.grid(row=0, column=0, padx=26, pady=(24, 8), sticky="w")

        grid = tk.Frame(frame)
        grid.grid(row=1, column=0, padx=24, pady=10, sticky="nsew")
        for col in range(3):
            grid.grid_columnconfigure(col, weight=1)

        for index, (game_id, (name, choices)) in enumerate(GAME_BUTTONS.items()):
            card = tk.Frame(grid, bd=0, highlightthickness=1)
            card.grid(row=index // 3, column=index % 3, padx=10, pady=10, sticky="nsew")
            card.grid_columnconfigure(0, weight=1)
            title = tk.Label(card, text=name, font=("Segoe UI", 15, "bold"))
            title.grid(row=0, column=0, padx=16, pady=(16, 10), sticky="w")
            buttons = tk.Frame(card)
            buttons.grid(row=1, column=0, padx=12, pady=(0, 16), sticky="ew")
            for choice_index, choice in enumerate(choices):
                button = tk.Button(
                    buttons,
                    text=choice.title(),
                    command=lambda g=game_id, c=choice: self.play_game(g, c),
                )
                button.grid(row=0, column=choice_index, padx=4, sticky="ew")
                buttons.grid_columnconfigure(choice_index, weight=1)

        result_panel = tk.Frame(frame, highlightthickness=1)
        result_panel.grid(row=2, column=0, padx=34, pady=(8, 28), sticky="ew")
        result_panel.grid_columnconfigure(0, weight=1)
        self.result_label = tk.Label(result_panel, textvariable=self.result_var, font=("Segoe UI", 13), wraplength=760)
        self.result_label.grid(row=0, column=0, padx=18, pady=16, sticky="w")
        return frame

    def build_friends_page(self):
        frame = tk.Frame(self.content)
        frame.grid_columnconfigure(0, weight=1)
        frame.grid_columnconfigure(1, weight=1)

        title = tk.Label(frame, text="Friends", font=("Segoe UI", 24, "bold"))
        title.grid(row=0, column=0, columnspan=2, padx=26, pady=(24, 12), sticky="w")

        search_panel = tk.Frame(frame, highlightthickness=1)
        search_panel.grid(row=1, column=0, padx=24, pady=10, sticky="nsew")
        search_panel.grid_columnconfigure(0, weight=1)
        tk.Label(search_panel, text="Find Player", font=("Segoe UI", 14, "bold")).grid(row=0, column=0, padx=16, pady=(16, 8), sticky="w")
        self.friend_search = tk.Entry(search_panel, font=("Segoe UI", 12))
        self.friend_search.grid(row=1, column=0, padx=16, pady=8, sticky="ew")
        tk.Button(search_panel, text="Search", command=self.search_users).grid(row=1, column=1, padx=16, pady=8)
        self.search_results = tk.Frame(search_panel)
        self.search_results.grid(row=2, column=0, columnspan=2, padx=16, pady=12, sticky="ew")

        list_panel = tk.Frame(frame, highlightthickness=1)
        list_panel.grid(row=1, column=1, padx=24, pady=10, sticky="nsew")
        list_panel.grid_columnconfigure(0, weight=1)
        tk.Label(list_panel, text="Your Squad", font=("Segoe UI", 14, "bold")).grid(row=0, column=0, padx=16, pady=(16, 8), sticky="w")
        tk.Button(list_panel, text="Refresh", command=self.refresh_social).grid(row=0, column=1, padx=16, pady=(16, 8))
        self.friend_list = tk.Frame(list_panel)
        self.friend_list.grid(row=1, column=0, columnspan=2, padx=16, pady=8, sticky="ew")
        self.request_list = tk.Frame(list_panel)
        self.request_list.grid(row=2, column=0, columnspan=2, padx=16, pady=8, sticky="ew")
        return frame

    def build_chat_page(self):
        frame = tk.Frame(self.content)
        frame.grid_columnconfigure(0, weight=1)
        frame.grid_rowconfigure(1, weight=1)

        title = tk.Label(frame, text="Encrypted Chat", font=("Segoe UI", 24, "bold"))
        title.grid(row=0, column=0, padx=26, pady=(24, 12), sticky="w")

        self.chat_partner_label = tk.Label(frame, text="Pick a friend from the Friends tab.", font=("Segoe UI", 12))
        self.chat_partner_label.grid(row=0, column=0, padx=26, pady=(34, 12), sticky="e")

        self.chat_text = tk.Text(frame, height=18, wrap="word", state=tk.DISABLED, font=("Segoe UI", 11))
        self.chat_text.grid(row=1, column=0, padx=24, pady=10, sticky="nsew")

        composer = tk.Frame(frame)
        composer.grid(row=2, column=0, padx=24, pady=(8, 24), sticky="ew")
        composer.grid_columnconfigure(0, weight=1)
        self.chat_entry = tk.Entry(composer, font=("Segoe UI", 12))
        self.chat_entry.grid(row=0, column=0, sticky="ew", ipady=7)
        self.chat_entry.bind("<Return>", lambda _event: self.send_message())
        tk.Button(composer, text="Send", command=self.send_message).grid(row=0, column=1, padx=(10, 0), ipadx=18, ipady=6)
        return frame

    def build_account_page(self):
        frame = tk.Frame(self.content)
        frame.grid_columnconfigure(0, weight=1)

        title = tk.Label(frame, text="Account", font=("Segoe UI", 24, "bold"))
        title.grid(row=0, column=0, padx=26, pady=(24, 12), sticky="w")

        panel = tk.Frame(frame, highlightthickness=1)
        panel.grid(row=1, column=0, padx=24, pady=10, sticky="ew")
        panel.grid_columnconfigure(1, weight=1)

        self.account_status = tk.Label(panel, text="", font=("Segoe UI", 12, "bold"))
        self.account_status.grid(row=0, column=0, columnspan=2, padx=16, pady=(16, 8), sticky="w")

        labels = [("Username", "username_entry"), ("Email", "email_entry"), ("Password", "password_entry")]
        for row, (label_text, attr) in enumerate(labels, start=1):
            tk.Label(panel, text=label_text, font=("Segoe UI", 11)).grid(row=row, column=0, padx=16, pady=8, sticky="w")
            show = "*" if "Password" in label_text else ""
            entry = tk.Entry(panel, font=("Segoe UI", 12), show=show)
            entry.grid(row=row, column=1, padx=16, pady=8, sticky="ew", ipady=5)
            setattr(self, attr, entry)

        actions = tk.Frame(panel)
        actions.grid(row=4, column=0, columnspan=2, padx=16, pady=16, sticky="ew")
        tk.Button(actions, text="Login", command=self.login).grid(row=0, column=0, padx=(0, 8), ipadx=18, ipady=6)
        tk.Button(actions, text="Create Account", command=self.register).grid(row=0, column=1, padx=8, ipadx=18, ipady=6)
        tk.Button(actions, text="Logout", command=self.logout).grid(row=0, column=2, padx=8, ipadx=18, ipady=6)
        tk.Button(actions, text="Open Account Website", command=lambda: webbrowser.open(f"{SERVER_URL}/login.html")).grid(row=0, column=3, padx=8, ipadx=18, ipady=6)

        self.update_account_status()
        return frame

    def apply_theme(self):
        theme = self.theme
        style = ttk.Style()
        try:
            style.theme_use("clam")
        except Exception:
            pass
        style.configure("TCombobox", fieldbackground=theme["panel"], background=theme["panel"], foreground=theme["text"])

        self.root.configure(bg=theme["bg"])
        for frame in [self.header, self.sidebar, self.content, *self.frames.values()]:
            frame.configure(bg=theme["bg"])

        for widget in self.root.winfo_children():
            self.paint_tree(widget)

    def paint_tree(self, widget):
        theme = self.theme
        cls = widget.winfo_class()
        try:
            if cls in {"Frame", "TFrame"}:
                widget.configure(bg=theme["panel"] if widget is self.sidebar else theme["bg"])
            elif cls == "Label":
                widget.configure(bg=widget.master.cget("bg"), fg=theme["text"])
            elif cls == "Button":
                widget.configure(
                    bg=theme["accent"],
                    fg=theme["button_text"],
                    activebackground=theme["accent_2"],
                    activeforeground=theme["button_text"],
                    relief=tk.FLAT,
                    bd=0,
                    cursor="hand2",
                    font=("Segoe UI", 10, "bold"),
                )
            elif cls == "Entry":
                widget.configure(bg=theme["panel_alt"], fg=theme["text"], insertbackground=theme["text"], relief=tk.FLAT)
            elif cls == "Text":
                widget.configure(bg=theme["panel"], fg=theme["text"], insertbackground=theme["text"], relief=tk.FLAT)
        except Exception:
            pass

        try:
            if int(widget.cget("highlightthickness")):
                widget.configure(bg=theme["panel"], highlightbackground=theme["accent"], highlightcolor=theme["accent"])
        except Exception:
            pass

        for child in widget.winfo_children():
            self.paint_tree(child)

    def change_theme(self, _event=None):
        self.theme_name = self.theme_picker.get()
        self.apply_theme()

    def show_page(self, page):
        for frame in self.frames.values():
            frame.grid_forget()
        self.frames[page].grid(row=0, column=0, sticky="nsew")
        if page in {"friends", "chat"} and self.token:
            self.refresh_social()

    def start_server(self):
        thread = threading.Thread(target=self._start_server_worker, daemon=True)
        thread.start()

    def _start_server_worker(self):
        if self.check_server_ready():
            self.server_ready = True
            self.status_var.set("Server ready")
            return

        self.server_thread = threading.Thread(target=self._run_embedded_server, daemon=True)
        self.server_thread.start()

        deadline = time.time() + 30
        while time.time() < deadline:
            if self.check_server_ready():
                self.server_ready = True
                self.status_var.set("Server ready")
                return
            time.sleep(0.5)

        self.status_var.set("Server still starting")

    def _run_embedded_server(self):
        server_file = self.runtime_dir / "gamebot_multiplayer_server.py"
        try:
            if str(self.runtime_dir) not in sys.path:
                sys.path.insert(0, str(self.runtime_dir))
            os.chdir(self.runtime_dir)
            spec = importlib.util.spec_from_file_location("gamebot_multiplayer_server", server_file)
            module = importlib.util.module_from_spec(spec)
            sys.modules["gamebot_multiplayer_server"] = module
            spec.loader.exec_module(module)
            with module.app.app_context():
                module.init_database()
            module.app.run(
                host="127.0.0.1",
                port=SERVER_PORT,
                debug=False,
                threaded=True,
                use_reloader=False,
            )
        except Exception as exc:
            self.status_var.set(f"Server failed to start: {exc}")

    def check_server_ready(self):
        try:
            with urllib.request.urlopen(f"{API_URL}/health", timeout=1) as response:
                return response.status == 200
        except Exception:
            return False

    def api_request(self, path, method="GET", payload=None, auth=True):
        if not self.server_ready and not self.check_server_ready():
            raise RuntimeError("Server is still starting. Try again in a moment.")

        data = None
        headers = {"Content-Type": "application/json"}
        if payload is not None:
            data = json.dumps(payload).encode("utf-8")
        if auth and self.token:
            headers["Authorization"] = f"Bearer {self.token}"

        request = urllib.request.Request(f"{API_URL}{path}", data=data, headers=headers, method=method)
        try:
            with urllib.request.urlopen(request, timeout=8) as response:
                body = response.read().decode("utf-8")
                return json.loads(body) if body else {}
        except urllib.error.HTTPError as exc:
            body = exc.read().decode("utf-8")
            try:
                message = json.loads(body).get("message", body)
            except Exception:
                message = body or str(exc)
            raise RuntimeError(message)

    def require_login(self):
        if self.token and self.current_user:
            return True
        messagebox.showinfo("Login needed", "Login or create an account first.")
        self.show_page("account")
        return False

    def register(self):
        username = self.username_entry.get().strip()
        email = self.email_entry.get().strip()
        password = self.password_entry.get()
        try:
            response = self.api_request("/auth/register", "POST", {"username": username, "email": email, "password": password}, auth=False)
            self.token = response["token"]
            self.current_user = response["user"]
            self.save_session()
            self.update_account_status()
            self.result_var.set("Account created. Welcome to the arena.")
        except Exception as exc:
            messagebox.showerror("Account", str(exc))

    def login(self):
        username = self.username_entry.get().strip()
        email = self.email_entry.get().strip()
        password = self.password_entry.get()
        identity = username or email
        payload = {"username": identity, "password": password}
        if email and not username:
            payload = {"email": email, "password": password}
        try:
            response = self.api_request("/auth/login", "POST", payload, auth=False)
            self.token = response["token"]
            self.current_user = response["user"]
            self.save_session()
            self.update_account_status()
            self.result_var.set(f"Logged in as {self.current_user['username']}.")
        except Exception as exc:
            messagebox.showerror("Account", str(exc))

    def logout(self):
        self.clear_session()
        self.update_account_status()
        self.result_var.set("Logged out.")

    def update_account_status(self):
        if not hasattr(self, "account_status"):
            return
        if self.current_user:
            coins = self.current_user.get("coins", 0)
            rating = self.current_user.get("rank_rating", self.current_user.get("rating", 1000))
            self.account_status.configure(text=f"Signed in as {self.current_user['username']} | Coins {coins} | Rating {rating}")
        else:
            self.account_status.configure(text="Not signed in")

    def play_game(self, game_type, choice):
        if not self.require_login():
            return
        try:
            response = self.api_request("/games/quick-play", "POST", {"game_type": game_type, "choice": choice})
            self.current_user = response.get("user", self.current_user)
            self.save_session()
            self.update_account_status()
            self.result_var.set(self.format_game_result(response))
        except Exception as exc:
            messagebox.showerror("Game", str(exc))

    def format_game_result(self, response):
        outcome = response.get("outcome", "ready").upper()
        reward = response.get("reward", 0)
        pieces = [f"{outcome} | +{reward} coins"]
        for key in ["player_choice", "opponent_choice", "total", "reels", "answer", "player_total", "dealer_total"]:
            if key in response:
                pieces.append(f"{key.replace('_', ' ').title()}: {response[key]}")
        return "     ".join(pieces)

    def search_users(self):
        if not self.require_login():
            return
        for child in self.search_results.winfo_children():
            child.destroy()
        query = self.friend_search.get().strip()
        try:
            response = self.api_request(f"/users/search?q={urllib.parse.quote(query)}")
            users = response.get("users", [])
            if not users:
                tk.Label(self.search_results, text="No players found.").grid(row=0, column=0, sticky="w")
            for row, user in enumerate(users):
                tk.Label(self.search_results, text=f"{user['username']} | {user['rank_tier']}").grid(row=row, column=0, sticky="w", pady=4)
                tk.Button(self.search_results, text="Add", command=lambda u=user: self.add_friend(u)).grid(row=row, column=1, padx=8)
            self.apply_theme()
        except Exception as exc:
            messagebox.showerror("Friends", str(exc))

    def add_friend(self, user):
        try:
            self.api_request("/friends/request", "POST", {"friend_id": user["id"]})
            messagebox.showinfo("Friends", f"Friend request sent to {user['username']}.")
            self.refresh_social()
        except Exception as exc:
            messagebox.showerror("Friends", str(exc))

    def refresh_social(self):
        if not self.token:
            return
        try:
            friends = self.api_request("/friends").get("friends", [])
            requests = self.api_request("/friends/requests").get("incoming", [])
            self.render_friends(friends, requests)
        except Exception:
            pass

    def render_friends(self, friends, requests):
        for panel in [self.friend_list, self.request_list]:
            for child in panel.winfo_children():
                child.destroy()

        if not friends:
            tk.Label(self.friend_list, text="No friends yet.").grid(row=0, column=0, sticky="w")
        for row, friend in enumerate(friends):
            tk.Label(self.friend_list, text=f"{friend['username']} | {friend['rank_tier']}").grid(row=row, column=0, sticky="w", pady=4)
            tk.Button(self.friend_list, text="Chat", command=lambda f=friend: self.open_chat(f)).grid(row=row, column=1, padx=8)

        if requests:
            tk.Label(self.request_list, text="Incoming Requests", font=("Segoe UI", 12, "bold")).grid(row=0, column=0, sticky="w", pady=(10, 4))
        for row, item in enumerate(requests, start=1):
            player = item["from"]
            tk.Label(self.request_list, text=player["username"]).grid(row=row, column=0, sticky="w", pady=4)
            tk.Button(self.request_list, text="Accept", command=lambda rid=item["friendship_id"]: self.accept_friend(rid)).grid(row=row, column=1, padx=8)
        self.apply_theme()

    def accept_friend(self, friendship_id):
        try:
            self.api_request(f"/friends/{friendship_id}/accept", "POST", {})
            self.refresh_social()
        except Exception as exc:
            messagebox.showerror("Friends", str(exc))

    def open_chat(self, friend):
        self.current_friend = friend
        self.chat_partner_label.configure(text=f"Chatting with {friend['username']}")
        self.show_page("chat")
        self.load_messages()

    def load_messages(self):
        if not self.current_friend:
            return
        try:
            response = self.api_request(f"/chat/{self.current_friend['id']}/messages")
            self.chat_text.configure(state=tk.NORMAL)
            self.chat_text.delete("1.0", tk.END)
            for message in response.get("messages", []):
                speaker = "You" if message["direction"] == "sent" else self.current_friend["username"]
                self.chat_text.insert(tk.END, f"{speaker}: {message['message']}\n")
            self.chat_text.configure(state=tk.DISABLED)
        except Exception as exc:
            messagebox.showerror("Chat", str(exc))

    def send_message(self):
        if not self.current_friend:
            messagebox.showinfo("Chat", "Pick a friend first.")
            return
        message = self.chat_entry.get().strip()
        if not message:
            return
        try:
            self.api_request(f"/chat/{self.current_friend['id']}/messages", "POST", {"message": message})
            self.chat_entry.delete(0, tk.END)
            self.load_messages()
        except Exception as exc:
            messagebox.showerror("Chat", str(exc))

    def on_close(self):
        self.root.destroy()


def main():
    root = tk.Tk()
    app = GameBotApp(root)
    root.protocol("WM_DELETE_WINDOW", app.on_close)
    root.mainloop()


if __name__ == "__main__":
    main()
