import random
from collections import deque
import pygame

# Pygame Initialization Constants
SCREEN_WIDTH = 700 # Increased width to accommodate status bar text
SCREEN_HEIGHT = 700 # Increased height for status bar
TILE_SIZE = 100 # Size of each room tile in pixels
GRID_OFFSET_X = (SCREEN_WIDTH - 5 * TILE_SIZE) // 2 # Center the grid horizontally
# Offset for status bar, making room at the bottom for UI
GRID_OFFSET_Y = (SCREEN_HEIGHT - 5 * TILE_SIZE - 100) // 2
STATUS_BAR_HEIGHT = 100 # Height of the status bar at the bottom

# Colors (RGB tuples)
WHITE = (255, 255, 255)
BLACK = (0, 0, 0)
GRAY = (150, 150, 150)
LIGHT_GRAY = (200, 200, 200) # Base color for room background
DARK_GRAY = (50, 50, 50)
RED = (255, 0, 0)
YELLOW = (255, 255, 0)
BLUE = (0, 0, 255)
BROWN = (139, 69, 19) # Color for food items
PLAYER_COLOR = (0, 255, 0) # Green color for the player dot

# Mapping of item names to their respective display colors
ITEM_COLORS = {
    'red key': RED,
    'yellow key': YELLOW,
    'blue key': BLUE,
    'food': BROWN,
    'water': BLUE # Water from a fountain
}

DIRECTIONS = ['north', 'south', 'east', 'west']
ITEMS = ['red key', 'yellow key', 'blue key', 'food', 'water']
KEY_ORDER = ['red key', 'yellow key', 'blue key']

class Room:
    def __init__(self):
        self.items = []
        self.fountain = False
        self.visit_count = 0 # Added to track how many times this room has been visited

    def describe(self):
        if self.fountain:
            return "[Dungeon Master] You hear water flowing nearby. There's a fountain here."
        if self.items:
            return f"[Dungeon Master] You see: {', '.join(self.items)}"
        return "[Dungeon Master] The room is empty."

class Maze:
    def __init__(self, size=5):
        self.size = size
        self.grid = [[Room() for _ in range(size)] for _ in range(size)]
        self.ensure_solvable_layout()

    def ensure_solvable_layout(self):
        path = self.generate_path()
        # Place keys in order along the path to ensure solvability
        self.grid[path[3][0]][path[3][1]].items.append('red key')
        self.grid[path[6][0]][path[6][1]].items.append('yellow key')
        self.grid[path[9][0]][path[9][1]].items.append('blue key')

        # Place fountain along path before the first key
        self.grid[path[2][0]][path[2][1]].fountain = True

        # Place 3 food items randomly along the generated path
        food_indices = random.sample(range(len(path)), 3)
        for idx in food_indices:
            x, y = path[idx]
            self.grid[x][y].items.append('food')

        # Rarely spawn additional food elsewhere in the maze (1% chance per room)
        for x in range(self.size):
            for y in range(self.size):
                if (x, y) not in path and random.random() < 0.01:
                    self.grid[x][y].items.append('food')

    def generate_path(self):
        # Generates a simple path to ensure keys and fountain are accessible
        x, y = 0, 0
        path = [(x, y)]
        visited = set(path)
        while len(path) < 12: # Ensure a sufficiently long path for items
            neighbors = []
            for dx, dy in [(-1,0), (1,0), (0,-1), (0,1)]: # Possible directions (N, S, W, E)
                nx, ny = x + dx, y + dy
                # Check bounds and if the neighbor has not been visited
                if 0 <= nx < self.size and 0 <= ny < self.size and (nx, ny) not in visited:
                    neighbors.append((nx, ny))
            if not neighbors:
                break  # Dead end, should not typically happen with a size 5 maze and short path
            x, y = random.choice(neighbors) # Move to a random unvisited neighbor
            visited.add((x, y))
            path.append((x, y))
        return path

    def get_room(self, x, y):
        return self.grid[x][y]

