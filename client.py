import socket
import threading
import queue
import json
import CHAT_SERVER
import os
import time


HOST = '127.0.0.1'   #Server IP address (IPv4)
TCP_PORT = 1234              #Port number the server is listening on
UDP_PORT = 1235


CURRENT_USERNAME = None
last_sent_typingPacket = 0 #used as a timestamp for the last sent typing packet
inactivity_time = None   # use it as countdown timer for when theres no typing activity happening from the client

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

               if message.startswith("SERVER:Exiting chat"): #exiting the sysyem
                    client.close()
                    os._exit(0)


               if message == '':
                    continue
               if (isinstance(message, str)):
                    if (message.startswith("ACK:") or message.startswith("ERROR:")):
                         server_msg_queue.put(message)
                    else:
                         print(message) 

               elif isinstance(message, bytes) and message.startswith("["):
                    server_msg_queue.put(message)

               elif message.startswith("FILE:"):
                    _, filename, filesize_String = message.split(":", 2)
                    filesize = int(filesize_String)

                    #save the file to a certain directory through a specified path- if the directory does not exist - the system will just make one
                    os.makedirs("downloads", exist_ok = True)
                    filepath = os.path.join("downloads", filename)

                    #reading and writing of the chunks of data from server
                    with open(filepath, "wb") as f:
                         current_bytes = 0       #number of chunks of data that we have recieved  so far
                         while current_bytes < filesize:
                              chunk = client.recv(min(4096, filesize - current_bytes))
                              if not chunk:
                                   break
                              f.write(chunk)
                              current_bytes += len(chunk)
                         print(f"\nFile received and saved to: {filepath}")

               
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
      print("type 'quit' to return to the menu")
      print("type '/file' to send a file\n")


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
              if message == "/file":
                   filepath = input("Enter the filepath:")
                   send_fileP2P(p2p_socket, filepath)
              else:     
                  p2p_socket.sendall(f"{username}: {message}".encode())
         else:
              print("ERROR:Empty message!")

#the sending of the file between peers
#different because its uses the peer-2-peer socket
def send_fileP2P(p2p_socket, filepath):
     try:
          #extract the file name and size from the filepath provided by the user
          filename = os.path.basename(filepath)
          filesize = os.path.getsize(filepath)

          #send the metadata to the server
          p2p_socket.sendall(f"FILE:{filename}:{filesize}".encode())

          #sending of the chunks of data in bytes
          with open(filepath, "rb") as f:
               while chunk := f.read():
                    p2p_socket.sendall(chunk)
          print(f"File '{filename}' send successfully!")
     except Exception as e:
          print(f"Error sending file: {e}")



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

def server_communication(client, p2p_socket, udp_port):
#Handles initial communication with the server, including sending the userID and starting the listening thread.
     while True:
          
          userID = input("\nLogin..\nEnter userID: ")
          if userID != '':
               
               peer_port = p2p_socket.getsockname()[1]
               client.sendall(f"{userID}:{peer_port}:{udp_port}".encode())  #send both ports
               
               
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

     threading.Thread(target=receiving_theUDP, daemon=True).start()
     
     
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
               
               #option to share a file
               if message.startswith("FILE:"):
                    _, filename, filesize_String = message.split(":", 2)
                    filesize = int(filesize_String)

                    #save the file to a certain directory through a specified path- if the directory does not exist - the system will just make one
                    os.makedirs("downloads", exist_ok = True)
                    filepath = os.path.join("downloads", filename)

                    #reading and writing of the chunks of data from server
                    with open(filepath, "wb") as f:
                         current_bytes = 0       #number of chunks of data that we have recieved  so far
                         while current_bytes < filesize:
                              chunk = p2p_socket.recv(min(4096, filesize - current_bytes))
                              if not chunk:
                                   break
                              f.write(chunk)
                              current_bytes += len(chunk)
                    print(f"\nFile received and saved to: {filepath}")
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
               
               print(f"\nTalk soon! Type 'quit'!.")
               stop_event.set() #new change
               break



