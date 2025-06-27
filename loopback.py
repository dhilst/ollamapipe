import asyncio
import sys
import argparse
import shlex

async def read_stream(stream, queue, output_end_marker, name=""):
    """
    Reads lines from an async stream until an end marker is found,
    then puts the accumulated lines into a queue.
    """
    print(f"[Bridge] Starting reader for {name}...")
    while True:
        try:
            lines = []
            end_marker_found = False

            while True:
                line = await stream.readline()
                if not line:
                    # If no line is read, wait a short period before trying again.
                    # This prevents busy-waiting and allows other tasks to run.
                    await asyncio.sleep(0.01) 
                    continue
                
                decoded_line = line.decode('utf-8').strip()
                
                if decoded_line == output_end_marker:
                    end_marker_found = True
                    break # End of this message, break inner loop
                
                lines.append(decoded_line)

            if lines: # Only put non-empty lines into the queue
                msg = "\n".join(lines) + "\n"
                await queue.put(msg)
            
            # If the end marker was found, continue the outer loop to read the next message.
            # If the inner loop broke because the stream closed (not line), the outer loop will
            # break too on the next iteration or the task will be cancelled.

        except asyncio.CancelledError:
            print(f"[Bridge] Reader for {name} cancelled.")
            break # Exit the loop if task is cancelled
        except Exception as e:
            print(f"[Bridge] Error reading from {name}: {e}")
            break # Exit the loop on other exceptions

async def write_stream(stream, queue, name=""):
    """
    Writes lines from a queue to an async stream.
    """
    print(f"[Bridge] Starting writer for {name}...")
    while True:
        try:
            data = await queue.get()
            if data is None: # Sentinel for termination
                print(f"[Bridge] {name} writer received termination signal.")
                break # Exit the loop
            
            # Ensure the data ends with a newline and is encoded
            line_to_write = (data + '\n').encode('utf-8')
            stream.write(line_to_write)
            await stream.drain() # Ensure the data is flushed immediately
            
            queue.task_done()
        except asyncio.CancelledError:
            print(f"[Bridge] Writer for {name} cancelled.")
            break # Exit the loop if task is cancelled
        except Exception as e:
            print(f"[Bridge] Error writing to {name}: {e}")
            break # Exit the loop on other exceptions

async def handle_user_input(proc1, proc2, c1_out_q, c2_out_q):
    """
    Handles direct user input to terminate the bridge.
    """
    print("\n[Bridge] Type 'exit' to terminate the process.")
    while True:
        try:
            # Use asyncio.to_thread for blocking input() call
            user_line = await asyncio.to_thread(sys.stdin.readline)
            if user_line.strip().lower() == 'exit':
                print("[Bridge] Initiating graceful shutdown...")
                
                # Send termination signals to all relevant queues
                await c1_out_q.put(None)
                await c2_out_q.put(None)
                
                # Close stdin of the subprocesses if they're still open
                if proc1.stdin and not proc1.stdin.is_closing():
                    proc1.stdin.close()
                    await proc1.stdin.wait_closed()
                if proc2.stdin and not proc2.stdin.is_closing():
                    proc2.stdin.close()
                    await proc2.stdin.wait_closed()
                
                # Allow time for queues to be processed and tasks to finish
                await asyncio.sleep(0.1) 
                
                # Terminate subprocesses if they are still running
                if proc1.returncode is None:
                    print("[Bridge] Terminating Command 1 subprocess...")
                    proc1.terminate()
                    await proc1.wait() # Wait for it to terminate
                
                if proc2.returncode is None:
                    print("[Bridge] Terminating Command 2 subprocess...")
                    proc2.terminate()
                    await proc2.wait() # Wait for it to terminate
                
                break # Exit the user input loop
            elif user_line.strip():
                print("[Bridge] User input not handled by bridge. Type 'exit' to quit.")
        except asyncio.CancelledError:
            print("[Bridge] User input handler cancelled.")
            break # Exit loop if task is cancelled
        except Exception as e:
            print(f"[Bridge] Error in user input handler: {e}")
            break

