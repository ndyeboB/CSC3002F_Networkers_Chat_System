

import socket
import threading
import queue


HOST = '127.0.0.1'   #Server IP address (IPv4)
PORT = 1234              #Port number the server is listening on





CURRENT_USERNAME = None

server_msg_queue = queue.Queue()

peer_session_active = threading.Event() # used to pause the menu while a peer session is active
peer_session_active.set()  # start cleared (no peer session running)

# new change
incoming_peer_queue = queue.Queue() # used to safely pass incoming peer connections from accept_loop to main thread

def listening_For_Messages(client):
# This function continously listens for incoming messages from the server. It runs on a separate thread so that the client can send and receive messages simultaneously.
     while True:
          try: 
               message = client.recv(2048).decode('utf-8')
               if message == '':
                    continue

               if (message.startswith("ACK:") or message.startswith("ERROR:")): 
                    server_msg_queue.put(message)
               else:
                    parts = message.split(":",1)
                    if len(parts) ==2:
                         print(f"\n[{parts[0]}]: {parts[1]}")
                         print("\n", end="", flush=True) # not a threading problem but a prompting problem
                    else:
                         print(f"\n{message}")
                         print("\n", end="", flush=True)
                             
               
          except Exception as e:
               print(e)
               print("ERROR:Disconnected from the server")
               break


def send_message(client):
    # This function allows the user to type messages and send them to the server.
    while True:
         message = input("Message: ")
         if message != '':
              client.sendall(message.encode())
         else:
              print("ERROR:Empty message!")
              

# new change = added 3rd arg
#   SENDS MESSAGES TYPED BY THE USER TO THE CONNECTED PEER
# STOPS WHEN THE USER TYPES 'quit' OR WHEN STOP_EVENT IS SET
def peer_send_msg(p2p_socket, username, stop_event):
      print("type 'quit' to return to the menu\n")

      while not stop_event.is_set(): 
         message = input("Peer Message: ")
          # new change
         if stop_event.is_set(): # RE-CHECK AFTER INPUT() RETURNS IN CASE THE PEER DISCONNECTED WHILE WE WERE WAITING
              print("\n[Session ended by remote peer]")
              break
     
         if message.lower() == 'quit':
              p2p_socket.sendall(f"{username}: has left the chat".encode())
              break
         if message != '':
              p2p_socket.sendall(f"{username}: {message}".encode())
         else:
              print("ERROR:Empty message!")

# RUNS A FULL 2-WAY PEER CHAT SESSION
# CALLED ON THE MAIN THREAD FRO BOTH THE OUTGOING CONNECTOR AND THE INCOMING ACCEPTOR (after the acceptor queues the connection)
#             
def handle_a_peer_chat(p2p_socket, username, peer_name="peer", send_handshake=False):
     #runs a full two-way peer chat session where it is called by both the connector and the acceptor so both sides can send & receive
     peer_session_active.clear()  # PAUSE the menu loop

     print(f"\nConnected to {peer_name}! Type 'quit' to end the chat session.")

     if send_handshake: # only the connector sends the username handshake
          p2p_socket.sendall(f"USERNAME:{username}".encode()) # we want to send our username to the peer so they know who they are connecting to
     
     stop_event = threading.Event() # shared bet rceiver and sender

     threading.Thread(target=peer_chat, args=(p2p_socket,stop_event), daemon=True).start()
     
     peer_send_msg(p2p_socket, username, stop_event) # new change = added 3rd arg

     p2p_socket.close()
     peer_session_active.set()    # RESUME the menu loop
     print("\nPeer session ended. Returning to menu...")

