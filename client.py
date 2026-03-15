
import socket
import threading
import queue
import os
import time
import tkinter as tk
from tkinter import scrolledtext, simpledialog, messagebox, filedialog, ttk

HOST     = '127.0.0.1'  # !!!!must be replaced with the IP address of the laptop that will host the SERVER!!!!
TCP_PORT = 1234
UDP_PORT = 1235

# ── Colour palette (dark blue theme) ─────────────────────────────────────────
BG       = "#1a1a2e"   # window background
PANEL    = "#16213e"   # sidebar / card
ACCENT   = "#0f3460"   # button background
HL       = "#e94560"   # red highlight (errors, logout)
GREEN    = "#4ecca3"   # online indicator / success
GOLD     = "#f5a623"   # notifications / typing indicator
TEXT     = "#eaeaea"   # primary text
MUTED    = "#7a7a9a"   # secondary text
CHAT_BG  = "#0d0d1a"   # chat display background
ENTRY_BG = "#1e1e35"   # input field background


class NetworkersChatApp:

    def __init__(self):
        # ── Networking ────────────────────────────────────────────────────
        self.client     = None   # TCP socket to the server
        self.p2p_socket = None   # TCP socket that accepts incoming P2P conns
        self.udp_socket = None   # UDP socket for typing notifications
        self.username   = None
        self.udp_port   = None

        # ── Queues ───────────────────────────────────────────────────────
        # display_queue: all incoming server messages, polled on main thread
        self.display_queue       = queue.Queue()
        # peer_incoming_queue: new inbound P2P connections waiting to be accepted
        self.peer_incoming_queue = queue.Queue()
        # pending peer name: set when we send GET_PEER: and wait for the reply
        self._pending_peer = None

        # ── State ────────────────────────────────────────────────────────
        self.my_groups = []          # groups this user is in
        # typing timer per target (group name or peer name)
        self._typing_timers: dict = {}
        self.last_udp_sent = 0       # throttle outgoing UDP packets

        # ── Root window ──────────────────────────────────────────────────
        self.root = tk.Tk()
        self.root.title("Networkers Chat")
        self.root.geometry("960x600")
        self.root.configure(bg=BG)
        self.root.resizable(True, True)

        self._build_login()

    # =========================================================================
    #  LOGIN SCREEN
    # =========================================================================

    def _build_login(self):
        self._login_frame = tk.Frame(self.root, bg=BG)
        self._login_frame.place(relx=0.5, rely=0.5, anchor="center")

        # Logo / title
        tk.Label(self._login_frame, text="◈  NETWORKERS",
                 font=("Arial", 26, "bold"), fg=GREEN, bg=BG).pack(pady=(0, 4))
        tk.Label(self._login_frame, text="WhatsApp? We do it better 😎",
                 font=("Arial", 10), fg=MUTED, bg=BG).pack(pady=(0, 28))

        # Card
        card = tk.Frame(self._login_frame, bg=PANEL, padx=36, pady=32)
        card.pack()

        tk.Label(card, text="Username", font=("Arial", 11, "bold"),
                 fg=TEXT, bg=PANEL).pack(anchor="w")

        self._user_entry = tk.Entry(
            card, font=("Arial", 13), width=26,
            bg=ENTRY_BG, fg=TEXT, insertbackground=TEXT,
            relief="flat", bd=0)
        self._user_entry.pack(ipady=8, pady=(4, 18))
        self._user_entry.bind("<Return>", lambda _: self._do_login())
        self._user_entry.focus()

        tk.Button(
            card, text="Join Chat →", font=("Arial", 12, "bold"),
            bg=GREEN, fg=BG, relief="flat", padx=28, pady=10,
            cursor="hand2", command=self._do_login).pack(fill="x")

        self._login_err = tk.Label(
            card, text="", font=("Arial", 10),
            fg=HL, bg=PANEL)
        self._login_err.pack(pady=(10, 0))

    def _do_login(self):
        username = self._user_entry.get().strip()
        if not username:
            self._login_err.config(text="Username cannot be empty.")
            return

        # TCP connection to server
        self.client = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        try:
            self.client.connect((HOST, TCP_PORT))
        except Exception as e:
            self._login_err.config(text=f"Cannot reach server: {e}")
            return

        # P2P listening socket (OS assigns a free port)
        self.p2p_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.p2p_socket.bind(("0.0.0.0", 0))
        self.p2p_socket.listen()
        peer_port = self.p2p_socket.getsockname()[1]

        # UDP socket for typing indicators
        self.udp_socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self.udp_socket.bind(("0.0.0.0", 0))
        self.udp_port = self.udp_socket.getsockname()[1]

        # Send login handshake: username:p2p_port:udp_port
        self.client.sendall(f"{username}:{peer_port}:{self.udp_port}".encode())
        response = self.client.recv(2048).decode().strip()

        if response.startswith("ERROR"):
            self._login_err.config(text=response.split(":", 1)[1] if ":" in response else response)
            self.client.close()
            self.p2p_socket.close()
            self.udp_socket.close()
            return

        # Login success
        self.username = username
        self.root.title(f"Networkers  ·  {username}")

        # Start background threads
        threading.Thread(target=self._listen_server,  daemon=True).start()
        threading.Thread(target=self._listen_udp,     daemon=True).start()
        threading.Thread(target=self._accept_peers,   daemon=True).start()

        # Switch to main screen
        self._login_frame.destroy()
        self._build_main()

        # Begin polling the display queue
        self.root.after(100, self._poll)

        # Fetch online users right away
        self._cmd_list_users()

    # =========================================================================
    #  MAIN SCREEN
    # =========================================================================

    def _build_main(self):

        # ── Top bar ───────────────────────────────────────────────────────
        topbar = tk.Frame(self.root, bg=ACCENT, height=46)
        topbar.pack(fill="x")
        topbar.pack_propagate(False)

        tk.Label(topbar, text="◈  NETWORKERS",
                 font=("Arial", 14, "bold"), fg=GREEN, bg=ACCENT).pack(
                 side="left", padx=18, pady=12)
        tk.Label(topbar, text=f"● {self.username}",
                 font=("Arial", 11), fg=TEXT, bg=ACCENT).pack(side="right", padx=18)

        # ── Body ──────────────────────────────────────────────────────────
        body = tk.Frame(self.root, bg=BG)
        body.pack(fill="both", expand=True)

        # ── SIDEBAR ───────────────────────────────────────────────────────
        sidebar = tk.Frame(body, bg=PANEL, width=210)
        sidebar.pack(side="left", fill="y")
        sidebar.pack_propagate(False)

        def section(text):
            tk.Label(sidebar, text=text, font=("Arial", 8, "bold"),
                     fg=GREEN, bg=PANEL).pack(anchor="w", padx=12, pady=(14, 3))

        def sidebar_btn(label, color, cmd):
            f = tk.Frame(sidebar, bg=PANEL)
            f.pack(fill="x", padx=10, pady=2)
            tk.Button(f, text=label, font=("Arial", 9),
                      bg=color, fg=TEXT, relief="flat",
                      activebackground=color, activeforeground=TEXT,
                      padx=8, pady=5, anchor="w", width=22,
                      cursor="hand2", command=cmd).pack(fill="x")

        # Online users list
        section("ONLINE USERS")
        self._users_lb = tk.Listbox(
            sidebar, bg=ENTRY_BG, fg=TEXT, selectbackground=ACCENT,
            font=("Consolas", 10), relief="flat", bd=0,
            height=6, activestyle="none", highlightthickness=0)
        self._users_lb.pack(fill="x", padx=10)

        # My groups list
        section("MY GROUPS")
        self._groups_lb = tk.Listbox(
            sidebar, bg=ENTRY_BG, fg=TEXT, selectbackground=ACCENT,
            font=("Consolas", 10), relief="flat", bd=0,
            height=5, activestyle="none", highlightthickness=0)
        self._groups_lb.pack(fill="x", padx=10)

        tk.Frame(sidebar, bg=PANEL, height=10).pack()

        sidebar_btn("↻  Refresh Users",    ACCENT, self._cmd_list_users)
        sidebar_btn("✉  Chat with Peer",   "#1b5e20", self._cmd_connect_peer)
        sidebar_btn("+  Create Group",     "#1a237e", self._cmd_create_group)
        sidebar_btn("→  Join Group",       "#1a237e", self._cmd_join_group)
        sidebar_btn("✗  Leave Group",      "#4a1010", self._cmd_leave_group)

        # Spacer then logout at the bottom
        tk.Frame(sidebar, bg=PANEL).pack(expand=True, fill="y")
        sidebar_btn("⏻  Logout",           HL,        self._cmd_logout)

        # ── CHAT AREA ─────────────────────────────────────────────────────
        chat_col = tk.Frame(body, bg=BG)
        chat_col.pack(side="left", fill="both", expand=True, padx=(2, 0))

        # Group selector bar
        sel_bar = tk.Frame(chat_col, bg=PANEL, height=38)
        sel_bar.pack(fill="x")
        sel_bar.pack_propagate(False)
        tk.Label(sel_bar, text="Group:", fg=MUTED, bg=PANEL,
                 font=("Arial", 10)).pack(side="left", padx=(12, 6), pady=8)

        self._active_group = tk.StringVar(value="(none)")
        self._group_menu = tk.OptionMenu(sel_bar, self._active_group, "(none)")
        self._group_menu.config(
            bg=ACCENT, fg=TEXT, activebackground=ACCENT, activeforeground=GREEN,
            relief="flat", font=("Arial", 10), borderwidth=0,
            highlightthickness=0, cursor="hand2")
        self._group_menu["menu"].config(bg=PANEL, fg=TEXT,
                                        activebackground=ACCENT, activeforeground=TEXT)
        self._group_menu.pack(side="left")

        # Chat display
        self._chat = scrolledtext.ScrolledText(
            chat_col, state="disabled", wrap="word",
            bg=CHAT_BG, fg=TEXT, font=("Consolas", 11),
            relief="flat", bd=0, padx=12, pady=10,
            selectbackground=ACCENT)
        self._chat.pack(fill="both", expand=True, padx=4, pady=4)

        # Colour tags for the chat display
        self._chat.tag_config("server",   foreground="#5bc8f5",
                              font=("Consolas", 10, "italic"))
        self._chat.tag_config("own",      foreground=GREEN)
        self._chat.tag_config("other",    foreground=TEXT)
        self._chat.tag_config("error",    foreground=HL,
                              font=("Consolas", 10, "italic"))
        self._chat.tag_config("ack",      foreground="#888",
                              font=("Consolas", 10, "italic"))
        self._chat.tag_config("file",     foreground=GOLD,
                              font=("Consolas", 10))
        self._chat.tag_config("typing",   foreground=GOLD,
                              font=("Consolas", 10, "italic"))

        # Typing indicator label
        self._typing_label = tk.Label(
            chat_col, text="", font=("Arial", 9, "italic"),
            fg=GOLD, bg=BG, anchor="w")
        self._typing_label.pack(fill="x", padx=8)

        # Message input row
        input_row = tk.Frame(chat_col, bg=PANEL, height=50)
        input_row.pack(fill="x", padx=4, pady=(0, 4))
        input_row.pack_propagate(False)

        self._msg_entry = tk.Entry(
            input_row, font=("Arial", 12),
            bg=ENTRY_BG, fg=TEXT, insertbackground=TEXT,
            relief="flat", bd=0)
        self._msg_entry.pack(side="left", fill="both", expand=True,
                             padx=(10, 6), pady=10)
        self._msg_entry.bind("<Return>",  lambda _: self._cmd_send_group())
        self._msg_entry.bind("<KeyPress>", self._on_group_key)

        tk.Button(input_row, text="📎", font=("Arial", 13),
                  bg=PANEL, fg=GOLD, relief="flat",
                  activebackground=PANEL, cursor="hand2",
                  command=self._cmd_send_file_group).pack(side="left", padx=(0, 4))

        tk.Button(input_row, text="Send",
                  font=("Arial", 11, "bold"),
                  bg=GREEN, fg=BG, relief="flat",
                  activebackground=GREEN, cursor="hand2",
                  padx=18, command=self._cmd_send_group).pack(
                  side="right", padx=10, pady=10)

    # =========================================================================
    #  BACKGROUND THREADS
    # =========================================================================

    def _listen_server(self):
        """
        Receives all TCP messages from the server.
        FILE: messages are handled inline (binary recv).
        Everything else is decoded and pushed to display_queue.
        """
        while True:
            try:
                raw = self.client.recv(4096)
                if not raw:
                    self.display_queue.put("SERVER:Disconnected from server.")
                    break

                # Binary file forwarded from server to group
                if raw.startswith(b"FILE:"):
                    self._receive_file_from_server(raw)
                    continue

                message = raw.decode('utf-8').strip()
                if message:
                    self.display_queue.put(message)
            except Exception as e:
                self.display_queue.put(f"SERVER:Connection lost — {e}")
                break

    def _receive_file_from_server(self, raw_header_bytes):
        """
        Called when a FILE: message arrives from the server.
        Reads exactly filesize bytes, saves to ./downloads/, notifies GUI.
        Protocol: FILE:groupname:filename:filesize
        """
        try:
            # The first recv may contain both the header and the start of file data
            if b"\n" in raw_header_bytes:
                header_raw, leftover = raw_header_bytes.split(b"\n", 1)
            else:
                header_raw = raw_header_bytes
                leftover   = b""

            header = header_raw.decode('utf-8')
            parts  = header.split(":", 3)
            if len(parts) < 4:
                return

            _, groupname, filename, filesize_str = parts
            filesize = int(filesize_str)

            os.makedirs("downloads", exist_ok=True)
            filepath = os.path.join("downloads", filename)

            received = len(leftover)
            with open(filepath, "wb") as f:
                if leftover:
                    f.write(leftover)
                while received < filesize:
                    chunk = self.client.recv(min(4096, filesize - received))
                    if not chunk:
                        break
                    f.write(chunk)
                    received += len(chunk)

            self.display_queue.put(
                f"FILE_RECEIVED:{groupname}:{filename}:{filepath}"
            )
        except Exception as e:
            self.display_queue.put(f"SYSTEM:File receive error — {e}")

    def _listen_udp(self):
        """
        Receives UDP typing-indicator packets from the server.
        Format: event:sender  (event = "typing" or "Stopped_typing")
        """
        while True:
            try:
                data, _ = self.udp_socket.recvfrom(2048)
                msg     = data.decode().strip()
                parts   = msg.split(":", 1)
                if len(parts) == 2:
                    event, sender = parts[0].strip(), parts[1].strip()
                    self.display_queue.put(f"UDP:{event}:{sender}")
            except Exception:
                break

    def _accept_peers(self):
        """
        Accepts incoming P2P TCP connections on a background thread.
        Reads the USERNAME handshake, queues the socket for the main thread.
        """
        while True:
            try:
                peer_sock, address = self.p2p_socket.accept()
                
                handshake = peer_sock.recv(2048).decode()
                peer_name = (handshake.split(":", 1)[1].strip()
                             if handshake.startswith("USERNAME:") else address[0])
                self.peer_incoming_queue.put((peer_sock, peer_name))
            except Exception:
                break

    # =========================================================================
    #  MAIN-THREAD POLLING LOOP
    # =========================================================================

    def _poll(self):
        """Drains display_queue and peer_incoming_queue every 100 ms."""
        # Process server / system messages
        try:
            while True:
                msg = self.display_queue.get_nowait()
                self._dispatch(msg)
        except queue.Empty:
            pass

        # Prompt user for incoming P2P connections
        try:
            while True:
                peer_sock, peer_name = self.peer_incoming_queue.get_nowait()
                answer = messagebox.askyesno(
                    "Incoming Chat", f"{peer_name} wants to chat. Accept?")
                if answer:
                    self._open_peer_window(peer_sock, peer_name, send_handshake=False)
                else:
                    peer_sock.close()
        except queue.Empty:
            pass

        self.root.after(100, self._poll)

    # =========================================================================
    #  MESSAGE DISPATCHER
    # =========================================================================

    def _dispatch(self, message: str):
        """Route every incoming message to the correct GUI action."""

        # ── UDP typing indicator ──────────────────────────────────────────
        if message.startswith("UDP:"):
            _, event, sender = message.split(":", 2)
            if event == "typing":
                self._show_typing(sender)
            else:
                self._clear_typing(sender)
            return

        # ── FILE received from server ─────────────────────────────────────
        if message.startswith("FILE_RECEIVED:"):
            _, groupname, filename, filepath = message.split(":", 3)
            self._append(f"📎  [{groupname}] File received: '{filename}'  →  {filepath}", "file")
            return

        # ── System internal disconnect message ────────────────────────────
        if message.startswith("SYSTEM:"):
            self._append(f"⚠  {message[7:]}", "error")
            return

        # ── Group chat message: <groupname>\nusername: text ───────────────
        if message.startswith("<"):
            lines   = message.split("\n", 1)
            gname   = lines[0][1:-1]   # strip < >
            content = lines[1] if len(lines) > 1 else ""
            if ": " in content:
                sender, text = content.split(": ", 1)
            else:
                sender, text = "?", content
            tag = "own" if sender == self.username else "other"
            self._append(f"[{gname}]  {sender}: {text}", tag)
            return

        # ── ACK:LIST_USERS:user1,user2 ────────────────────────────────────
        if message.startswith("ACK:LIST_USERS:"):
            users_str = message[len("ACK:LIST_USERS:"):]
            users = [u.strip() for u in users_str.split(",") if u.strip()]
            self._users_lb.delete(0, "end")
            for u in users:
                dot = "● " if u == self.username else "○ "
                self._users_lb.insert("end", dot + u)
            return

        # ── ACK:<ip>:<port>  →  peer found, open window ───────────────────
        if message.startswith("ACK:") and self._pending_peer:
            parts = message.split(":")
            # Distinguish from other ACKs by checking part count and IP-like pattern
            if len(parts) == 3 and parts[1].count(".") == 3:
                peer_ip   = parts[1]
                peer_port = int(parts[2])
                target    = self._pending_peer
                self._pending_peer = None
                try:
                    conn = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                    conn.connect((peer_ip, peer_port))
                    self._open_peer_window(conn, target, send_handshake=True)
                except Exception as e:
                    self._append(f"✘ Could not reach {target}: {e}", "error")
                return

        # ── ACK: group created → update sidebar ───────────────────────────
        if message.startswith("ACK:") and "created" in message.lower():
            self._append(f"✔  {message[4:]}", "ack")
            return

        # ── ACK: joined group → update sidebar ────────────────────────────
        if message.startswith("ACK:") and "joined" in message.lower():
            # Extract group name if possible
            self._append(f"✔  {message[4:]}", "ack")
            return

        # ── ACK: exited group → update sidebar ────────────────────────────
        if message.startswith("ACK:") and "exited" in message.lower():
            self._append(f"✔  {message[4:]}", "ack")
            return

        # ── ACK: file sent ────────────────────────────────────────────────
        if message.startswith("ACK:") and "file" in message.lower():
            self._append(f"✔  {message[4:]}", "ack")
            return

        # ── Generic ACK ───────────────────────────────────────────────────
        if message.startswith("ACK:"):
            self._append(f"✔  {message[4:]}", "ack")
            return

        # ── ERROR ─────────────────────────────────────────────────────────
        if message.startswith("ERROR:"):
            self._append(f"✘  {message[6:]}", "error")
            return

        # ── SERVER: broadcast notifications ──────────────────────────────
        if message.startswith("SERVER:") or message.startswith("SERVER: "):
            text = message.split(":", 1)[1].strip()
            self._append(f"🔔  {text}", "server")
            # Auto-refresh users panel on join/leave events
            if "joined" in text or "left" in text:
                try:
                    self.client.sendall("LIST_USERS".encode())
                except Exception:
                    pass
            # Auto-add group if we just got invited and added
            if "added to" in text: #or "joined" in text.lower():
                try:
                    gname = text.split("added to '")[1].rstrip("'")
                    if gname and gname not in self.my_groups:
                        self.my_groups.append(gname)
                        self._groups_lb.insert("end", gname)
                        self._update_group_dropdown()
                except Exception:
                    pass
                #self._sync_groups_from_server()
            return

        # Fallback
        self._append(message, "other")

    # =========================================================================
    #  PEER CHAT WINDOW
    # =========================================================================

    def _open_peer_window(self, peer_sock, peer_name, send_handshake=False):
        """
        Opens a dedicated Toplevel window for a P2P session.
        Multiple windows can be open simultaneously.
        Each window has its own socket, stop_event, and recv thread.
        """
        win = tk.Toplevel(self.root)
        win.title(f"Chat  ·  {peer_name}")
        win.geometry("520x440")
        win.configure(bg=BG)

        # Peer chat display
        disp = scrolledtext.ScrolledText(
            win, state="disabled", wrap="word",
            bg=CHAT_BG, fg=TEXT, font=("Consolas", 11),
            relief="flat", bd=0, padx=12, pady=10)
        disp.pack(fill="both", expand=True, padx=4, pady=4)
        disp.tag_config("own",  foreground=GREEN)
        disp.tag_config("peer", foreground="#c8d8f5")
        disp.tag_config("info", foreground=MUTED, font=("Consolas", 10, "italic"))
        disp.tag_config("file", foreground=GOLD)

        # Typing indicator
        typing_lbl = tk.Label(win, text="", font=("Arial", 9, "italic"),
                              fg=GOLD, bg=BG, anchor="w")
        typing_lbl.pack(fill="x", padx=8)

        # Input row
        row = tk.Frame(win, bg=PANEL, height=50)
        row.pack(fill="x", padx=4, pady=(0, 4))
        row.pack_propagate(False)

        p_entry = tk.Entry(row, font=("Arial", 12),
                           bg=ENTRY_BG, fg=TEXT, insertbackground=TEXT,
                           relief="flat", bd=0)
        p_entry.pack(side="left", fill="both", expand=True,
                     padx=(10, 6), pady=10)

        stop_event = threading.Event()

        def append_win(text, tag="peer"):
            disp.config(state="normal")
            disp.insert("end", text + "\n", tag)
            disp.config(state="disabled")
            disp.see("end")

        # ── UDP typing for peer window ────────────────────────────────────
        peer_last_udp = [0]   # mutable container so inner function can write it

        def on_peer_key(event):
            # Send typing UDP notification to the peer (target = peer_name)
            now = time.time()
            if now - peer_last_udp[0] > 2:
                try:
                    self.udp_socket.sendto(
                        f"typing:{self.username}:{peer_name}".encode(),
                        (HOST, UDP_PORT))
                    peer_last_udp[0] = now
                except Exception:
                    pass
            # Reset inactivity timer
            if peer_name in self._typing_timers:
                self._typing_timers[peer_name].cancel()
            timer = threading.Timer(
                3.0, lambda: self.udp_socket.sendto(
                    f"Stopped_typing:{self.username}:{peer_name}".encode(),
                    (HOST, UDP_PORT)) if self.udp_socket else None)
            timer.daemon = True
            timer.start()
            self._typing_timers[peer_name] = timer

        p_entry.bind("<KeyPress>", on_peer_key)

        # ── Receive loop (background thread) ─────────────────────────────
        def recv_loop():
            while not stop_event.is_set():
                try:
                    raw = peer_sock.recv(4096)
                    if not raw:
                        win.after(0, lambda: append_win("[Peer disconnected]", "info"))
                        stop_event.set()
                        break

                    # P2P file transfer
                    if raw.startswith(b"FILE:"):
                        _receive_peer_file(raw)
                        continue

                    msg = raw.decode('utf-8')
                    if msg.startswith("USERNAME:"):
                        continue
                    win.after(0, lambda m=msg: append_win(m, "peer"))

                    # Show typing indicator in this window
                    if peer_name in self._typing_timers:
                        win.after(0, lambda: typing_lbl.config(
                            text=f"{peer_name} is typing…"))

                except Exception:
                    if not stop_event.is_set():
                        win.after(0, lambda: append_win("[Connection lost]", "info"))
                    stop_event.set()
                    break

        def _receive_peer_file(raw_bytes):
            """Receive a file sent by the peer over the P2P socket."""
            try:
                if b"\n" in raw_bytes:
                    header_raw, leftover = raw_bytes.split(b"\n", 1)
                else:
                    header_raw, leftover = raw_bytes, b""

                header = header_raw.decode('utf-8')
                parts  = header.split(":", 2)
                if len(parts) < 3:
                    return
                _, filename, filesize_str = parts
                filesize = int(filesize_str)

                os.makedirs("downloads", exist_ok=True)
                filepath = os.path.join("downloads", filename)
                received = len(leftover)
                with open(filepath, "wb") as f:
                    if leftover:
                        f.write(leftover)
                    while received < filesize:
                        chunk = peer_sock.recv(min(4096, filesize - received))
                        if not chunk:
                            break
                        f.write(chunk)
                        received += len(chunk)

                win.after(0, lambda fp=filepath, fn=filename:
                          append_win(f"📎  File received: '{fn}'  →  {fp}", "file"))
            except Exception as e:
                win.after(0, lambda: append_win(f"[File error: {e}]", "info"))

        # ── Send text ─────────────────────────────────────────────────────
        def send_msg(event=None):
            text = p_entry.get().strip()
            if not text:
                return
            try:
                peer_sock.sendall(f"{self.username}: {text}".encode())
                append_win(f"You: {text}", "own")
                p_entry.delete(0, "end")
            except Exception as e:
                append_win(f"[Send error: {e}]", "info")

        # ── Send file (P2P) ───────────────────────────────────────────────
        def send_file():
            filepath = filedialog.askopenfilename(parent=win, title="Send File")
            if not filepath:
                return
            try:
                filename = os.path.basename(filepath)
                filesize = os.path.getsize(filepath)
                peer_sock.sendall(f"FILE:{filename}:{filesize}".encode())
                with open(filepath, "rb") as f:
                    while chunk := f.read(4096):
                        peer_sock.sendall(chunk)
                append_win(f"📎  Sent file: '{filename}'", "file")
            except Exception as e:
                append_win(f"[File send error: {e}]", "info")

        # ── Close handler ─────────────────────────────────────────────────
        def on_close():
            stop_event.set()
            for t in list(self._typing_timers.values()):
                t.cancel()
            try:
                peer_sock.sendall(f"{self.username}: left the chat.".encode())
                peer_sock.close()
            except Exception:
                pass
            win.destroy()

        win.protocol("WM_DELETE_WINDOW", on_close)

        # Buttons
        tk.Button(row, text="📎", font=("Arial", 13),
                  bg=PANEL, fg=GOLD, relief="flat",
                  activebackground=PANEL, cursor="hand2",
                  command=send_file).pack(side="left", padx=(0, 4))

        tk.Button(row, text="Send", font=("Arial", 11, "bold"),
                  bg=GREEN, fg=BG, relief="flat",
                  activebackground=GREEN, cursor="hand2",
                  padx=18, command=send_msg).pack(side="right", padx=10, pady=10)

        p_entry.bind("<Return>", send_msg)

        # Handshake + start threads
        if send_handshake:
            peer_sock.sendall(f"USERNAME:{self.username}".encode())

        threading.Thread(target=recv_loop, daemon=True).start()

        append_win(f"Connected to {peer_name}.  Close window to end session.", "info")
        win.update_idletasks() 
        p_entry.focus_set()
        
        

    # =========================================================================
    #  ACTION HANDLERS  (wired to sidebar buttons and menu)
    # =========================================================================

    def _cmd_list_users(self):
        try:
            self.client.sendall("LIST_USERS".encode())
        except Exception:
            pass

    def _cmd_connect_peer(self):
        target = simpledialog.askstring(
            "Chat with Peer", "Enter the username:", parent=self.root)
        if not target:
            return
        self._pending_peer = target.strip()
        try:
            self.client.sendall(f"GET_PEER:{self._pending_peer}".encode())
        except Exception as e:
            self._append(f"✘  {e}", "error")
            self._pending_peer = None

    def _cmd_create_group(self):
        """Prompt for group name + optional initial members, send CREATE_GROUP."""
        dlg = tk.Toplevel(self.root)
        dlg.title("Create Group")
        dlg.geometry("320x200")
        dlg.configure(bg=BG)
        dlg.resizable(False, False)
        dlg.grab_set()

        tk.Label(dlg, text="Group name:", fg=TEXT, bg=BG,
                 font=("Arial", 10)).pack(padx=20, pady=(18, 2), anchor="w")
        name_e = tk.Entry(dlg, bg=ENTRY_BG, fg=TEXT,
                          insertbackground=TEXT, relief="flat", font=("Arial", 11))
        name_e.pack(fill="x", padx=20, ipady=6)
        name_e.focus()

        tk.Label(dlg, text="Initial members (comma-separated, optional):",
                 fg=MUTED, bg=BG, font=("Arial", 9)).pack(padx=20, pady=(10, 2), anchor="w")
        mem_e = tk.Entry(dlg, bg=ENTRY_BG, fg=TEXT,
                         insertbackground=TEXT, relief="flat", font=("Arial", 11))
        mem_e.pack(fill="x", padx=20, ipady=6)

        def do_create():
            name = name_e.get().strip()
            mems = mem_e.get().strip()
            if not name:
                return
            payload = f"CREATE_GROUP:{name}:{mems}:{self.username}"
            self.client.sendall(payload.encode())
            # Optimistically add to local sidebar
            if name not in self.my_groups:
                self.my_groups.append(name)
                self._groups_lb.insert("end", name)
                self._update_group_dropdown()
            dlg.destroy()

        tk.Button(dlg, text="Create", font=("Arial", 11, "bold"),
                  bg=GREEN, fg=BG, relief="flat", padx=16, pady=6,
                  cursor="hand2", command=do_create).pack(pady=14)
        name_e.bind("<Return>", lambda _: do_create())

    def _cmd_join_group(self):
        name = simpledialog.askstring("Join Group", "Group name:", parent=self.root)
        if not name:
            return
        self.client.sendall(f"JOIN_GROUP:{name.strip()}:{self.username}".encode())
        # Optimistically add to local sidebar
        if name not in self.my_groups:
            self.my_groups.append(name)
            self._groups_lb.insert("end", name)
            self._update_group_dropdown()

    def _cmd_leave_group(self):
        sel = self._groups_lb.curselection()
        if not sel:
            messagebox.showinfo("Select a Group",
                                "Click a group in the MY GROUPS list first.")
            return
        gname = self._groups_lb.get(sel[0])
        self.client.sendall(f"EXIT_GROUP:{gname}".encode())
        self.my_groups.remove(gname)
        self._groups_lb.delete(sel[0])
        self._update_group_dropdown()

    def _cmd_send_group(self):
        gname = self._active_group.get()
        if gname == "(none)":
            self._append("Create or join a group first.", "error")
            return
        text = self._msg_entry.get().strip()
        if not text:
            return
        self.client.sendall(f"GROUP_MSG:{gname}:{text}".encode())
        self._msg_entry.delete(0, "end")

    def _cmd_send_file_group(self):
        """Send a file to the active group via the server."""
        gname = self._active_group.get()
        if gname == "(none)":
            messagebox.showinfo("No Group", "Join or create a group first.")
            return
        filepath = filedialog.askopenfilename(title="Send File to Group")
        if not filepath:
            return
        try:
            filename = os.path.basename(filepath)
            filesize = os.path.getsize(filepath)
            # Updated FILE header includes groupname: FILE:groupname:filename:filesize
            self.client.sendall(f"FILE:{gname}:{filename}:{filesize}".encode())
            with open(filepath, "rb") as f:
                while chunk := f.read(4096):
                    self.client.sendall(chunk)
            self._append(f"📎  Sending '{filename}' to [{gname}]…", "file")
        except Exception as e:
            self._append(f"✘  File send failed: {e}", "error")

    def _cmd_logout(self):
        if messagebox.askyesno("Logout", "Leave the chat?"):
            try:
                self.client.sendall("EXIT_CHAT_SYSTEM".encode())
            except Exception:
                pass
            self.root.quit()

    # =========================================================================
    #  TYPING INDICATOR HELPERS
    # =========================================================================

    def _on_group_key(self, event):
        """Send a UDP typing notification when the user types in the group chat input."""
        gname = self._active_group.get()
        if gname == "(none)":
            return
        now = time.time()
        if now - self.last_udp_sent > 2:
            try:
                self.udp_socket.sendto(
                    f"typing:{self.username}:{gname}".encode(),
                    (HOST, UDP_PORT))
                self.last_udp_sent = now
            except Exception:
                pass
        # Reset 3-second inactivity timer
        key = f"group_{gname}"
        if key in self._typing_timers:
            self._typing_timers[key].cancel()
        timer = threading.Timer(3.0, self._stop_typing_udp, args=(gname,))
        timer.daemon = True
        timer.start()
        self._typing_timers[key] = timer

    def _stop_typing_udp(self, target):
        try:
            self.udp_socket.sendto(
                f"Stopped_typing:{self.username}:{target}".encode(),
                (HOST, UDP_PORT))
        except Exception:
            pass

    def _show_typing(self, sender):
        """Show '[sender] is typing…' label and auto-clear after 4 s."""
        self._typing_label.config(text=f"{sender} is typing…")
        key = f"clear_{sender}"
        if key in self._typing_timers:
            self._typing_timers[key].cancel()
        timer = threading.Timer(
            4.0,
            lambda: self.root.after(0,
                lambda: self._typing_label.config(text="")
                if self._typing_label.winfo_exists() else None))
        timer.daemon = True
        timer.start()
        self._typing_timers[key] = timer

    def _clear_typing(self, sender):
        key = f"clear_{sender}"
        if key in self._typing_timers:
            self._typing_timers[key].cancel()
        if self._typing_label.winfo_exists():
            self._typing_label.config(text="")

    # =========================================================================
    #  SIDEBAR HELPERS
    # =========================================================================

    def _update_group_dropdown(self):
        menu = self._group_menu["menu"]
        menu.delete(0, "end")
        if self.my_groups:
            for g in self.my_groups:
                menu.add_command(label=g,
                                 command=lambda v=g: self._active_group.set(v))
            if self._active_group.get() not in self.my_groups:
                self._active_group.set(self.my_groups[-1])
        else:
            self._active_group.set("(none)")

    def _sync_groups_from_server(self):
        """No-op placeholder — groups are added optimistically on create/join."""
        pass

    # =========================================================================
    #  CHAT DISPLAY HELPER
    # =========================================================================

    def _append(self, text: str, tag: str = "other"):
        self._chat.config(state="normal")
        self._chat.insert("end", text + "\n", tag)
        self._chat.config(state="disabled")
        self._chat.see("end")

    # =========================================================================
    #  ENTRY POINT
    # =========================================================================

    def run(self):
        self.root.mainloop()


# ─────────────────────────────────────────────────────────────────────────────

if __name__ == '__main__':
    NetworkersChatApp().run()
