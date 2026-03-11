

import socket
import threading
import queue
import CHAT_SERVER


HOST = '127.0.0.1'   #Server IP address (IPv4)
PORT = 1234              #Port number the server is listening on

server_msg_queue = queue.Queue()
peer_session_active = threading.Event()
peer_session_active.set()  # start cleared (no peer session running)




def listening_For_Messages(client):
# This function continously listens for incoming messages from the server. It runs on a separate thread so that the client can send and receive messages simultaneously.
     while True:
          try: 
               message = client.recv(2048).decode('utf-8')
               if message == '':
                    continue

               if message.startswith("ACK:") or message.startswith("ERROR:"):
                    server_msg_queue.put(message)
               else:
                    parts = message.split(":",1)

                    if len(parts) ==2:
                         print(f"\n[{parts[0]}]: {parts[1]}")
                    else:
                         print(f"\n{message}")
                             
               
          except:
               print("\nDisconnected from the server")
               break

def handleClient(client):
     while True:
          data = client.recv(2048)

          if not data:
               break

#def processMessage that sends to the memebers in the group 


def send_message(client):
    # This function allows the user to type messages and send them to the server.
    while True:
         message = input("Message: ")
         if message != '':
              client.sendall(message.encode())
         else:
              print("Empty message!")
              


def peer_send_msg(p2p_socket):
      print("type 'quit' to return to the menu")
      while True:
         message = input("Peer Message: ")
         if message.lower() == 'quit':
              break
         if message != '':
              p2p_socket.sendall(f"PEER:{message}".encode())
         else:
              print("Empty message!")
              
def handle_a_peer_chat(p2p_socket, peer_name="peer"):
     #runs a full two-way peer chat session where it is called by both the connector and the acceptor so both sides can send & receive
     peer_session_active.clear()  # PAUSE the menu loop
     print(f"\nConnected to {peer_name}!")

     threading.Thread(target=peer_chat, args=(p2p_socket,), daemon=True).start()
     peer_send_msg(p2p_socket)
     p2p_socket.close()
     peer_session_active.set()    # RESUME the menu loop

def server_communication(client, p2p_socket):
#Handles initial communication with the server, including sending the userID and starting the listening thread.
     while True:
          
          userID = input("\nLogin..\nEnter userID: ")
          if userID != '':
               
               peer_port = p2p_socket.getsockname()[1]
               client.sendall(f"{userID}:{peer_port}".encode())
               
               
               receiving_msg = client.recv(2048).decode() # the client receives the server responce about login success/error
               
               print(receiving_msg) # we take the server response
               
               if receiving_msg.startswith("ACK"): # if the server ACKnowledged username success
                    
                    break
               else:
                    print("Try again with another username!")
          else:
               print("Invalid: UserID cannot be empty")
               
          #start the listening thread after login success
     threading.Thread(target=listening_For_Messages, args=(client, ), daemon=True).start()
     
     
     interface_menu(client, p2p_socket) # after login success, show the menu
                              # main thread that handles sending messages
     


def peer_chat(p2p_socket):
     while True:
          try: 
               message = p2p_socket.recv(2048).decode('utf-8')
               if message != '':
                    userID = message.split(":",1)[0]
                    messageContent = message.split(":",1)[1]

                    print(f"\n[PEER]: {messageContent}")
                    print("Peer Message: ", end="", flush=True)
                    
                    
               else:
                    print("Peer Message is empty!")
                    break
          except:
               print("Disconnected from the peer suddenly.")
               break

     


def interface_menu(client, p2p_socket):
     peer_session_active.wait()  # block here if a peer session is running
     while True:
               
               print("\nWELCOME TO THE NETWORKERS CHAT SYSTEM!!")
               print("1. Connect to Peer")
               print("5. Create Group")
               print("2. Join Group")
               print("4. Send message to a group")
               #print("4. Send a file")
               print("4. Exit")

               
               choice = input("Choose your action: \n")

               if choice == "1":
                    name = input("Please enter the username of the person you want to chat with: ")

                    client.sendall(f"GET_PEER:{name}".encode())

                    try:

                         response = server_msg_queue.get(timeout=5) # we wait for the reply via the queue, not via recv() because there would be a race condition. listening_forMess will put the reply here
                    except server_msg_queue.Empty:
                         print("No response from server (timeout). Try again")
                         continue

                    if response.startswith("ERROR"):
                         
                         print(response)
                         continue



                    peer_info = response.split(":")
                    if len(peer_info) <3 :
                         print(f"Invalid response: {response}")
                         continue

                    peer_ip = peer_info[1].strip()
                    peer_port = int(peer_info[2])

                    try:
                         #apparently we need another socket to do the Connecting because p2p does the listening!!
                         #p2p_socket.connect((peer_ip, peer_port))
                         conn_peer_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                         conn_peer_socket.connect((peer_ip, peer_port))
                         #print(f"Successfully connected to peer at {peer_ip}: {peer_port}! Let's chat!")
                         handle_a_peer_chat(conn_peer_socket, peer_name=name)
                         # receiving messages from a peer while concurrently :) waitingg
                         #threading.Thread(target=peer_chat, args=(p2p_socket, ), daemon=True).start()

                         #peer_send_msg(p2p_socket)
                    except:
                         print("Could not connect to peer.")


               elif choice == "2":
                    client.sendall(choice.encode())

               elif choice =="3":
                    groupName= input("Enter the name of the group: ")
                    for users in CHAT_SERVER.groups[groupName]:
                         for client in CHAT_SERVER.online_clients:
                              if users == CHAT_SERVER.online_clients[0]: 
                                   send_message(client)
                    
               elif choice =="5":
                    client.sendall(choice.encode())

                    



               elif choice == "4":
                    client.sendall(choice.encode())
                    
                    print("Goodbye! Hope to see you soon!")
                    break

               
               else:
                    print("Invalid choice!")

          

          
def send_group_message(client):
     print("\nWELCOME TO OUR DEFAULT GROUP CHAT!!")
     print("Type 'return' to go back to the menu\n\nStart typing message!")

     while True:
          message = input() # you write

          if message.lower() == 'return': # exit
               client.sendall("is has exited the default group...".encode())
               break
          if message != "":
               client.sendall(message.encode())

def sendFile(client, filepath):
     with open(filepath, "rb") as f:
          data = f.read()
     fileName = filepath
     fileSize = len(data)

     #client.sendall(header.encode()) #??
     client.sendall(data)

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
          return


     
     # lets set up our p2p listening socket
     p2p_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
     try:

          p2p_socket.bind(("0.0.0.0", 0))# 0 means that OS will assign a port number
          
     except:
          print("Could not bind the socket!")
          return


     p2p_socket.listen()
     print("The peer is listening for a connection from another peer...")

     

     def accept_loop():
          while True:
               try:
                    peer, address = p2p_socket.accept() # peer = peer_socket 
               
                    print(f"\nAbout to initiate connection with peer: {address[0]} {address[1]}...")
               
                    threading.Thread(target=peer_chat, args=(peer,), daemon=True).start()
               except:
                    break

     threading.Thread(target=accept_loop, daemon=True).start()
     server_communication(client, p2p_socket)

if __name__== '__main__':
    main()