def server_communication(client, p2p_socket):
#Handles initial communication with the server, including sending the userID and starting the listening thread.
     while True:
          
          userID = input("\nLogin..\nEnter userID: ")
          if userID != '':
               
               peer_port = p2p_socket.getsockname()[1]
               client.sendall(f"{userID}:{peer_port}".encode())
               
               
               receiving_msg = client.recv(2048).decode() # the client receives the server responce about login success/error
               
               print(receiving_msg) # we take the server response
               
               if receiving_msg.startswith("\nACK"): # if the server ACKnowledged username success
                    global CURRENT_USERNAME # making the username variable global to access it in the access_loop()
                    CURRENT_USERNAME = userID
                    break
               else:
                    print("ERROR:Try again with another username!")
          else:
               print("ERROR:UserID cannot be empty")
               
          #start the listening thread after login success
     
     threading.Thread(target=listening_For_Messages, args=(client, ), daemon=True).start()
     
     
     interface_menu(client, p2p_socket, userID) # after login success, show the menu
                              # main thread that handles sending messages
     

# new change = added 2nd arg
# RECEIVES AND PRINTS MESSAGES FROM THE CONNECTED PEER
# SETS STOP_EVENT WHEN THE PEER DISCONNECTS SO peer_send_msg CAN EXIT CLEANLY
def peer_chat(p2p_socket, stop_event):
     while True:
          try: 
               message = p2p_socket.recv(2048).decode('utf-8')

               if not message:
                    print("\nPeer has disconnected.")
                    stop_event.set() # SIGNAL peer_send_msg TO STOP BLOCKING ON INPUT()
                    break

               # username handshake message , we skip it, its not a chat message
               if message.startswith("USERNAME:"):
                    continue

               parts = message.split(":",1)

               if len(parts) ==2:
                    userID = parts[0]
                    messageContent = parts[1]

               else:
                    userID = "PEER" # safe fallback
                    messageContent = message

               print(f"\n[{userID}]: {messageContent}")
               print("Peer Message: ", end="", flush=True)
                    
          except:
               
               print(f"\nTalk soon!.")
               stop_event.set() #new change
               break

     


def interface_menu(client, p2p_socket, username):
     
     while True:
          peer_session_active.wait()  # block here if a peer session is running

          has_incoming = not incoming_peer_queue.empty() # LET THE USER KNOW IF SOMEONE IS WAITING TO CHAT

          print("\nWELCOME TO THE NETWORKERS CHAT SYSTEM!!")
          print("1. Connect to Peer")
          print("2. Join Default Group")
          print("3. Send messages to Default group")
          print("4. Exit")
          print("5. List online users")
          print("6. Create group")
          print("7. Send group message")
          print("8. Join group")

          # ADDED A 5TH CHOICE SO THE RECEIVER CAN 'ACCEPT' THE INVITAION TO CONNECT AND CHAT
          if has_incoming:
               print("8. Accept incoming peer connection")

           
          choice = input("Choose your action: \n")

          if choice == "1":
               name = input("\nPlease enter the username of the person you want to chat with: ")

               client.sendall(f"GET_PEER:{name}".encode())

               try:

                    response = server_msg_queue.get(timeout=5) # we wait for the reply via the queue, not via recv() because there would be a race condition. listening_for_Mess will put the reply here
               except queue.Empty:
                    print("ERROR:No response from server (timeout). Try again")
                    continue

               if response.startswith("ERROR"):
                    
                    print(response)
                    continue



               peer_info = response.split(":")
               if len(peer_info) <3 :
                    print(f"ERROR:Invalid response: {response}")
                    continue

               peer_ip = peer_info[1].strip()
               peer_port = int(peer_info[2])

               try:
                    #apparently we need another socket to do the Connecting because p2p does the listening!!
                    #p2p_socket.connect((peer_ip, peer_port))
                    conn_peer_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                    conn_peer_socket.connect((peer_ip, peer_port))
                    #print(f"Successfully connected to peer at {peer_ip}: {peer_port}! Let's chat!")
                    # CHANGED 
                    # FROM
                    handle_a_peer_chat(conn_peer_socket, username, peer_name=name, send_handshake=True)
                    # TO
                    #threading.Thread(target=handle_a_peer_chat, args=(conn_peer_socket, username, peer_name=name, True), daemon=True).start()

                    # receiving messages from a peer while concurrently :) waitingg
                    #threading.Thread(target=peer_chat, args=(p2p_socket, ), daemon=True).start()

                    #peer_send_msg(p2p_socket)
               except Exception as e:
                    print(e)
                    print("ERROR:Could not connect to peer.")


          elif choice == "2":
               client.sendall(choice.encode())
               # we want to wait for the server's joined reply before looping
               try:
                    reply = server_msg_queue.get(timeout=5)
                    parts = reply.split(":",1)
                    print(parts[1] if len(parts) == 2 else reply)
               except queue.Empty :
                    #print("No reply from server")
                    pass

          elif choice =="3":
               send_group_message(client)
               

          elif choice == "4":
               client.sendall(choice.encode())
               
               print("Goodbye! Hope to see you soon!")
               break

          elif choice == "5":
               client.sendall("LIST_USERS".encode())

               try:
                    response = server_msg_queue.get(timeout=5)
                    parts = response.split(":")
                    if parts[0] == "ACK":
                         print("\nONLINE Users:")
                         print(parts[2])

               except queue.Empty:
                    print("ERROR:No response from server")

          elif choice == "6":
               group = input("Enter group name: ")
               client.sendall(f"CREATE_GROUP:{group}".encode())

               try:
                    response = server_msg_queue.get(timeout=5)
                    print(response)
               except queue.Empty:
                    print("ERROR:No response from server")

          elif choice == "7":
               send_group_message(client)

          elif choice  == "8":
               groupname = input("Enter group name: ")
               client.sendall(f"JOIN_GROUP:{groupname}".encode())
               try:
                    response = server_msg_queue.get(timeout=5)
                    print(response)
               except queue.Empty:
                    print("ERROR:No response from server")

               

     
          # ACCEPT INCOMING PEER CONN
          # INCOMING CONN IS HANDLED HERE ON THE MAIN THREAD SO THERE IS ONLY EVER ONE INPUT() AT A TIME
          elif choice == "9.":
               try:
                    peer, peer_name = incoming_peer_queue.get_nowait()
                    handle_a_peer_chat(peer, username, peer_name=peer_name, send_handshake=False)
               except queue.Empty:
                    print("ERROR:No pending incoming connections.")
             
          else:
               #print("Invalid choice!")
               continue

          

          