def interface_menu(client, p2p_socket, username):
     
     while True:
          peer_session_active.wait()  # block here if a peer session is running

          has_incoming = not incoming_peer_queue.empty() # LET THE USER KNOW IF SOMEONE IS WAITING TO CHAT

          print("\nWELCOME TO THE NETWORKERS CHAT SYSTEM!!")
          print("1. Connect to Peer")
          print("2. List online users")
          print("3. Create group")
          print("4. Join group")
          print("5. Send group message")
          print("6. Exit a group")
          print("7. Exit the chat system")

          # ADDED A 7TH CHOICE SO THE RECEIVER CAN 'ACCEPT' THE INVITAION TO CONNECT AND CHAT
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
               client.sendall("LIST_USERS".encode())

               try:
                    response = server_msg_queue.get(timeout=5)
                    parts = response.split(":")
                    if parts[0] == "ACK":
                         print("\nONLINE Users:")
                         print(parts[2])

               except queue.Empty:
                    print("ERROR:No response from server")


          #send to the server to continue with the creation of the group
          elif choice == "3":
          
               groupName = input("Enter the name of the new group: \n")
               members= input("Enter a comma seperared list of members (e.g Zama,Khanyi): \n") 
               client.sendall(f"CREATE_GROUP:{groupName}:{members}:{username}".encode())

               try:
                    response = server_msg_queue.get(timeout=5)
                    print(response)

               except queue.Empty:
                    print("ERROR:No response from server")
             

          #send to the server to continue with add the member to the group   
          elif choice=="4":
               groupName = input("Enter the name of the group you would like to join: \n")  
               client.sendall(f"JOIN_GROUP:{groupName}:{username}".encode())

               try:
                    response = server_msg_queue.get(timeout=5)
                    print(response)
               except queue.Empty:
                    print("ERROR:No response from server")


          # elif choice == "3":
          #      client.sendall(choice.encode())
          #      # we want to wait for the server's joined reply before looping
          #      try:
          #           reply = server_msg_queue.get(timeout=5)
          #           parts = reply.split(":",1)
          #           print(parts[1] if len(parts) == 2 else reply)
          #      except queue.Empty :
          #           #print("No reply from server")
          #           pass


          #send message to groups
          elif choice =="5":
               group = input("Enter group name you woud like to chat in:\n")
               print("Type 'return' to go back")

               while True:
                    message = input()
                    if message.lower() == "return":
                         break
                    if message !="":
                         client.sendall(f"GROUP_MSG:{group}:{message}".encode())
               
               # #try:
               #      #response = server_msg_queue.get(timeout=5)
               #      #print(response)
               # except queue.Empty:
               #      print("ERROR:No response from server")


          #all the client to exit the specified group
          elif choice == "6":
               group = input("Enter the name of the group you would like to exit:\n")
               client.sendall(f"EXIT_GROUP:{group}".encode())  

               try:
                    response = server_msg_queue.get(timeout=5)
                    print(response)
               except queue.Empty:
                    print("ERROR:No response from server")


          #Exit chat system and disconnect from the server
          elif choice == "7":
               print("Goodbye! Hope to see you soon!")
               client.sendall(f"EXIT_CHAT_SYSTEM".encode())
               break
     
          # ACCEPT INCOMING PEER CONN
          # INCOMING CONN IS HANDLED HERE ON THE MAIN THREAD SO THERE IS ONLY EVER ONE INPUT() AT A TIME
          elif choice == "8":
               try:
                    peer, peer_name = incoming_peer_queue.get_nowait()
                    handle_a_peer_chat(peer, username, peer_name=peer_name, send_handshake=False)
               except queue.Empty:
                    print("ERROR:No pending incoming connections.")
             
          else:
               print("Invalid choice!")
               continue

          
