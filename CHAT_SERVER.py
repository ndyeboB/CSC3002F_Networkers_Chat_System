# we are importing the required libaries
import socket
import threading
import json


HOST = "127.0.0.1"
PORT = 1234 # the range of use is 0 to 65
 # lets set a limit on the amount of people that can be a chat -- later we can build more capacity in our system

class CHAT_SERVER:
    online_clients = [] #list of  clients that are curently online and connected to the server
    groups = {} # group just to show group chat demonstartion



def work_with_client(client, username):
    
    threading.Thread(target=server_listening, args=(client, username)).start() # because we put the login implementation in main(), this function can just start the listener thread
   
    # this CREATES a NEW THREAD
    # that thread runs server_listening
    # SO EACH CLIENT HAS ITS OWN LOOP!!!!!
    # without this 1 client could talk but with it each client runs indepedently
    

# the server must actively listen for upcoming message from a client
def server_listening(client, username): # responsible of collecting the message
    
    while True:
        try:

            message = client.recv(2048).decode('utf-8') # listens for the message that the client wants to send
        except:
            print(f"{username} disconnected unexpectedly.")
            break

        if message =='':
            continue

        if message == "EXITING":

            if username in CHAT_SERVER.groups["default"]:
                CHAT_SERVER.groups["default"].remove(username)
            grp_broadcast = "SERVER: "+f"{username} has left the default group. Goodbye {username}!"
            lets_send_message_to_everyone(grp_broadcast, exclude_username=username)
            continue

        # Choice 1: Connect to friend (peer)
        if message.startswith("GET_PEER:"):
            
            _, target = message.split(":",1)
            peer_ip = None
            peer_port = None

            for user in CHAT_SERVER.online_clients:
                if user[0] == target:
                    peer_ip = user[2]
                    peer_port = user[3]
                    break
                    
            if peer_ip:
                client.sendall(f"ACK:{peer_ip}:{peer_port}".encode())
            else:
                client.sendall("ERROR:User not found".encode())

        #Choice 2: Listing all the online users
        elif message == "LIST_USERS":
            user_list =[]

            for user in CHAT_SERVER.online_clients:
                user_list.append(user[0])

            users = ", ".join(user_list)
            
            response = f"ACK:LIST_USERS: {users}"
            client.sendall(response.encode())


        #Choice 3: Create a new group
        elif message.startswith("CREATE_GROUP:"):
            _,groupname, members, creator = message.split(";",3)
            allMembers = members.strip().split(",")
            for member in allMembers:
                found = False
                for x in range(len(CHAT_SERVER.online_clients)):
                    if member == CHAT_SERVER.online_clients[x][0]:
                        found = True
                        continue
                       
            if not found:
                client.sendall(member+ " could not be added to the group".encode())
                allMembers.remove(member)

            if creator not in allMembers:
                allMembers.append(creator)
            
            if groupname in CHAT_SERVER.groups:
                client.sendall(f"ERROR:Group {groupname} already exists.".encode())
            else:
                #We add the group to the dictionary
                CHAT_SERVER.groups.append(groupname)
                CHAT_SERVER.groups[groupname].append(allMembers)

            send_to_group("You have been added to "+ groupname, groupname)
            client.sendall(f"ACK:Group {groupname} has been successfully created.".encode())


        #Choice 4: Join an existing grup
        elif message.startswith("JOIN_GROUP:"):
            _, groupname, newMember = message.split(":",2)

            if groupname not in CHAT_SERVER.groups:
                client.sendall(f"ERROR: Group {groupname} does not exist.".encode())
            else:
                if newMember not in CHAT_SERVER.groups[groupname]:
                    CHAT_SERVER.groups[groupname].append(newMember)
                    send_to_group(f"{newMember} has been added to the group {groupname}", groupname)   
                    client.sendall(f"ACK:You have been successfully added to the group {groupname}".encode())
                else:
                    client.sendall(f"ACK:You are already in the group {groupname}".encode())
                

        #Choice 5: Send message to a group
        elif message.startswith("GROUP_MSG:"):
            try:
                _,groupname,text= message.split(":",2)

                if groupname not in CHAT_SERVER.groups:
                    client.sendall(f"ERROR: The group {groupname} does not exist".encode())
                if username not in CHAT_SERVER.groups[groupname]:
                    client.sendall(f"ERROR: You are not in the group {groupname}".encode())

                for user, sock, ip, port, in CHAT_SERVER.online_clients:
                    if user in CHAT_SERVER.groups[groupname]:
                        try:
                            sock.sendall(f"<{groupname}>:{username}: {text}".encode())
                        except:
                            pass     
            except:
                client.sendall("ERROR:Invalid group message".encode())

        #Choice 6: The user leaves a group
        elif message.startswith("EXIT_GROUP:"):
            _,groupname = message.split(":",1)
            if groupname not in CHAT_SERVER.groups:
                client.sendall(f"ERROR: The group {groupname} does not exist".encode())
            if username not in CHAT_SERVER.groups[groupname]:
                client.sendall(f"ERROR: You are not in the group {groupname}".encode())
            else:
                CHAT_SERVER.groups[groupname].remove(username)
                send_to_group(f"{username} has exited the group {groupname}", groupname)
                client.sendall(f"ACK: You have exited the group {groupname}".encode())

        #Choice 7: The user leaves the whole chat system 
        elif message.startswith("EXIT_CHAT_SYSTEM"):
            client.sendall("SERVER:Exiting chat...".encode())

            for user, client_socket, ip, peer_port in CHAT_SERVER.online_clients:
                if user == username:
                    CHAT_SERVER.online_clients.remove((user, client_socket, ip, peer_port))
                    break

            for members in CHAT_SERVER.groups.values():
                if username in members:
                    members.remove(username)
            lets_send_message_to_everyone(f"{username} has left the chat system.", username)
            

    
    