async def main():
    parser = argparse.ArgumentParser(
        description="Bridge two command-line programs for bidirectional I/O."
    )
    parser.add_argument(
        "--c1", 
        required=True, 
        help="The executable for Command 1 (e.g., 'python', 'my_script.sh')."
    )
    parser.add_argument(
        "--c1-args", 
        nargs='*', 
        default=[], 
        help="Arguments for Command 1. Provide them space-separated (e.g., --c1-args -u script1.py)."
    )
    parser.add_argument(
        "--c1-stop",
        default="END_C1_OUTPUT", 
        help="A string marking the end of Command 1's output. This string will be removed from the message sent to Command 2."
    )
    
    parser.add_argument(
        "--c2", 
        required=True, 
        help="The executable for Command 2 (e.g., 'python', 'another_script.rb')."
    )
    parser.add_argument(
        "--c2-args", 
        nargs='*', 
        default=[], 
        help="Arguments for Command 2. Provide them space-separated (e.g., --c2-args data.txt --verbose)."
    )
    parser.add_argument(
        "--c2-stop",
        default="END_C2_OUTPUT", 
        help="A string marking the end of Command 2's output. This string will be removed from the message sent to Command 1."
    )

    args = parser.parse_args()

    command1_to_run = [args.c1] + args.c1_args
    command2_to_run = [args.c2] + args.c2_args

    print(f"[{' '.join(command1_to_run)}] <--> [{' '.join(command2_to_run)}] Bridge starting...")

    # Create async queues for communication
    # From Command 1 stdout -> Command 2 stdin
    c1_out_to_c2_in_queue = asyncio.Queue()
    # From Command 2 stdout -> Command 1 stdin
    c2_out_to_c1_in_queue = asyncio.Queue()

    proc1 = None
    proc2 = None
    try:
        # Start Command 1 subprocess
        print(f"[Bridge] Executing Command 1: {' '.join(command1_to_run)}")
        proc1 = await asyncio.create_subprocess_exec(
            *command1_to_run,
            stdin=asyncio.subprocess.PIPE,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE, # Keep stderr for debugging, not actively processed by bridge
        )

        # Start Command 2 subprocess
        print(f"[Bridge] Executing Command 2: {' '.join(command2_to_run)}")
        proc2 = await asyncio.create_subprocess_exec(
            *command2_to_run,
            stdin=asyncio.subprocess.PIPE,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE, # Keep stderr for debugging
        )

        # Create tasks for reading from command 1 stdout and writing to command 2 stdin
        read_c1_out_task = asyncio.create_task(
            read_stream(proc1.stdout, c1_out_to_c2_in_queue, args.c1_stop, "Command 1 STDOUT")
        )
        write_c2_in_task = asyncio.create_task(
            write_stream(proc2.stdin, c1_out_to_c2_in_queue, "Command 2 STDIN")
        )

        # Create tasks for reading from command 2 stdout and writing to command 1 stdin
        read_c2_out_task = asyncio.create_task(
            read_stream(proc2.stdout, c2_out_to_c1_in_queue, args.c2_stop, "Command 2 STDOUT")
        )
        write_c1_in_task = asyncio.create_task(
            write_stream(proc1.stdin, c2_out_to_c1_in_queue, "Command 1 STDIN")
        )

        # Create task for user input (to gracefully exit)
        user_input_task = asyncio.create_task(
            handle_user_input(proc1, proc2, c1_out_to_c2_in_queue, c2_out_to_c1_in_queue)
        )

        # Run all tasks concurrently
        await asyncio.gather(
            read_c1_out_task,
            write_c2_in_task,
            read_c2_out_task,
            write_c1_in_task,
            user_input_task,
            return_exceptions=True # Allow other tasks to continue if one raises an exception
        )

        # Wait for both subprocesses to finish
        print("[Bridge] Waiting for subprocesses to complete...")
        await asyncio.gather(proc1.wait(), proc2.wait())
        print(f"[Bridge] Command 1 exited with code: {proc1.returncode}")
        print(f"[Bridge] Command 2 exited with code: {proc2.returncode}")

    except FileNotFoundError as e:
        print(f"[Error] Command not found: {e.filename}")
    except Exception as e:
        print(f"[Critical Error] An unexpected error occurred: {e}")
    finally:
        # Ensure subprocesses are terminated if they are still running
        if proc1 and proc1.returncode is None:
            print("[Bridge] Cleaning up: Terminating Command 1 subprocess...")
            proc1.terminate()
            await proc1.wait()
        if proc2 and proc2.returncode is None:
            print("[Bridge] Cleaning up: Terminating Command 2 subprocess...")
            proc2.terminate()
            await proc2.wait()
        print("[Bridge] Bridge stopped.")


if __name__ == "__main__":
    asyncio.run(main())

