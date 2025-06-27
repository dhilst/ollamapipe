import argparse
import sys
from langchain_ollama import OllamaLLM as Ollama
from langchain_core.prompts import PromptTemplate
from colorama import Fore, Style, init  # Import colorama for colored terminal output
import time  # For adding a small delay in the loop


def main():
    """
    Main function to parse arguments, initialize Ollama, and run the agent chain.
    """
    # Initialize Colorama for cross-platform terminal coloring
    init(autoreset=True)

    parser = argparse.ArgumentParser(
        description="Create and run a chain of LangChain agents using Ollama.",
        # Use RawTextHelpFormatter for better formatting of multi-line help messages
        formatter_class=argparse.RawTextHelpFormatter,
    )
    parser.add_argument(
        "--model",
        action="append",  # Allows the --model argument to be used multiple times
        type=str,
        required=True,
        help="""Ollama model(s) to use (e.g., 'llama2', 'mistral', 'phi3').
        This argument can be used multiple times.
        If one model is specified, it will be used for all agents.
        If multiple models are specified, the Nth agent will use the Nth model.
        Ensure the model(s) are pulled using 'ollama pull <model_name>' before running.""",
    )
    parser.add_argument(
        "--task",
        type=str,
        required=True,
        help="The initial task or input for the first agent in the chain.",
    )
    parser.add_argument(
        "--agent",
        action="append",  # Allows the --agent argument to be used multiple times
        metavar="ROLE:PRE_PROPT",  # How the argument appears in help messages
        help="""Define an agent in the chain. This argument can be used multiple times
        to define a sequence of agents.
        Format: 'Role:Pre-prompt'.
        Example: --agent 'Summarizer:You are an expert summarizer.'
        The output of one agent becomes the input for the next agent in the chain.""",
    )
    parser.add_argument(
        "--loop",
        type=int,
        nargs="?",  # Makes the argument optional; if present without value, const is used
        const=1,  # Value if --loop is present without an argument (e.g., --loop)
        default=0,  # Value if --loop is not present at all
        help="""Number of times to loop the chain execution.
        Default: 0 (no looping, single execution).
        If present without a value (--loop), defaults to 1 loop.
        Use -1 for infinite looping.""",
    )
    parser.add_argument(
        "--no-history",
        action="store_true",  # This flag will be True if present, False otherwise
        help="If present, chat history (accumulated agent interactions within a chain run) will not be included in agent prompts.",
    )
    parser.add_argument(
        "--history-turns",
        type=int,
        default=4,  # Default to keeping the last 4 turns (2 user, 2 assistant)
        help="Maximum number of recent conversation turns (user+assistant pairs) to include in the history. Only applies if --no-history is not used.",
    )
    parser.add_argument(
        "--num-predict",
        type=int,
        default=-1,  # Default to -1, which means no limit on tokens for Ollama
        help="""Sets the number of tokens to predict for the Ollama model.
        Use -1 for unlimited prediction (default).""",
    )
    parser.add_argument(
        "--num-ctx",
        type=int,
        default=8192,  # Default context window size
        help="""Sets the context window size (num_ctx) for the Ollama model.
        This parameter corresponds to the 'num_ctx' setting in Ollama's Modelfile.
        Default: 8192.""",
    )

    args = parser.parse_args()

    # Ensure at least one agent is defined
    if not args.agent:
        print(
            f"{Fore.RED}Error: At least one agent must be defined using the --agent argument.{Style.RESET_ALL}",
            file=sys.stderr,
        )
        parser.print_help()
        sys.exit(1)

    # Inform about model usage strategy
    if len(args.model) == 1:
        print(f"--- Single Ollama model '{args.model[0]}' will be used for all agents. ---")
    else:
        print(
            f"--- Multiple Ollama models specified: {args.model}. Each agent will use a corresponding model. ---"
        )
        if len(args.model) < len(args.agent):
            print(
                f"{Fore.YELLOW}Warning: You have defined {len(args.agent)} agents but only {len(args.model)} models.",
                file=sys.stderr,
            )
            print(
                f"The remaining agents will use the last specified model: '{args.model[-1]}'.{Style.RESET_ALL}",
                file=sys.stderr,
            )

    # Define a list of colors that look good on dark terminals
    output_colors = [
        Fore.GREEN,  # For positive or general output
        Fore.CYAN,  # For informational or process output
        Fore.MAGENTA,  # For distinct steps or warnings
        Fore.YELLOW,  # For alerts or specific highlight
        Fore.BLUE,  # Another good general purpose color
    ]

    initial_task = args.task
    loop_iteration = 0
    final_output_from_prev_iteration = ""  # Initialize for the loop

    # Determine the number of iterations based on the --loop argument
    num_iterations = args.loop
    is_infinite_loop = False

    if num_iterations == -1:
        is_infinite_loop = True
    elif num_iterations == 0:  # If --loop was not provided (default 0), execute once
        num_iterations = 1
    # If num_iterations is > 0 (including the 'const=1' case), it runs that many times

    # Initialize chat history outside the loop to persist across iterations
    chain_run_history = []

    # Main loop for continuous execution if --loop flag is present
    while is_infinite_loop or (loop_iteration < num_iterations):
        loop_iteration += 1
        print(
            f"\n{Fore.WHITE}{Style.BRIGHT}--- {'Starting Loop Iteration' if is_infinite_loop or args.loop > 0 else 'Starting Chain'} {loop_iteration if is_infinite_loop or args.loop > 0 else ''} ---{Style.RESET_ALL}"
        )

        # Input for the first agent. If looping, it's the output of the previous loop's last agent.
        # Otherwise, it's the initial task.
        current_input_for_agent = (
            initial_task if loop_iteration == 1 else final_output_from_prev_iteration
        )

        print(f"\n--- Starting Chain with Input: '{current_input_for_agent}' ---\n")

        # Iterate through each defined agent in the order they were provided
        for i, agent_str in enumerate(args.agent):
            # Determine the color for the current agent's output
            current_color = output_colors[i % len(output_colors)]

            try:
                # Split the agent string into role and pre-prompt
                # Use .split(':', 1) to split only on the first colon, in case pre-prompt contains colons
                role, pre_prompt = agent_str.split(":", 1)
                role = role.strip()
                pre_prompt = pre_prompt.strip()
                if not role or not pre_prompt:
                    raise ValueError(
                        "Role and pre-prompt cannot be empty after stripping whitespace."
                    )
            except ValueError as e:
                print(
                    f"{Fore.RED}Error: Invalid agent format '{agent_str}'. Expected 'Role:Pre-prompt'. Details: {e}{Style.RESET_ALL}",
                    file=sys.stderr,
                )
                sys.exit(1)

            # Determine which model to use for the current agent
            current_model_name = ""
            if len(args.model) == 1:
                current_model_name = args.model[0]
            elif i < len(args.model):
                current_model_name = args.model[i]
            else:
                # If more agents than models, use the last specified model
                current_model_name = args.model[-1]
                print(
                    f"{Fore.YELLOW}  Note: Agent {i+1} is using the last specified model '{current_model_name}' as not enough unique models were provided.{Style.RESET_ALL}",
                    file=sys.stderr,
                )

            print(f"{current_color}--- Running Agent {i+1} ---{Style.RESET_ALL}")
            print(f"{current_color}  Role: {role}")
            print(f"{current_color}  Pre-prompt: {pre_prompt}")
            print(f"{current_color}  Model for this Agent: {current_model_name}")  # Display the model being used
            # Display num_predict if it's not the default -1
            if args.num_predict != -1:
                print(f"{current_color}  Max tokens to predict: {args.num_predict}")
            print(f"{current_color}  Input for this Agent: '{current_input_for_agent}'{Style.RESET_ALL}")

            try:
                # Initialize the Ollama LLM for the current agent with the determined model
                # Pass num_predict and num_ctx if they are set
                llm_params = {"model": current_model_name}
                if args.num_predict != -1:
                    llm_params["num_predict"] = args.num_predict
                
                # Add num_ctx to llm_params
                llm_params["num_ctx"] = args.num_ctx

                llm = Ollama(**llm_params)

                # Perform a quick test invocation to ensure Ollama is running and model is available
                print(
                    f"{current_color}  Attempting to connect to Ollama model '{current_model_name}'...{Style.RESET_ALL}"
                )
                _ = llm.invoke("Hello", stop=["."])  # Use a stop token to get a very short response
                print(f"{current_color}  Successfully connected to Ollama for this agent.{Style.RESET_ALL}")
            except Exception as e:
                print(
                    f"{Fore.RED}Error connecting to Ollama or model '{current_model_name}' not found for Agent {i+1}: {e}{Style.RESET_ALL}",
                    file=sys.stderr,
                )
                print(
                    f"{Fore.RED}Please ensure Ollama is running and the specified model is pulled (e.g., 'ollama pull llama2').{Style.RESET_ALL}",
                    file=sys.stderr,
                )
                sys.exit(1)

            # Construct the full prompt, conditionally including chat history
            composed_prompt_parts = []

            # If --no-history is NOT present, prepend the chain_run_history
            if not args.no_history and chain_run_history:
                # Apply history compaction: keep only the last N turns
                # Each turn consists of a user message and an assistant message
                # Note: 'history_turns' refers to user/assistant pairs, so we compact to 2 * turns for individual messages
                num_messages_to_keep_in_history = args.history_turns * 2
                compacted_history = chain_run_history[-num_messages_to_keep_in_history:]

                composed_prompt_parts.append("\n--- Conversation History Start ---\n")

                for hist_entry in compacted_history:
                    # Simple formatting for OllamaLLM to understand a "chat" format
                    composed_prompt_parts.append(
                        f"{hist_entry['role']}: {hist_entry['content']}\n"
                    )
                composed_prompt_parts.append("\n--- Conversation History End ---\n")

            composed_prompt_parts.append(
                f"{pre_prompt}\n\nYour task as {role} is to process the following input:\n{current_input_for_agent}"
            )
            full_prompt_text = "".join(composed_prompt_parts)

            # Estimate prompt size (word count as a proxy for tokens)
            current_prompt_size = len(full_prompt_text.split())
            print(f"{current_color}  Context Usage: {current_prompt_size}/{args.num_ctx} {current_prompt_size*100/args.num_ctx:.02f}% (approx. words/tokens){Style.RESET_ALL}")
            print(f"{current_color} PROMPT: {full_prompt_text} {Style.RESET_ALL}")
            prompt_template = PromptTemplate.from_template(full_prompt_text)

            print(
                f"{current_color}  Generating response using model '{current_model_name}' for Agent {i+1} ({role})...{Style.RESET_ALL}"
            )

            # --- START: Streaming Implementation ---
            response_chunks = []
            response_text = ""
            print(
                f"\n{current_color}{Style.BRIGHT}--- Agent {i+1} ({role}) Response (Streaming) ---{Style.RESET_ALL}\n{current_color}{Style.BRIGHT}",
                end="",
            )
            try:
                # Use llm.stream() instead of llm.invoke() for real-time output
                for chunk in llm.stream(prompt_template.format()):
                    # The chunk directly contains the string content for OllamaLLM
                    print(chunk, end="", flush=True)  # Print chunk and flush buffer
                    response_chunks.append(chunk)  # Append the string chunk directly
                response_text = "".join(
                    response_chunks
                )  # Join all chunks to get the full response
                print(f"{Style.RESET_ALL}\n")  # Reset style and add a final newline after streaming
            except Exception as e:
                print(
                    f"{Fore.RED}Error during LLM streaming invocation for Agent {i+1} ({role}): {e}{Style.RESET_ALL}",
                    file=sys.stderr,
                )
                print(
                    f"{Fore.RED}Please check the Ollama server logs for more details.{Style.RESET_ALL}",
                    file=sys.stderr,
                )
                sys.exit(1)
            # --- END: Streaming Implementation ---

            # Update history for the current chain run if --no-history is NOT present
            if not args.no_history:
                # Add the agent's 'query' (pre-prompt + input) as a 'user' turn
                chain_run_history.append(
                    {
                        "role": "user",
                        "content": f"Role: {role}, Pre-prompt: {pre_prompt}, Input: {current_input_for_agent}",
                    }
                )
                # Add the agent's response as an 'assistant' turn
                chain_run_history.append({"role": "assistant", "content": response_text})

            # The output of the current agent becomes the input for the next agent in the chain
            current_input_for_agent = response_text

        # This will be the input for the first agent in the next loop iteration (if --loop is on)
        final_output_from_prev_iteration = current_input_for_agent

        print(
            f"\n{Fore.GREEN}--- Chain execution complete for Loop Iteration {loop_iteration if is_infinite_loop or args.loop > 0 else ''} ---{Style.RESET_ALL}"
        )
        print(
            f"{Fore.GREEN}Final output of this iteration:\n{final_output_from_prev_iteration}{Style.RESET_ALL}"
        )

        if not is_infinite_loop:
            if loop_iteration == num_iterations:
                break  # Exit the loop if not infinite and current iteration matches target
        else:
            print(
                f"\n{Fore.WHITE}Sleeping for a few seconds before next loop iteration... (Press Ctrl+C to stop){Style.RESET_ALL}"
            )
            time.sleep(
                5
            )  # Small delay to make loops readable and prevent rapid API calls


if __name__ == "__main__":
    main()
