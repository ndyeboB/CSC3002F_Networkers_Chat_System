# ============================================================
# CHAT_SERVER.py  —  Networkers Chat  (Stage 3)
# Bugs fixed:
#   - Removed stale EXITING/default-group handler
#   - Fixed FILE: handler (groupname was undefined → crash)
#   - Removed duplicate EXIT_GROUP handler
#   - Fixed JOIN_GROUP sending both ACK and ERROR at once
#   - Fixed EXIT_CHAT_SYSTEM mutating list mid-loop
#   - Added SO_REUSEADDR for dev convenience
# ============================================================

import socket
import threading

HOST     = "0.0.0.0" # this ensures that the server can connect with external client
TCP_PORT = 1234
UDP_PORT = 1235

# UDP socket the server uses to forward typing notifications to clients
udp_socket_server = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)


class CHAT_SERVER:
    online_clients = []   # tuples: (username, tcp_socket, ip, p2p_tcp_port, udp_port)
    groups         = {}   # { groupname: [username, ...] }
    lock           = threading.Lock()   # protects shared state across threads


# ── Broadcast helpers ─────────────────────────────────────────────────────────

def lets_send_message_to_everyone(message, exclude_username=None):
    with CHAT_SERVER.lock:
        snapshot = list(CHAT_SERVER.online_clients)
    for username, client_socket, ip, peer_port, udp_port in snapshot:
        if username != exclude_username:
            try:
                client_socket.sendall(message.encode())
            except Exception:
                pass


def send_to_group(message, groupName, file_data=None):
    """Send a text message (and optional binary file payload) to every group member."""
    with CHAT_SERVER.lock:
        members  = list(CHAT_SERVER.groups.get(groupName, []))
        snapshot = list(CHAT_SERVER.online_clients)
    for username, client_socket, ip, peer_port, udp_port in snapshot:
        if username in members:
            try:
                client_socket.sendall(message.encode())
                if file_data:
                    client_socket.sendall(file_data)
            except Exception:
                pass


# ── Per-client listener ───────────────────────────────────────────────────────

def work_with_client(client, username):
    threading.Thread(target=server_listening, args=(client, username), daemon=True).start()