def send_group_message(client):
     group = input("Enter group name: ")
     print("Type 'return' to go back")
     print("Type '/file' to send a file\n")

     while True:
          message = input()
          if message.lower() == "return":
               break
          if message !="":
               if message == "/file":  #option to allow user to file share
                    filepath = input("Enter the filepath: ")
                    send_fileCS(client, filepath)
               else:
                    input_field(message, CURRENT_USERNAME, group) #come back here 
                    client.sendall(f"GROUP_MSG:{group}:{message}".encode())

#This function is called when the user wants to send a file to another user
def send_fileCS(client, filepath):
     try:
          #extract the file name and size from the filepath provided by the user
          filename = os.path.basename(filepath)
          filesize = os.path.getsize(filepath)

          #send the metadata to the server
          client.sendall(f"FILE:{filename}:{filesize}".encode())

          #sending of the chunks of data in bytes
          with open(filepath, "rb") as f:
               while chunk := f.read():
                    client.sendall(chunk)
          print(f"File '{filename}' send successfully!")
     except Exception as e:
          print(f"Error sending file: {e}")

#send the udp packet from client to sever
def send_udp_notification(message):
     udp_socket_client.sendto(message.encode(), (HOST, UDP_PORT))

#explain
def cancel_timer():
     global inactivity_time
     if inactivity_time:
          inactivity_time.cancel()

#called every time a user types a character
def input_field(message, sender, target):
     global last_sent_typingPacket, inactivity_time

     #if the input field/box is empty, send the 'stopped typing' notification immediately
     if len(message) == 0:
          send_udp_notification(f"Stopped_typing:{sender}:{target}")
          return
     
     #used to send the typing notifcation every 2 seconds
     current = time.time()
     if current - last_sent_typingPacket > 2:
          send_udp_notification(f"typing:{sender}:{target}")
          last_sent_typingPacket = current

     #reset the countdown if there is no activity in about 3 seconds
     reset_InactivityTimer(sender, target)

#send the 'stopped typing' packet
def user_stoppedTyping(sender, target):
     send_udp_notification(f"Stopped_typing:{sender}:{target}")

def reset_InactivityTimer(sender, target):
     global inactivity_time
     if inactivity_time:
          inactivity_time.cancel() #if a timer already exists, cancel it
     inactivity_time = threading.Timer(3.0, user_stoppedTyping, args=(sender, target)) # creates a new timer if the user does not type for 3 seconds - we then call user_StoppedTyping()
     inactivity_time.start()

def receiving_theUDP():
     global udp_socket_client
     while True:
          try:
               data, address = udp_socket_client.recvfrom(2048)
               message = data.decode()
               print(f"UDP received from {address}: {message}")
               event, sender = message.split(':')

               if event == 'typing':
                    print(f"{sender} is typign..")
               elif event == "Stopped_typing":
                    print(f"{sender} stopped typing")
          except Exception as e:
               print(f"UDP receive error: {e}")


#Main function
def main():
     global udp_socket_client
     

     #create the socket object
     #AF_INET: Use IPV4 addresses(home address of a computer)
     #SOCK_STREAM: We are going to be using TCP packets for communication
     client = socket.socket(socket.AF_INET, socket.SOCK_STREAM)

     #connect to the server(TCP connection)
     try:
          client.connect((HOST, TCP_PORT))
          print(f"Connection is successful to server: {HOST} {TCP_PORT}!")
     except Exception as e:
          print(e)
          print("ERROR:Connection is unsuccessful!")
          return

     #lets set up our udp socket for notifications
     udp_socket_client = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
     udp_socket_client.bind(("0.0.0.0", 0))  #operating system assigns random port
     udp_port = udp_socket_client.getsockname()[1]  # get the assigned random port 

     
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
                    print("Type '8' to accept the invitation.\n")
                    # new change
                    print("Choose your action: ", end="", flush=True)                       
                    #handle_a_peer_chat(peer, CURRENT_USERNAME, peer_name=peer_name) # we start the full peer session without a thread so that it runs on the main thread
               except Exception as e:
                    print(e)
                    break

     threading.Thread(target=accept_loop, daemon=True).start()
     server_communication(client, p2p_socket, udp_port)

if __name__== '__main__':
    main()