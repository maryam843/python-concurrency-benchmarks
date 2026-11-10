# The standard mpi4py send/recv example, supplied with the original exercise and modified here:
# it also works with a single rank (see CREDITS.md).
from mpi4py import MPI

comm = MPI.COMM_WORLD  # Create MPI communicator (group of processes)
rank = comm.Get_rank()  # Get the rank (process ID) of the current process
size = comm.Get_size()

if size < 2:
    # Earlier bug: with 1 rank, send(dest=1) failed with MPI_ERR_RANK. Send to myself instead.
    data = comm.sendrecv({"a": 7, "b": 3.14}, dest=0, sendtag=11, source=0, recvtag=11)
    print("Only 1 rank: process 0 sent the data to itself:", data)
elif rank == 0:  # Code executed by process 0
    data = {"a": 7, "b": 3.14}  # Data dictionary to send
    comm.send(data, dest=1, tag=11)  # Send data to process 1 with tag 11
elif rank == 1:  # Code executed by process 1
    data = comm.recv(source=0, tag=11)  # Receive data from process 0 (tag 11)
    print("On process 1, data received:", data)  # Print received data