def server_listening(client, username):
    while True:
        try:
            message = client.recv(4096).decode('utf-8')
        except Exception:
            print(f"[SERVER] {username} disconnected unexpectedly.")
            _cleanup_user(client, username)
            break

        if not message:
            continue

        # ── GET_PEER:<target>  →  peer-to-peer signalling ─────────────────
        if message.startswith("GET_PEER:"):
            _, target = message.split(":", 1)
            peer_ip = peer_port_found = None
            with CHAT_SERVER.lock:
                for user, _, ip, p2p_port, __ in CHAT_SERVER.online_clients:
                    if user == target:
                        peer_ip, peer_port_found = ip, p2p_port
                        break
            if peer_ip:
                client.sendall(f"ACK:{peer_ip}:{peer_port_found}".encode())
            else:
                client.sendall(f"ERROR:User '{target}' not found".encode())

        # ── LIST_USERS ─────────────────────────────────────────────────────
        elif message == "LIST_USERS":
            with CHAT_SERVER.lock:
                users = [u[0] for u in CHAT_SERVER.online_clients]
            client.sendall(f"ACK:LIST_USERS:{','.join(users)}".encode())

        # ── CREATE_GROUP:<groupname>:<members>:<creator> ───────────────────
        elif message.startswith("CREATE_GROUP:"):
            parts = message.split(":", 3)
            if len(parts) < 4:
                client.sendall("ERROR:Invalid CREATE_GROUP format".encode())
                continue
            _, groupname, members_str, creator = parts
            all_members = [m.strip() for m in members_str.split(",") if m.strip()]
            if creator not in all_members:
                all_members.append(creator)

            with CHAT_SERVER.lock:
                if groupname in CHAT_SERVER.groups:
                    client.sendall(f"ERROR:Group '{groupname}' already exists".encode())
                    continue
                CHAT_SERVER.groups[groupname] = all_members

            send_to_group(f"SERVER:You have been added to '{groupname}'", groupname)
            client.sendall(f"ACK:Group '{groupname}' created successfully".encode())
            print(f"[SERVER] Group '{groupname}' created: {all_members}")

        # ── JOIN_GROUP:<groupname>:<username> ──────────────────────────────
        elif message.startswith("JOIN_GROUP:"):
            parts = message.split(":", 2)
            if len(parts) < 3:
                client.sendall("ERROR:Invalid JOIN_GROUP format".encode())
                continue
            _, groupname, new_member = parts
            with CHAT_SERVER.lock:
                if groupname not in CHAT_SERVER.groups:
                    client.sendall(f"ERROR:Group '{groupname}' does not exist".encode())
                    continue
                if new_member in CHAT_SERVER.groups[groupname]:
                    # BUG FIX: previously sent both ACK and ERROR here
                    client.sendall(f"ACK:You are already in '{groupname}'".encode())
                    continue
                CHAT_SERVER.groups[groupname].append(new_member)

            send_to_group(f"SERVER:{new_member} joined '{groupname}'", groupname)
            client.sendall(f"ACK:Joined '{groupname}' successfully".encode())

        # ── EXIT_GROUP:<groupname> ─────────────────────────────────────────
        elif message.startswith("EXIT_GROUP:"):
            _, groupname = message.split(":", 1)
            with CHAT_SERVER.lock:
                if groupname not in CHAT_SERVER.groups:
                    client.sendall(f"ERROR:Group '{groupname}' not found".encode())
                    continue
                if username not in CHAT_SERVER.groups[groupname]:
                    client.sendall(f"ERROR:You are not in '{groupname}'".encode())
                    continue
                CHAT_SERVER.groups[groupname].remove(username)

            send_to_group(f"SERVER:{username} left '{groupname}'", groupname)
            client.sendall(f"ACK:Exited '{groupname}'".encode())

        # ── GROUP_MSG:<groupname>:<text> ───────────────────────────────────
        elif message.startswith("GROUP_MSG:"):
            try:
                _, groupname, text = message.split(":", 2)
                with CHAT_SERVER.lock:
                    if groupname not in CHAT_SERVER.groups:
                        client.sendall(f"ERROR:Group '{groupname}' does not exist".encode())
                        continue
                    if username not in CHAT_SERVER.groups[groupname]:
                        client.sendall(f"ERROR:You are not in '{groupname}'".encode())
                        continue
                send_to_group(f"<{groupname}>\n{username}: {text}", groupname)
            except ValueError:
                client.sendall("ERROR:Invalid GROUP_MSG format".encode())

        # ── FILE:<groupname>:<filename>:<filesize> ─────────────────────────
        # BUG FIX: groupname was previously undefined — now parsed from the header.
        # Protocol: client sends  FILE:groupname:filename:filesize  then raw bytes.
        elif message.startswith("FILE:"):
            try:
                parts = message.split(":", 3)
                if len(parts) < 4:
                    client.sendall("ERROR:Invalid FILE header (expected FILE:group:name:size)".encode())
                    continue
                _, groupname, filename, filesize_str = parts
                filesize = int(filesize_str)

                with CHAT_SERVER.lock:
                    if groupname not in CHAT_SERVER.groups:
                        client.sendall(f"ERROR:Group '{groupname}' does not exist".encode())
                        continue
                    if username not in CHAT_SERVER.groups[groupname]:
                        client.sendall(f"ERROR:You are not in '{groupname}'".encode())
                        continue

                # Read exact filesize bytes off the TCP stream
                file_data = b""
                while len(file_data) < filesize:
                    chunk = client.recv(min(4096, filesize - len(file_data)))
                    if not chunk:
                        break
                    file_data += chunk

                # Forward header + bytes to every group member
                send_to_group(message, groupname, file_data)
                client.sendall(f"ACK:File '{filename}' sent to '{groupname}'".encode())

            except Exception as e:
                client.sendall(f"ERROR:File transfer failed — {e}".encode())

        # ── EXIT_CHAT_SYSTEM ───────────────────────────────────────────────
        elif message.startswith("EXIT_CHAT_SYSTEM"):
            client.sendall("ACK:Goodbye!".encode())
            # BUG FIX: _cleanup_user builds a new list instead of mutating mid-loop
            _cleanup_user(client, username)
            break

        # ── Unknown command ────────────────────────────────────────────────
        else:
            client.sendall("ERROR:Unknown command".encode())


