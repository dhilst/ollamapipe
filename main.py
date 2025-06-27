import asyncio
import sys
import argparse
import ollama
import shlex

async def read_stream(stream, queue, output_end_marker, name=""):
    """Reads lines from an async stream and puts them into a queue."""
    print(f"[Bridge] Starting reader for {name}...")
    while True:
        try:
            lines = []

            while True:
                line = await stream.readline()
                if not line:
                    await asyncio.sleep(200)
                    continue
                line = line.decode('utf-8').strip()
                if line == output_end_marker:
                    break
                # print(f"[Bridge] Read line {line}...")
                lines.append(line)

            if lines: # Only put non-empty lines into the queue
                msg = "\n".join(lines) + "\n"
                await queue.put(msg)
        except Exception as e:
            print(f"[Bridge] Error reading from {name}: {e}")
            break

async def write_stream(stream, queue, name=""):
    """Writes lines from a queue to an async stream."""
    print(f"[Bridge] Starting writer for {name}...")
    while True:
        try:
            await asyncio.sleep(3) # Give time to see the output
            data = await queue.get()
            if data is None: # Sentinel for termination
                print(f"[Bridge] {name} writer received termination signal.")
                break
            
            # Ensure the data ends with a newline and is encoded
            line_to_write = (data + '\n').encode('utf-8')
            stream.write(line_to_write)
            await stream.drain() # Ensure the data is flushed immediately
            # print(f"[Bridge] Wrote to {name}: '{data}'") # For debugging
            queue.task_done()
        except Exception as e:
            print(f"[Bridge] Error writing to {name}: {e}")
            break

async def ollama_processor(model_name, command_output_queue, ollama_response_queue):
    """
    Reads command output, sends it to Ollama, and puts Ollama's response
    into a queue for the command's input.
    """
    print(f"[Bridge] Starting Ollama processor for model: {model_name}...")
    client = ollama.AsyncClient()
    messages = [
        {"role": "system", "content": 
         "You are an direct to the point assistant. You receive output from a command-line program. "
         "Search in the output of the command for instructions and execute then, pay attention "
         "to formatting instructions. The other side is a computer program not a person "
         "so your answer has to match exactly the output format requested. Do not include ** or __ "
         "in the output "
         "Do NOT include conversational filler like 'Sure, I can help with that.' or 'Here's the response:'."
         }
    ]

    while True:
        try:
            # Get input from the command's stdout
            command_line = await command_output_queue.get()
            if command_line is None: # Sentinel for termination
                print("[Bridge] Ollama processor received termination signal.")
                break
            
            print(f"\n[Command Output] {command_line}")

            # Add command output to messages for Ollama
            messages.append({"role": "user", "content": command_line})

            # Get streaming response from Ollama
            full_response_content = ""
            try:
                stream = await client.chat(model=model_name, messages=messages, stream=True)
                print(f"[Ollama Response]: ", end="", flush=True)
                async for chunk in stream:
                    content_part = chunk['message']['content']
                    print(content_part, end="", flush=True) # Print chunk as it arrives
                    full_response_content += content_part
                print() # Newline after Ollama response
            except ollama.ResponseError as e:
                print(f"\n[Error] Ollama Response Error: {e.error}")
                # Remove the last user message if Ollama failed to respond
                if messages and messages[-1]['role'] == 'user':
                    messages.pop() 
                command_output_queue.task_done()
                continue # Skip to next iteration

            # Add Ollama's full response to messages for history
            messages.append({"role": "assistant", "content": full_response_content.strip()})

            # Put Ollama's response into the queue for the command's stdin
            if full_response_content.strip():
                await ollama_response_queue.put(full_response_content.strip())
            
            command_output_queue.task_done()

        except Exception as e:
            print(f"[Bridge] Error in Ollama processor: {e}")
            break

