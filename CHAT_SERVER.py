# we are importing the required libaries
import socket
import threading
import sys

HOST = "127.0.0.1"
PORT = 1234 # the range of use is 0 to 65535

CLIENT_LIMIT = 5 # lets set a limit on the amount of people that can be a chat -- later we can build more capacity in our system

class CHAT_SERVER:
    online_clients = [] # list of all clients that are curently online and connected to the serv

groups = {"default": []} # default group just to show group chat demonstartion



def work_with_client(client):
    # initial connection with the client

    while True:
        username = client.recv(2048).decode('utf-8') # wait for the username that yo may receive from the client
        
        if username == "":
            print("The username given by the client is empty!")


        username_used = False
        for user in CHAT_SERVER.online_clients: # loop in the online_list to check if username already exists
            if user[0] == username:
                username_used = True
                break
        if username_used: # if the username has been found
            client.send("ERROR:Username has been already taken".encode())
        else:
            CHAT_SERVER.online_clients.append((username, client)) # we add the client to list
            
            client.send("ACK:Login successful!\n".encode()) # we tell the client login is successful!
            entry_message = "SERVER: "+f"{username} has entered the chat system!"
            lets_send_message_to_everyone(entry_message, exclude_username=username) 
            # when a new user is added to the chat, every one else is notified
            break
        
    # this CREATES a NEW THREAD
    # that thread runs server_listening
    # SO EACH CLIENT HAS ITS OWN LOOP!!!!!
    # without this 1 client could talk but with it each client runs indepedently
    threading.Thread(target=server_listening, args=(client, username, )).start()


# the server must actively listen for upcoming message from a client
def server_listening(client, username): # responsible of collecting the message
    
    while True:
        try :
            message = client.recv(2048).decode('utf-8') # listens for the message that the client wants to send

        except OSError:
            print("Client is diconnected and socket is closed.")
            break


        if message =='':
            #main_message = username + ':' + message
            #lets_send_message_to_everyone(main_message)
            continue

        if message == "EXIT":
            print(username, "has disconnected.")

            grp_broadcast = "SERVER: "+f"{username} has left the default group. Goodbye {username}!"
            lets_send_message_to_everyone(grp_broadcast, exclude_username=username)
            groups.remove(client)
            client.close()
            break

        # Choice 1: Connect to friend (peer)
        if message == "1":
            client.send("SERVER:Zamashengu is still working on this feature!".encode())
        # Choice 2: Join default group
        elif message == "2":
            if username not in groups["default"]: # check if you are not in the group already

                groups["default"].append(username)
                client.send("SERVER:You have joined the default group.".encode())
            else:
                client.send("SERVER:You are already in the group.".encode())

        elif message =="4":
            
            for user in CHAT_SERVER.online_clients:
                    
                    if user[1] == client:

                        CHAT_SERVER.online_clients.remove(user)
                        print(f"Exiting system....\nGoodbye {username}! Hope to see you soon!\n")
                        
            client.close()           
            break
        
        
        # user has already pressed a option, --> default group
        else:
            if username in groups["default"]:
                group_message = f"{username}: {message}"
                grp_broadcast = "SERVER: "+f"{username} has entered the default group!"
                lets_send_message_to_everyone(grp_broadcast, exclude_username=username)
                send_to_default_group(group_message)
            else:
                client.send("SERVER:Join the default group first (option 2)".encode())
            
    
    
# this is to send a message to a single client
# needs to be further implemented so the client can choose who to send a message to with peer to peer
def lets_send_message_to_client(client, message):
    client.sendall(message.encode()) # client = receiving client

# needs to be further implemented so we first initiate a seperate group chat to send to everyone
def lets_send_message_to_everyone(message, exclude_username=None): 
        for username, client_socket in CHAT_SERVER.online_clients:
            try:
                if username != exclude_username:   # this ensures that we broadcast to everyone except the user who sent it
                    client_socket.sendall(message.encode())

            except:
                print("Removing disconnected client")

                if client_socket in CHAT_SERVER.online_clients:
                    CHAT_SERVER.online_clients.remove(client_socket)

def handleFile(client, headers, groupMembers):
    fileSize = int(headers["Filesize"]) 
    fileData= b''
    remaining= fileSize

    while remaining > 0:
        chunk = client.recv(min(2048))
        fileData+=chunk
        remaining-= len(chunk)

def send_to_default_group(message):
    for user in CHAT_SERVER.online_clients:
        username = user[0]
        client_socket = user[1]

        if username in groups["default"]:
            client_socket.sendall(message.encode()) # works the same way as the function lets_send_messages_to_client

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
        print(f"ERROR! The server cannot bind to host: {HOST} and port: {PORT}. Please try again!")


    server.listen(CLIENT_LIMIT)
    print("The server is listening for a connection...")
    
    # this while loop will keep listening to client connections
    while True:
        client, address = server.accept() # client = client socket
        # address = represents where client comes from
        print(f"Successfully connected to client: {address[0]} {address[1]}")
    
        
        threading.Thread(target=work_with_client, args=(client,)).start()  

if __name__ == '__main__':
    main()