class Player:
    def __init__(self, maze):
        self.x = 0 # Player's current row (0-indexed)
        self.y = 0 # Player's current column (0-indexed)
        self.score = 0
        self.health = 100
        self.inventory = [] # Stores food items
        self.keys_collected = [] # Stores collected keys in order
        self.turns = 0
        self.maze = maze
        self.has_water = False # True if player has water in their bottle
        self.hints = []
        self.visited_rooms = set() # Store (x, y) coordinates of visited rooms
        self.penalty_rewards_history = deque(maxlen=10) # Stores last 10 penalty/reward messages
        self.saw_items_history = deque(maxlen=10) # Stores last 10 saw items and their locations


        self.move_reward = 3
        self.move_penality = 1 # Base penalty for revisiting a room
        self.look_reward = -2
        self.take_reward = 1
        self.eat_reward = 1
        self.hints_reward = 5
        self.win_reward = 50


    def add_hint(self, hint):
        self.update_score(self.hints_reward, f"hint: {hint}")
        self.hints.append(hint)

    def update_score(self, score, action_description): # Renamed 'action' to 'action_description'
        old_score = self.score
        self.score += score
        
        emoji_str = ""
        if score > 0:
            emoji_str = "⭐" * int(score)
            message_type = "Reward"
        else:
            emoji_str = "🔴" * int(abs(score))
            message_type = "Penalty"
            
        message = f"{message_type} for <{action_description}> {emoji_str}" # Use action_description here
        self.penalty_rewards_history.append(message)
        print(f"[Dungeon Master] {message}")


    def move(self, direction):
        # Map direction strings to (dx, dy) changes
        dx, dy = {'north': (-1, 0), 'south': (1, 0), 'west': (0, -1), 'east': (0, 1)}.get(direction, (0, 0))
        new_x = self.x + dx
        new_y = self.y + dy
         
        # Check if the new position is within maze bounds
        if 0 <= new_x < self.maze.size and 0 <= new_y < self.maze.size:
            # Increment visit count for the *new* room
            self.maze.grid[new_x][new_y].visit_count += 1 

            self.x = new_x
            self.y = new_y
            self.turns += 1

            # Penalize moving to an already visited room
            if (self.x, self.y) in self.visited_rooms:
                self.update_score(-self.move_penality, f"{direction} (revisit)") # Base penalty
            else:
                self.visited_rooms.add((self.x, self.y)) # Mark current room as visited
                self.move_reward += 2
                self.update_score(self.move_reward, f"{direction}")
             
            # Player loses health every 3 turns
            if self.turns % 3 == 0:
                self.health -= 5
            return f"[Dungeon Master] You moved {direction}. {self.look(move=True)}"
        else:
            # Invalid move penalty is double the already visited penalty
            self.update_score(-2 * self.move_penality, f"{direction} (invalid)") 
            return "[Dungeon Master] You can't go that way."

    def current_room(self):
        # Returns the Room object at the player's current coordinates
        return self.maze.get_room(self.x, self.y)

    def look(self, move=False):
        # Describes the current room
        if not move:
            self.look_reward *= 1.1
            self.update_score(self.look_reward, "look")

        room = self.current_room()
        description = []

        # Check available directions
        available_directions = []
        for direction in DIRECTIONS:
            dx, dy = {'north': (-1, 0), 'south': (1, 0), 'west': (0, -1), 'east': (0, 1)}.get(direction, (0, 0))
            new_x = self.x + dx
            new_y = self.y + dy
            if 0 <= new_x < self.maze.size and 0 <= new_y < self.maze.size:
                available_directions.append(direction)
         
        if available_directions:
            description.append(f"You can move: {', '.join(available_directions)}.")
        else:
            description.append("You are trapped! There's no way out from here.")

        # Check items in the room
        if room.fountain:
            description.append("You hear water flowing nearby. There's a fountain here.")
            self.saw_items_history.append(f"Fountain at ({self.x},{self.y})")
        if room.items:
            items_str = ', '.join(room.items)
            description.append(f"You see: {items_str}.")
            self.saw_items_history.append(f"Items: {items_str} at ({self.x},{self.y})")
         
        if not room.items and not room.fountain:
            description.append("The room is empty.")

        return "[Dungeon Master] " + " ".join(description)

    def take(self):
        room = self.current_room()
        if not room.items and not room.fountain:
            self.take_reward *= 1.5
            self.update_score(-self.take_reward, "take (nothing)")
            return "[Dungeon Master] There's nothing to take up."
         
        output = []
        # Iterate through items in the room to take them up
        for item in room.items[:]: # Use a slice to iterate over a copy, allowing modification
            if item == 'food':
                self.update_score(self.take_reward, "take food")
                self.inventory.append('food')
                room.items.remove(item)
                output.append("[Dungeon Master] takeed up food.")
                # Remove from saw_items_history if present
                for history_entry in list(self.saw_items_history): # Iterate over a copy
                    if f"Items: food at ({self.x},{self.y})" in history_entry:
                        self.saw_items_history.remove(history_entry)
                        break
            elif item in KEY_ORDER:
                # Check if the key is the next one in the required collection order
                current_key_index = len(self.keys_collected)
                if KEY_ORDER.index(item) == current_key_index:
                    self.update_score(self.take_reward * 10, f"take {item}")
                    self.keys_collected.append(item)
                    output.append(f"[Dungeon Master] takeed up {item}.")
                    room.items.remove(item)
                    # Remove from saw_items_history if present
                    for history_entry in list(self.saw_items_history):
                        if f"Items: {item} at ({self.x},{self.y})" in history_entry: # Check for the specific item
                            self.saw_items_history.remove(history_entry)
                            break
                else:
                    self.update_score(-self.take_reward, f"take {item} (wrong order)")
                    output.append(f"[Dungeon Master] You can't take up the {item} yet. You need to collect keys in order: Red, Yellow, Blue.")
         
        # Handle taking up water from a fountain
        if room.fountain:
            self.has_water = True
            room.fountain = False # Fountain is depleted after use
            self.update_score(self.take_reward, "take water")
            output.append("[Dungeon Master] You filled your bottle with water.")
            # Remove fountain entry from saw_items_history
            for history_entry in list(self.saw_items_history):
                if f"Fountain at ({self.x},{self.y})" in history_entry:
                    self.saw_items_history.remove(history_entry)
                    break
         
        return "\n".join(output) if output else "[Dungeon Master] There's nothing you can take up right now."


    def inventory_status(self):
        items = self.inventory.copy()
        if self.has_water:
            items.append("water") # Add water to display if player has it
        return "[Dungeon Master] Inventory: " + ", ".join(items) if items else "[Dungeon Master] Inventory is empty."

    def status(self):
        return f"[Dungeon Master] Location: ({self.x},{self.y}) | Health: {self.health} | Keys: {', '.join(self.keys_collected)}"

    def eat(self):
        if 'food' in self.inventory:
            self.update_score(self.eat_reward, "eat")
            self.inventory.remove('food')
            self.health = min(100, self.health + 20) # Restore 20 health, max 100
            return f"[Dungeon Master] You ate some food. Health is now {self.health}."
        return "[Dungeon Master] You have no food."

    def drink(self):
        if self.has_water:
            self.update_score(self.eat_reward, "drink")
            self.has_water = False
            self.health = min(100, self.health + 10) # Restore 10 health, max 100
            return f"[Dungeon Master] You drank water. Health is now {self.health}."
        return "[Dungeon Master] You have no water."

    def finish(self):
        if ("blue key" in self.keys_collected
            and "yellow key" in self.keys_collected
            and "red key" in self.keys_collected):
            self.update_score(self.win_reward, "finish (win)")
            return "[Dungeon Master] You used the blue key and escaped the maze! 🎉"
        else:
            self.update_score(-2, "finish (no blue key)")
            return "[Dungeon Master] You don't have the blue key, you need it"

