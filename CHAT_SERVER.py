# we are importing the required libaries
import socket
import threading
import json


HOST = "127.0.0.1"
PORT = 1234 # the range of use is 0 to 65
 # lets set a limit on the amount of people that can be a chat -- later we can build more capacity in our system

class CHAT_SERVER:
    online_clients = [] # list of all clients that are curently online and connected to the server
    #groups = {"default": []} # default group just to show group chat demonstartion

    #creates the 2D array to store the groups
    groups= [["Nothing"]*2 for x in range(1)]

    @staticmethod         
    def groupExistence(groupName):
        print(CHAT_SERVER.groups)
        print("="+CHAT_SERVER.groups[0][0]+"=")
        Found = False
        for x in range(len(CHAT_SERVER.groups)):
            if groupName == CHAT_SERVER.groups[x][0]:
                Found = True
            else:
                continue
        return Found


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
        

        # Choice 2: Join default group
        elif message == "3":
            if username not in CHAT_SERVER.groups["default"]:

                CHAT_SERVER.groups["default"].append(username)
                client.sendall("SERVER:You have joined the default group.".encode())
                grp_broadcast = "SERVER: "+f"{username} has joined the default group!"
                lets_send_message_to_everyone(grp_broadcast, exclude_username=username)
            else:
                client.sendall("SERVER:You are already in the group.".encode())

        #The functionality of creating a new group
        elif message =="2":
            groupName =  client.recv(2048).decode('utf-8')
            members =  client.recv(2048).decode('utf-8')
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

            #if the group array has "Nothing", we add a new row to the groups
            for i in range(len(CHAT_SERVER.groups)):
                if CHAT_SERVER.groups[i][0] == "Nothing" or CHAT_SERVER.groups[i][1] =="Nothing":
                    CHAT_SERVER.groups[i][0] = groupName
                    CHAT_SERVER.groups[i][1] = allMembers
                    print(CHAT_SERVER.groups[i][0])
                    print(CHAT_SERVER.groups[i][1])

                else:
                    CHAT_SERVER.groups.append((groupName, allMembers))


            send_to_group("You have been added to "+ groupName, groupName)
            client.sendall(("Group "+ groupName+ " was successfully created.\n").encode())

        elif message == "4":
            handleClient(client)
            

        elif message =="5":
            client.sendall("SERVER:Exiting chat...".encode())

            CHAT_SERVER.online_clients = [
                u for u in CHAT_SERVER.online_clients if u[0] !=username # asked chat how to remove user from list 
            ]

            for x in range(len(CHAT_SERVER.groups)):
                members = CHAT_SERVER.groups[x][1]

                for y in range(len(members)):
                    if username == members[y]:
                        members.remove(username)
                        client.close()
                        break
        # else:
        #     if username in CHAT_SERVER.groups["default"]:
        #         group_message = f"{username}: {message}"
                
        #         send_to_default_group(group_message)
        #     else:
        #         client.sendall("SERVER:Join the default group first (option 2)".encode())



    
    
# this is to send a message to a single client
# needs to be further implemented so the client can choose who to send a message to with peer to peer
def lets_send_message_to_client(client, message):
    client.sendall(message.encode()) # client = receiving client

# needs to be further implemented so we first initiate a seperate group chat to send to everyone
def lets_send_message_to_everyone(message, exclude_username=None): 
        for username, client_socket, ip, peer_port in CHAT_SERVER.online_clients:
            if username != exclude_username:   # this ensures that we broadcast to everyone except the user who sent it
                try:
                    client_socket.sendall(message.encode())
                except:
                    pass


# def send_to_default_group(message):
#     for username, client_socket, ip, peer_port in CHAT_SERVER.online_clients:
#         if username in CHAT_SERVER.groups["default"]:
#             try:
#                 client_socket.sendall(message.encode()) # works the same way as the function lets_send_messages_to_client
#             except:
#                 pass

def send_to_group(message, groupName):
    #for username, client_socket in CHAT_SERVER.online_clients:
    groups= getGroup()
    for i in range(len(groups)):
        if groupName == groups[i][0]:
            for user in groups[i][1]:
                for username, client_socket, ip, peer_port in CHAT_SERVER.online_clients:
                    if user == username:
                        try:
                            client_socket.sendall(message.encode())
                        except:
                            pass

def handleClient(client):
    while True:
        request = client.recv(2048).decode()
        if request == "GET_GROUPS":
            print("hey7")
            groupArray = getGroup()
            print(groupArray)
            data = json.dumps(groupArray)

            client.sendall(data.encode())
            print("finished handle")
            break


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
            print("The username given by the client is empty!")
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
