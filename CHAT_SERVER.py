# we are importing the required libaries
import socket
import threading

HOST = "0.0.0.0"
PORT = 1234 # the range of use is 0 to 65535

CLIENT_LIMIT = 5 # lets set a limit on the amount of people that can be a chat -- later we can build more capacity in our system

online_clients = [] # list of all clients that are curently online and connected to the server





def work_with_client(client):
    # initial connection with the client

    while True:
        username = client.recv(2048).decode('utf-8') # wait for the username that yo may receive from the client
        if username != '':
            online_clients.append((username, client)) # we add the client to list
            entry_message = "Server: "+f"{username} has entered the chat system!"
            lets_send_message_to_everyone(entry_message) 
            # when a new user is added to the chat, every one else is notified
            break
        else:
            print("The username given by the client is empty!")
    # this CREATES a NEW THREAD
    # that thread runs server_listening
    # SO EACH CLIENT HAS ITS OWN LOOP!!!!!
    # without this 1 client could talk but with it each client runs indepedently
    threading.Thread(target=server_listening, args=(client, username, )).start()


# the server must actively listen for upcoming message from a client
def server_listening(client, username): # responsible of collecting the message
    
    while True:
        message = client.recv(2048).decode('utf-8') # listens for the message that the client wants to send

        if message !='':
            main_message = username + ':' + message
            lets_send_message_to_everyone(main_message)

        else:
            print(f"The message sent from client: {username} is empty. Please try again.")
    
    
# this is to send a message to a single client
# needs to be further implemented so the client can choose who to send a message to with peer to peer
def lets_send_message_to_client(client, message):
    client.sendall(message.encode()) # client = receiving client

# needs to be further implemented so we first initiate a seperate group chat to send to everyone
def lets_send_message_to_everyone(message): 

    for user in online_clients:
        lets_send_message_to_client(user[1], message) # user[1] takes the client object because when we appended to the list we had username as the 1st element amd client as the 2md element

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