GAME_COMMANDS = """
🔎 Maze Interaction Commands
  look         - Describe the current room.
  take         - Pick up visible items or water.
  inventory    - Show what you’re carrying.
  status       - Show health, location, and keys.
  eat          - Eat food to restore 20 health.
  drink        - Drink water to restore 10 health.
  finish       - Use the blue key in your inventory to get out of the maze
  help         - Show this help message.
"""

GAME_HELP = f"""
[Dungeon Master]
🧭 Welcome to the Maze Escape Survival!

You’ve awoken inside a mysterious, randomly-generated maze with no memory of how you got here.
Your goal: escape alive by exploring the maze, collecting key items, and surviving its harsh conditions.

🌍 Environment
- The maze is a grid of interconnected rooms.
- Each room may contain:
  • Nothing (empty)
  • A fountain (source of water)
  • One of the three colored keys: red, yellow, blue
  • Food (very rare)
- The layout and contents are random every game.

🎯 Objective
Your mission is to:
1. Explore the maze room by room.
2. Collect the keys in a strict order:
   🔴 Red Key → 🟡 Yellow Key → 🔵 Blue Key
3. Once all keys are collected, use:
   finish to escape the maze and win!!!!!

Use finish once you have the blue key

🔐 Keys and Doors
- You need to collect keys in order.
- Once you have all the keys, use the blue key to finish the puzzle

🧭 Movement
Use these commands to move:
  north, south, east, west

Each move counts as one turn.

{GAME_COMMANDS}

❤️ Health & Survival
- You start with 100 health.
- Every 3 turns, you lose 5 health due to fatigue.
- Restore health by:
  • Eating food (+20 health)
  • Drinking water (+10 health)
- Water is collected from fountains via 'take'.
- You can only carry one water at a time.
- If health reaches 0, you die and lose.
- You receive rewards for good actions and penalities for bad actions
  optimize for max score

🍽️ Food & Water
- 3 foods spawn at game start in random rooms.
- Additional food has a 1% chance to appear in any room.
- There's only one fountain per maze.
- Don’t forget to refill your water!

Instructions:
1. Take the red key
2. Take the yellow key
3. Take the blue key
4. Use the blue key

🧠 Output 

- You control the player by typing simple words commands.
- All your answers will have up to 3 words
  where the allowed words are in the 'Maze Interaction Commands',
- Do not explaing or start a conversation, you're a
  controller for a player, not a reasoner, simply output
  the next command (a single word), nothign more.

🧠 Tips to Win
✔ Explore every room
✔ Keep track of visited locations.
✔ Prioritize survival: food and water are rare.
✔ Always get water when you find a fountain.
✔ Only collect keys in order: red → yellow → blue.
✔ Preffer moving around, exploring and takeing 
✔ take up food before eat
✔ Maximize rewards and score
✔ Minimize penalities 
✔ You no longer have 'hint' command.

💀 How to Lose
✘ Starving: Health drops to 0 from exhaustion.
✘ Skipping resources when you find them.
✘ Wandering aimlessly without progress.

🎯 Task
- Win the game


🔎 Interaction Examples

Here are a list of examples of interations between
the dungeon master and the player. Use them as
referece, you should mimick the player commands, not
behavior. You must find the propper behavior that
leads out of the maze.

[Dungeon Master] What is your command? east
[Dungeon Master] What is your command? south
[Dungeon Master] What is your command? west
[Dungeon Master] What is your command? north
[Dungeon Master] What is your command? look
[Dungeon Master] What is your command? east
[Dungeon Master] What is your command? take
[Dungeon Master] What is your command? south
[Dungeon Master] What is your command? west
[Dungeon Master] What is your command? north
[Dungeon Master] What is your command? take
[Dungeon Master] What is your command? eat
[Dungeon Master] What is your command? south
[Dungeon Master] What is your command? east
[Dungeon Master] What is your command? west
[Dungeon Master] What is your command? north
[Dungeon Master] What is your command? drink
[Dungeon Master] What is your command? take
[Dungeon Master] What is your command? finish

[Dungeon Master] You see: food
[Dungeon Master] What is your command? take
[Dungeon Master] takeed up food.
[Dungeon Master] What is your command? eat
[Dungeon Master] You see: fontain 
[Dungeon Master] What is your command? take
[Dungeon Master] You see: key    
[Dungeon Master] What is your command? take
[Dungeon Master] What is your command? take

[Dungeon Master] Keys: red key, yellow key, blue key
[Dungeon Master] What is your command? finish

Think carefully. Move tactically. Watch your health.
Maximize your score. Type any command to begin...
"""

