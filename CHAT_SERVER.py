# we are importing the required libaries
import socket
import threading

HOST = "0.0.0.0"
PORT = 1234 # the range of use is 0 to 65535

CLIENT_LIMIT = 100 # lets set a limit on the amount of people that can be a chat -- later we can build more capacity in our system

online_clients = [] # list of all clients that are curently online and connected to the server


# main function
def main():
    # CONFIGURING OUR SERVER

    # we are now creating a socket by creating a socket objects
    server = socket.socket(socket.AF_INET, socket.SOCK_STREAM)

    try:
        # provide the server with an address in the form of host IP and port
        server.bind((HOST, PORT))
        print(f"We have initiated the server on {HOST} {PORT} and it is running!")

    except:
        print(f"ERROR! The server cannot bind to host: {HOST} and port: {PORT}. Please try again!")


    server.listen(CLIENT_LIMIT)
    
    # this while loop will keep listening to client connections
    while True:
        client, address = server.accept() 
        print(f"Successfully connected to client {address[0]} {address[1]}")


if __name__ == '__main__':
    main()