def _cleanup_user(client_sock, username):
    """Remove a user from all server state and notify everyone."""
    with CHAT_SERVER.lock:
        CHAT_SERVER.online_clients = [
            u for u in CHAT_SERVER.online_clients if u[0] != username
        ]
        for members in CHAT_SERVER.groups.values():
            if username in members:
                members.remove(username)
    lets_send_message_to_everyone(f"SERVER:{username} left the chat.", username)
    try:
        client_sock.close()
    except Exception:
        pass


# ── UDP typing-indicator relay ────────────────────────────────────────────────

def listening_for_theUDP():
    """Listen for typing-indicator packets from clients and forward them."""
    while True:
        try:
            data, _ = udp_socket_server.recvfrom(2048)
            message = data.decode()
            parts = message.split(":")
            if len(parts) != 3:
                continue
            event, sender, target = parts
            pass_notification(event.strip(), sender.strip(), target.strip())
        except Exception as e:
            print(f"[SERVER] UDP error: {e}")


def pass_notification(event, sender, target):
    """Forward a typing notification to the target peer or group members."""
    with CHAT_SERVER.lock:
        snapshot = list(CHAT_SERVER.online_clients)
        groups   = dict(CHAT_SERVER.groups)

    for username, _, ip, __, udp_port in snapshot:
        if not udp_port or username == sender:
            continue
        if username == target:
            # Direct peer notification
            try:
                udp_socket_server.sendto(f"{event}:{sender}".encode(), (ip, udp_port))
            except Exception:
                pass
        elif target in groups and username in groups[target]:
            # Group notification — send to every other member
            try:
                udp_socket_server.sendto(f"{event}:{sender}".encode(), (ip, udp_port))
            except Exception:
                pass


# ── Main ──────────────────────────────────────────────────────────────────────

def main():
    server = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    server.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)

    try:
        server.bind((HOST, TCP_PORT))
        print(f"[SERVER] TCP listening on {HOST}:{TCP_PORT}")
        udp_socket_server.bind((HOST, UDP_PORT))
        print(f"[SERVER] UDP listening on {HOST}:{UDP_PORT}")
        threading.Thread(target=listening_for_theUDP, daemon=True).start()
    except Exception as e:
        print(f"[SERVER] Cannot start: {e}")
        return

    server.listen()
    print("[SERVER] Ready — waiting for clients...\n")

    while True:
        client, address = server.accept()
        print(f"[SERVER] Connection from {address[0]}:{address[1]}")

        try:
            data  = client.recv(2048).decode('utf-8')
            parts = data.split(":")
            if len(parts) == 2:
                username, peer_port = parts
                udp_port = None
            elif len(parts) == 3:
                username, peer_port, udp_port = parts
            else:
                client.sendall("ERROR:Bad login format".encode())
                client.close()
                continue

            peer_port = int(peer_port)
            udp_port  = int(udp_port) if udp_port else None
        except Exception:
            client.sendall("ERROR:Bad login format".encode())
            client.close()
            continue

        if not username:
            client.sendall("ERROR:Username cannot be empty".encode())
            client.close()
            continue

        with CHAT_SERVER.lock:
            taken = any(u[0] == username for u in CHAT_SERVER.online_clients)

        if taken:
            client.sendall("ERROR:Username already taken".encode())
            client.close()
            continue

        with CHAT_SERVER.lock:
            CHAT_SERVER.online_clients.append(
                (username, client, address[0], peer_port, udp_port)
            )

        client.sendall("\nACK:Login successful!\n".encode())
        lets_send_message_to_everyone(f"SERVER:{username} joined the chat!", username)
        print(f"[SERVER] '{username}' logged in.")

        threading.Thread(target=work_with_client, args=(client, username), daemon=True).start()


if __name__ == '__main__':
    main()