def draw_game_state(screen, maze, player, font_small, font_medium):
    """
    Renders the current state of the game on the Pygame screen.
    Includes the maze grid, items, player, and status bar.
    """
    # Fill the background of the screen
    screen.fill(DARK_GRAY)

    # Draw maze grid and items within each room
    for row in range(maze.size):
        for col in range(maze.size):
            # Calculate the top-left pixel coordinates for the current tile
            x = GRID_OFFSET_X + col * TILE_SIZE
            y = GRID_OFFSET_Y + row * TILE_SIZE
             
            # Calculate room color based on visit count
            room = maze.get_room(row, col)
            darkening_step = 15 # Adjust this value to control how quickly it darkens
            current_r = max(50, LIGHT_GRAY[0] - (room.visit_count * darkening_step))
            current_g = max(50, LIGHT_GRAY[1] - (room.visit_count * darkening_step))
            current_b = max(50, LIGHT_GRAY[2] - (room.visit_count * darkening_step))
            room_color = (current_r, current_g, current_b)

            # Draw the background of the room tile with rounded corners
            pygame.draw.rect(screen, room_color, (x, y, TILE_SIZE, TILE_SIZE), 0, 5) 
            # Draw a border around the room tile
            pygame.draw.rect(screen, GRAY, (x, y, TILE_SIZE, TILE_SIZE), 3, 5) 

            item_draw_offset = 0 # Offset to draw multiple items in a room
             
            # Draw fountain if present in the room
            if room.fountain:
                # Position the fountain circle near the center of the tile
                item_x = x + TILE_SIZE // 2 - 10 
                item_y = y + TILE_SIZE // 2 - 10
                # Draw a blue circle for the fountain
                pygame.draw.circle(screen, ITEM_COLORS['water'], (item_x, item_y), 10)
                item_draw_offset += 25 # Move offset for the next item to avoid overlap

            # Draw other items (keys, food) present in the room
            for item in room.items:
                # Get the color for the current item, default to black if not defined
                color = ITEM_COLORS.get(item, BLACK) 
                # Position for the item, using the offset
                item_x = x + 10 + item_draw_offset
                item_y = y + 10
                # Draw a small colored square for the item
                pygame.draw.rect(screen, color, (item_x, item_y, 15, 15), 0, 3) 
                item_draw_offset += 25 # Increment offset for the next item


    # Draw the player character
    # Player's Y (column) maps to Pygame X, Player's X (row) maps to Pygame Y
    player_x_display = GRID_OFFSET_X + player.y * TILE_SIZE + TILE_SIZE // 2 
    player_y_display = GRID_OFFSET_Y + player.x * TILE_SIZE + TILE_SIZE // 2 
    # Draw a green circle for the player
    pygame.draw.circle(screen, PLAYER_COLOR, (player_x_display, player_y_display), TILE_SIZE // 3)

    # Draw the status bar at the bottom of the screen
    status_bar_y = SCREEN_HEIGHT - STATUS_BAR_HEIGHT
    pygame.draw.rect(screen, BLACK, (0, status_bar_y, SCREEN_WIDTH, STATUS_BAR_HEIGHT))
     
    # Render player's health
    health_text = font_medium.render(f"Health: {player.health}", True, WHITE)
    screen.blit(health_text, (20, status_bar_y + 10)) # Position health text

    # Render player's inventory
    inventory_items = player.inventory.copy()
    if player.has_water:
        inventory_items.append("water") # Add "water" to inventory display if player carries it
    inventory_text = font_small.render(f"Inventory: {', '.join(inventory_items) if inventory_items else 'Empty'}", True, WHITE)
    screen.blit(inventory_text, (20, status_bar_y + 40)) # Position inventory text

    # Render collected keys
    keys_text = font_small.render(f"Keys: {', '.join(player.keys_collected) if player.keys_collected else 'None'}", True, WHITE)
    screen.blit(keys_text, (20, status_bar_y + 65)) # Position keys text

    # Update the full display surface to the screen
    pygame.display.flip()


def main():
    # Initialize all Pygame modules
    pygame.init()
    # Set up the display screen with defined width and height
    screen = pygame.display.set_mode((SCREEN_WIDTH, SCREEN_HEIGHT))
    # Set the title of the Pygame window
    pygame.display.set_caption("Maze Escape Survival")

    # Initialize fonts for displaying status information
    font_small = pygame.font.SysFont("Arial", 18)
    font_medium = pygame.font.SysFont("Arial", 24, bold=True)

    # Create the maze and player objects
    maze = Maze()
    player = Player(maze)
    # Increment visit count for the starting room
    player.maze.grid[player.x][player.y].visit_count += 1
    player.visited_rooms.add((player.x, player.y)) # Mark starting room as visited

    # Print initial game messages to the console
    print("[Dungeon Master] Welcome to the Maze Escape!")
    print("[Dungeon Master] Commands: north, south, east, west, look, take, inventory, status, eat, drink, help use <item>\n")
    print(GAME_HELP)

    # Perform the initial drawing of the game state on the Pygame window
    draw_game_state(screen, maze, player, font_small, font_medium)

    running = True # Control variable for the main game loop
    while running:
        # Event handling for Pygame window (e.g., closing the window)
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                running = False # Set running to False to exit the game loop
                break # Exit the inner event loop

        if not running: # If the window was closed, break out of the main game loop
            break
             
        # Check player's health to determine game over
        if player.health <= 0:
            print("You collapsed from exhaustion. Game over.")
            running = False # End the game
            break

        # Print saw items history
        print("\n--- Last 10 Saw Items and Locations ---")
        if not player.saw_items_history:
            print("[Dungeon Master] No items seen yet.")
        else:
            for entry in player.saw_items_history:
                print(f"[Dungeon Master] {entry}")
        print("---------------------------------------")

        # Print penalty/reward history
        print("\n--- Last 10 Penalties/Rewards ---")
        if not player.penalty_rewards_history:
            print("[Dungeon Master] No penalties or rewards recorded yet.")
        else:
            for entry in player.penalty_rewards_history:
                print(f"[Dungeon Master] {entry}")
        print("---------------------------------")

        # Prompt for user input in the console
        print(f"[Dungeon Master] Keys: {', '.join(player.keys_collected)}")
        if (player.hints):
            for hint in player.hints:
                print("Hint: ", hint)
         
        print("[Dungeon Master] What is your command?")
        print("THE END OF PROMPT") # Marker from original code, kept as is
         
        # Get command from user via console input. This will block the Pygame window
        # updates until input is received. This is intentional to preserve original behavior.
        inp = input(">> ").strip()
        cmd = inp.lower() 
         
        result = "" # Variable to hold the output message from game actions

        # Process the user command
        if cmd == "finish":
            result = player.finish()
            print(result)
        elif cmd in DIRECTIONS:
            result = player.move(cmd)
            print(result)
        elif cmd == "look":
            result = player.look()
            print(result)
        elif cmd == "take":
            result = player.take()
            print(result)
        elif cmd == "inventory":
            result = player.inventory_status()
            print(result)
        elif cmd == "status":
            result = player.status()
            print(result)
        elif cmd == "eat":
            result = player.eat()
            print(result)
        elif cmd == "drink":
            result = player.drink()
            print(result)
        elif cmd.startswith("hint"):
            player.add_hint(inp[len("hint")+1:].strip())
        elif cmd == "help":
            print(GAME_HELP)
        else:
            print(f"[Dungeon Master] Unknown command {cmd}")
            print("[Dungeon Master] Use one of the valid commands:")
            print(GAME_COMMANDS)
            player.update_score(-10, f"unknown command: {cmd}")
         
        # Redraw the game state on the Pygame window after each command is processed
        draw_game_state(screen, maze, player, font_small, font_medium)

    # Quit Pygame modules when the main game loop finishes
    pygame.quit() 

if __name__ == "__main__":
    main()
