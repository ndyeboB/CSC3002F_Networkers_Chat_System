#Testing client-server connection

import socket
import threading

HOST = '196.24.130.36'  #Blessings laptop server
PORT = 1234

#Main function
def main():
     #create the socket object
     #AF_INET: Use IPV4 addresses(home address of a computer)
     #SOCK_STREAM: We are going to be using TCP packets for communication
     client = socket.socket(socket.AF_INET, socket.SOCK_STREAM)

     #connect to the server(using the host and port adresses)
     try:
          client.connect((HOST, PORT))
          print("connection is successful")
     except:
          print(f"connection is unsuccessful")

if __name__== '__main__':
    main()