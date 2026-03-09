#Testing client-server connection

import CHAT_SERVER
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


def peer_send_msg(peer):
      while True:
         message = input("Message: ")
         if message != '':
              peer.sendall(message.encode())
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
               
               if receiving_msg.startswith("ACK"): # if the server ACKnowledged username success
                    
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


def peer_chat(peer, address):
     while True:
          try: 
               message = peer.recv(2048).decode('utf-8')
               if message != '':
                    userID = message.split(":")[0]
                    messageContent = message.split(":")[1]

                    print(f"[{userID}]: {messageContent}")
                    
                    
               else:
                    print("Message is empty!")
          except:
               print("Disconnected from the peer suddenly.")
               break

     peer_send_msg(peer)


def interface_menu(client):
     while True:
          print("\nWELCOME TO THE NETWORKERS CHAT SYSTEM!!")
          print("1. Connect to Peer")
          print("2. Join Default Group")
          print("3. Send messages to Default group")
          print("4. Exit")

          choice = input("Choose your action: \n")

          if choice == "1":
               name = input("Please enter the person you want to chat with")

               client.sendall(f"GET_PEER:{name}".encode())

          elif choice == "2":
               client.sendall(choice.encode())

          elif choice =="3":
               send_group_message(client)
               client.sendall(choice.encode())



          elif choice == "4":
                    client.sendall(choice.encode())
                    for user in CHAT_SERVER.online_clients:
                         username = user[0]
                         print(f"Goodbye {username}! Hope to see you soon!")
                         break

             
          else:
               print("Invalid choice!")

          

          
def send_group_message(client):
     print("\nWELCOME TO OUR DEFAULT GROUP CHAT!!")
     print("Type 'return' to go back to the menu\n\nStart typing message!!")

     while True:
          message = input() # you write

          if message.lower() == 'return': # exit
               client.sendall("EXITING".encode())
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

     p2p_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
     try:

          p2p_socket.bind(("0.0.0.0", 0))# 0 means that OS will assign a port number
          
     except:
          print("Could not bind the socket!")


     p2p_socket.listen()
     print("The peer is listening for a connection from another peer...")

     def accept_loop():
          while True:
               peer, address = p2p_socket.accept() # peer = peer_socket 
          
               print(f"Successfully connected to peer: {address[0]} {address[1]}")
          
               threading.Thread(target=peer_chat, args=(client,)).start()

     threading.Thread(target=accept_loop, args=()).start()
     

if __name__== '__main__':
    main()