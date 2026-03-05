#Testing client-server connection

import socket
import threading

HOST = '127.0.0.1'   #Server IP address (IPv4)
PORT = 1234              #Port number the server is listening on


def listening_For_Messages(client):
# This function continously listens for incoming messages from the server. It runs on a separate thread so that the client can send and receive messages simultaneously.
     while True:
          try: 
               message = client.recv(2048).decode('utf-8')
               if message != '':
                    userID = message.split(":")[0]
                    messageContent = message.split(":")[1]

                    print(f"[{userID}]: {messageContent}")
                    
                    
               else:
                    print("Message is empty!")
          except:
               print("Disconnected from the server")
               break


def send_message(client):
    # This function allows the user to type messages and send them to the server.
    while True:
         message = input("Message: ")
         if message != '':
              client.sendall(message.encode())
         else:
              print("Empty message!")
              exit(0)

def server_communication(client):
#Handles initial communication with the server, including sending the userID and starting the listening thread.
     while True:
          userID = input("\nLogin..\nEnter userID: ")
          if userID != '':
               client.sendall(userID.encode())
               receiving_msg = client.recv(2048).decode() # the client receives the server responce about login success/error

               print(receiving_msg) # we take the server response
               if receiving_msg.startswith("ACK"): # if the server ACKnowledged username succes
                    break
               else:
                    print("Try again with another username!")
          else:
               print("Invalid: UserID cannot be empty")
               
          #start the listening thread after login success
     threading.Thread(target=listening_For_Messages, args=(client, )).start()

     interface_menu(client) # after login success, show the menu
     
          # main thread that handles sending messages
     send_message(client)


def interface_menu(client):
     while True:
          print("\nWELCOME TO THE NETWORKERS CHAT SYSTEM!!")
          print("1. Connect to Peer")
          print("2. Join Default Group")
          print("3. Send messages to Default group")
          print("4. Exit")

          choice = input("Choose your action: \n")

          if choice in ["1", "2", "4"]:
               client.sendall(choice.encode())

               if choice == "4":
                    break

          elif choice == "3":
               send_group_message(client) # we need to make a function that allows messaging
          
          else:
               print("Invalid choice!")

def send_group_message(client):
     print("\nWELCOME TO OUR DEFAULT GROUP CHAT!!")
     print("Type 'return' to go back to the menu")

     while True:
          message = input() # you write

          if message.lower() == 'return': # exit
               
               break
          if message != "":
               client.sendall(message.encode())



#Main function
def main():
     #create the socket object
     #AF_INET: Use IPV4 addresses(home address of a computer)
     #SOCK_STREAM: We are going to be using TCP packets for communication
     client = socket.socket(socket.AF_INET, socket.SOCK_STREAM)

     #connect to the server(TCP connection)
     try:
          client.connect((HOST, PORT))
          print(f"Connection is successful to server: {HOST} {PORT}!")
     except:
          print("Connection is unsuccessful!")

     server_communication(client)

if __name__== '__main__':
    main()