def send_group_message(client):
     group = input("Enter group name: ")
     print("Type 'return' to go back")

     while True:
          message = input()
          if message.lower() == "return":
               break
          if message !="":
               client.sendall(f"GROUP_MSG:{group}:{message}".encode())


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
     except Exception as e:
          print(e)
          print("ERROR:Connection is unsuccessful!")
          return


     
     # lets set up our p2p listening socket
     p2p_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
     try:

          p2p_socket.bind(("0.0.0.0", 0))# 0 means that OS will assign a port number
          
     except Exception as e:
          print(e)
          print("ERROR:Could not bind the socket!")
          return


     p2p_socket.listen()
     print("The peer is listening for a connection from another peer...")

     

     def accept_loop():
          #global CURRENT_USERNAME

          while True:
               try:
                    peer, address = p2p_socket.accept() # peer = peer_socket 
               
                    

                    handshake = peer.recv(2048).decode() # the receiver of the connection is receiving the username of the initiator
                    if handshake.startswith("USERNAME:"):
                         peer_name = handshake.split(":", 1)[1]
                    else:
                         peer_name = address[0] # else we just keep the port of the sender

                    #new change
                    incoming_peer_queue.put((peer, peer_name))

                    print(f"\n***{peer_name} wants to start a chat with you! \nIncoming connection with peer: {address[0]} {address[1]}...")  
                    print("Type '5' to accept the invitation.\n")
                    # new change
                    print("Choose your action: ", end="", flush=True)                       
                    #handle_a_peer_chat(peer, CURRENT_USERNAME, peer_name=peer_name) # we start the full peer session without a thread so that it runs on the main thread
               except Exception as e:
                    print(e)
                    break

     threading.Thread(target=accept_loop, daemon=True).start()
     server_communication(client, p2p_socket)

if __name__== '__main__':
    main()