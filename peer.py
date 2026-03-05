import socket
import threading

hostIP = "0.0.0.0"
port= 2357

def sendMessage(client, message):
    client.sendall(message.encode()) # client = receiving client

def connectPeer(client):
    while True:
        username = client.recv(2048).decode('utf-8') # wait for the username that you may receive from the client
        if username != '':
            #online_clients.append((username, client)) # we add the client to list
            entry = "Peer: "+f"{username} has connected!"
            sendMessage(entry)
            break
        else:
            print("The username is empty!")
            
    threading.Thread(target=listen, args=(client, username, )).start()

def listen(client, username):
    message = client.recv(2048).decode('utf-8')
    if message !="":
        finalMessage= username+":"+ message
        sendMessage(finalMessage)
    else:
        print(f"The message sent from client: {username} is empty. Please try again.")
    

def main():
    server = socket.socket(socket.AF_INET, socket.SOCK_STREAM) # we are using TCP
    try:
        # attach the server with an address in the form of host IP and port
        server.bind((hostIP,port))
        
    except:
        print(f"ERROR! The server cannot bind to host: {hostIP} and port: {port}. Please try again!")

    server.listen()
    #print(f"The server on {hostIP} {port} is listening for a connection...")
    initiator = input("Would you like to initiate a conversation? (yes/no)").lower()

    if initiator == "no":
        while True:
            connection, address = server.accept()
            print(f"Successfully connected to peer: {address[0]} {address[1]}")
            threading.Thread(target=connectPeer, args=(connection,)).start()

    elif initiator == "yes":
        connectTo= input("Enter the username of the person you want to connect to?")
        for x in CHAT_SERVER.online_user:
            

    else:
        print("Enter 'yes' or 'no'")

if __name__ == '__main__':
    main()
    