# this is to send a message to a single client
# needs to be further implemented so the client can choose who to send a message to with peer to peer
# def lets_send_message_to_client(client, message):
#     client.sendall(message.encode()) # client = receiving client

# needs to be further implemented so we first initiate a seperate group chat to send to everyone
def lets_send_message_to_everyone(message, exclude_username=None): 
        for username, client_socket, ip, peer_port in CHAT_SERVER.online_clients:
            if username != exclude_username:   # this ensures that we broadcast to everyone except the user who sent it
                try:
                    client_socket.sendall(message.encode())
                except:
                    pass

def send_to_group(message, groupName):
    groups= getGroup()
    for group, members in groups:
        #look for specified group
        if groupName in group:
            for user in members:
                for username, client_socket, ip, peer_port in CHAT_SERVER.online_clients:
                    if user == username:
                        try:
                            client_socket.sendall(message.encode())
                        except:
                            pass

# def handleClient(client):
#     while True:
#         request = client.recv(2048).decode()
#         if request == "GET_GROUPS":
#             print("hey7")
#             groupArray = getGroup()
#             print(groupArray)
#             data = json.dumps(groupArray)

#             client.sendall(data.encode())
#             print("finished handle")
#             break


def getGroup():
    return CHAT_SERVER.groups

# main function
def main():
    # CONFIGURING OUR SERVER

    # we are now creating a socket by creating a socket objects
    server = socket.socket(socket.AF_INET, socket.SOCK_STREAM) # we are using TCP

    try:
        # attach the server with an address in the form of host IP and port
        server.bind((HOST, PORT))
        print(f"Running the server on {HOST} {PORT}")
        

    except:
        print(f"ERROR! The server cannot bind to host: {HOST} and port: {PORT}.")
        return

    server.listen()
    print("The server is listening for connections...")
    
    # this while loop will keep listening to client connections -- MUST RUN FOREVER
    while True:
        client, address = server.accept() # client = client socket
        # address = represents where client comes from
        print(f"Successfully connected to client: {address[0]} {address[1]}") # this port is the client's tcp conn to the server, not the listening port

        data = client.recv(2048).decode('utf-8') # wait for the username that yo may receive from the client
        username, peer_port = data.split(":")
        peer_port = int(peer_port)

        if username == "":
            print("ERROR:The username given by the client is empty!")
            client.close()
            continue # makes it got back to waiting...


        username_used = False
        for user in CHAT_SERVER.online_clients: # loop in the online_list to check if username already exists
            if user[0] == username:
                username_used = True
                break
        if username_used: # if the username has been found
            client.sendall("ERROR:Username has been already taken".encode())
            client.close()
            continue # makes it got back to waiting...

        
        CHAT_SERVER.online_clients.append((username, client, address[0], peer_port)) # we add the client to list
    
        client.sendall("\nACK:Login successful!\n".encode()) # we tell the client login is successful!
        
        entry_message = "SERVER: "+f"{username} has entered the chat system!"
        lets_send_message_to_everyone(entry_message, exclude_username=username) 
        # when a new user is added to the chat, every one else is notified
        
            
        
         # we create a thread for THIS client so  we go back to accepting new ones   
        threading.Thread(target=work_with_client, args=(client, username, )).start()  

if __name__ == '__main__':
    main()