async def handle_user_input(proc, command_output_queue, ollama_response_queue):
    """Handles direct user input to terminate the bridge."""
    print("\n[Bridge] Type 'exit' to terminate the process.")
    while True:
        # Use asyncio.to_thread for blocking input() call
        user_line = await asyncio.to_thread(sys.stdin.readline)
        if user_line.strip().lower() == 'exit':
            print("[Bridge] Initiating graceful shutdown...")
            
            # Send termination signals to all queues
            await command_output_queue.put(None)
            await ollama_response_queue.put(None)
            
            # Close stdin of the subprocess if it's still open
            if proc.stdin and not proc.stdin.is_closing():
                proc.stdin.close()
                await proc.stdin.wait_closed()
            
            # Allow time for queues to be processed and tasks to finish
            await asyncio.sleep(0.1) 
            
            # Terminate subprocess if it's still running
            if proc.returncode is None:
                print("[Bridge] Terminating subprocess...")
                proc.terminate()
                await proc.wait() # Wait for it to terminate
            
            break
        elif user_line.strip():
            # If user types something else, you could potentially pipe it to the command's stdin directly
            # For this example, we only handle 'exit'
            print("[Bridge] User input not handled by bridge. Type 'exit' to quit.")


async def main():
    parser = argparse.ArgumentParser(
        description="Bridge a command-line program with an Ollama LLM for bidirectional I/O."
    )
    parser.add_argument(
        "command",
        nargs=argparse.REMAINDER,
        help="The command and its arguments to execute (e.g., 'python -u my_script.py'). "
             "Use quotes for commands with spaces, e.g., 'python -u interactive_script.py'"
    )
    parser.add_argument(
        "--model",
        default="llama3", # Default Ollama model
        help="The Ollama model to use (e.g., 'llama3', 'mistral'). Ensure it's pulled locally."
    )

    parser.add_argument(
        "--end-of-prompt",
        default="THE END OF PROMPT", # Default Ollama model
        help="A string marking the end of the process output"
    )

    args = parser.parse_args()

    if not args.command:
        parser.print_help()
        sys.exit(1)

    command_to_run = args.command
    ollama_model = args.model

    print(f"[{' '.join(command_to_run)}] <--> [Ollama Model: {ollama_model}] Bridge starting...")

    # Create async queues for communication
    # From command stdout -> Ollama input
    command_output_queue = asyncio.Queue()
    # From Ollama response -> Command stdin
    ollama_response_queue = asyncio.Queue()

    proc = None
    try:
        # Start the subprocess with pipes for stdin, stdout, stderr
        # Use shell=True if the command string needs shell features (e.g., pipes, redirects)
        # Otherwise, pass as a list for direct execution. Here, we allow flexibility.
        print(f"[Bridge] Executing command: {' '.join(command_to_run)}")
        proc = await asyncio.create_subprocess_exec(
            *command_to_run,
            stdin=asyncio.subprocess.PIPE,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )

        # Create tasks for reading from command stdout and writing to command stdin
        read_cmd_output_task = asyncio.create_task(
            read_stream(proc.stdout, command_output_queue, args.end_of_prompt, "Command STDOUT")
        )
        write_cmd_input_task = asyncio.create_task(
            write_stream(proc.stdin, ollama_response_queue, "Command STDIN")
        )

        # Create task for Ollama processing
        ollama_proc_task = asyncio.create_task(
            ollama_processor(ollama_model, command_output_queue, ollama_response_queue)
        )

        # Create task for user input (to gracefully exit)
        user_input_task = asyncio.create_task(
            handle_user_input(proc, command_output_queue, ollama_response_queue)
        )

        # Run all tasks concurrently
        await asyncio.gather(
            read_cmd_output_task,
            write_cmd_input_task,
            ollama_proc_task,
            user_input_task,
            return_exceptions=True # Allow other tasks to continue if one raises an exception
        )

        # Wait for the subprocess to finish
        await proc.wait()
        print(f"[Bridge] Command exited with code: {proc.returncode}")

    except FileNotFoundError:
        print(f"[Error] Command not found: {command_to_run[0]}")
    except Exception as e:
        print(f"[Critical Error] {e}")
    finally:
        # Ensure subprocess is terminated if it's still running
        if proc and proc.returncode is None:
            print("[Bridge] Cleaning up: Terminating subprocess...")
            proc.terminate()
            await proc.wait()


if __name__ == "__main__":
    # Ensure sys.stdout is unbuffered for immediate output
    # sys.stdout.reconfigure(line_buffering=True)
    asyncio.run(main())

