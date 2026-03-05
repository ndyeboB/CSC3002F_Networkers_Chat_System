#Testing client-server connection

import socket
import threading

HOST = '196.24.130.36 -'   #Server IP address (IPv4)
PORT = 1234              #Port number the server is listening on

def listeningForMessages(client):
# This function continously listens for incoming messages from the server. It runs on a separate thread so that the client can send and receive messages simultaneously.
     while True:
          message = client.recv(2048).decode('utf-8')
          if message != '':
               userID = message.split(":")[0]
               messageContent = message.split(':')[1]

               print(f"[{userID}] {messageContent}")
               
          else:
               print("message is empty")

def send_message(client):
    # This function allows the user to type messages and send them to the server.
    while True:
         message = input("message:")
         if message != '':
              client.sendall(message.encode())
         else:
              print("empty message")
              exit(0)

def server_communication(client):
#Handles initial communication with the server, including sending the userID and starting the listening thread.
     userID = input("Enter userID:")
     if userID != '':
          client.sendall(userID.encode())
     else:
          print("Invalid: userID cannot be empty")
          exit(0)
     #start the listening thread
     threading.Thread(target=listeningForMessages, args=(client, )).start()
  
     # main thread that handles sending messages
     send_message(client)

#Main function
def main():
     #create the socket object
     #AF_INET: Use IPV4 addresses(home address of a computer)
     #SOCK_STREAM: We are going to be using TCP packets for communication
     client = socket.socket(socket.AF_INET, socket.SOCK_STREAM)

     #connect to the server(TCP connection)
     try:
          client.connect((HOST, PORT))
          print("connection is successful")
     except:
          print(f"connection is unsuccessful")

     server_communication(client)

if __name__== '__main__':
    main()