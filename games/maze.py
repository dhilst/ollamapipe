import random
from collections import deque

DIRECTIONS = ['north', 'south', 'east', 'west']
ITEMS = ['red key', 'yellow key', 'blue key', 'food', 'water']
KEY_ORDER = ['red key', 'yellow key', 'blue key']

class Room:
    def __init__(self):
        self.items = []
        self.fountain = False

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
        # Place keys in order along the path
        self.grid[path[3][0]][path[3][1]].items.append('red key')
        self.grid[path[6][0]][path[6][1]].items.append('yellow key')
        self.grid[path[9][0]][path[9][1]].items.append('blue key')

        # Place fountain along path before first key
        self.grid[path[2][0]][path[2][1]].fountain = True

        # Place 3 food along the path randomly
        food_indices = random.sample(range(len(path)), 3)
        for idx in food_indices:
            x, y = path[idx]
            self.grid[x][y].items.append('food')

        # Rare food spawn elsewhere
        for x in range(self.size):
            for y in range(self.size):
                if (x, y) not in path and random.random() < 0.01:
                    self.grid[x][y].items.append('food')

    def generate_path(self):
        x, y = 0, 0
        path = [(x, y)]
        visited = set(path)
        while len(path) < 12:
            neighbors = []
            for dx, dy in [(-1,0), (1,0), (0,-1), (0,1)]:
                nx, ny = x + dx, y + dy
                if 0 <= nx < self.size and 0 <= ny < self.size and (nx, ny) not in visited:
                    neighbors.append((nx, ny))
            if not neighbors:
                break  # Dead end, but should not happen with size 5 and short paths
            x, y = random.choice(neighbors)
            visited.add((x, y))
            path.append((x, y))
        return path

    def get_room(self, x, y):
        return self.grid[x][y]

class Player:
    def __init__(self, maze):
        self.x = 0
        self.y = 0
        self.health = 100
        self.inventory = []
        self.keys_collected = []
        self.turns = 0
        self.maze = maze
        self.has_water = False

    def move(self, direction):
        dx, dy = {'north': (-1, 0), 'south': (1, 0), 'west': (0, -1), 'east': (0, 1)}.get(direction, (0, 0))
        new_x = self.x + dx
        new_y = self.y + dy
        if 0 <= new_x < self.maze.size and 0 <= new_y < self.maze.size:
            self.x = new_x
            self.y = new_y
            self.turns += 1
            if self.turns % 3 == 0:
                self.health -= 5
            return f"[Dungeon Master] You moved {direction}. {self.look()}"
        else:
            return "[Dungeon Master] You can't go that way."

    def current_room(self):
        return self.maze.get_room(self.x, self.y)

    def look(self):
        return self.current_room().describe()

    def pick(self):
        room = self.current_room()
        if not room.items and not room.fountain:
            return "[Dungeon Master] There's nothing to pick up."
        output = []
        for item in room.items[:]:
            if item == 'food':
                self.inventory.append('food')
                room.items.remove(item)
                output.append("[Dungeon Master] Picked up food.")
            elif item in KEY_ORDER:
                self.keys_collected.append(item)
                output.append(f"[Dungeon Master] Picked up {item}.")
                room.items.remove(item)
        if room.fountain:
            self.has_water = True
            room.fountain = False
            output.append("[Dungeon Master] You filled your bottle with water.")
        return "\n".join(output) if output else "[Dungeon Master] There's nothing you can pick up right now."

    def inventory_status(self):
        items = self.inventory.copy()
        if self.has_water:
            items.append("water")
        return "[Dungeon Master] Inventory: " + ", ".join(items) if items else "[Dungeon Master] Inventory is empty."

    def status(self):
        return f"[Dungeon Master] Location: ({self.x},{self.y}) | Health: {self.health} | Keys: {', '.join(self.keys_collected)}"

    def eat(self):
        if 'food' in self.inventory:
            self.inventory.remove('food')
            self.health = min(100, self.health + 20)
            return f"[Dungeon Master] You ate some food. Health is now {self.health}."
        return "[Dungeon Master] You have no food."

    def drink(self):
        if self.has_water:
            self.has_water = False
            self.health = min(100, self.health + 10)
            return f"[Dungeon Master] You drank water. Health is now {self.health}."
        return "[Dungeon Master] You have no water."

    def use(self, item):
        item = item.lower()
        if item in self.keys_collected and item == 'blue key' and len(self.keys_collected) == 3:
            return "[Dungeon Master] You used the blue key and escaped the maze! 🎉"
        return f"[Dungeon Master] You can't use {item} now."

GAME_HELP = """
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
   use blue key
   to escape the maze and win!

🔐 Keys and Doors
- You cannot collect keys out of order.
- Keys are symbolic doors; collect them to unlock the path forward.

🧭 Movement
Use these commands to move:
  north, south, east, west
Each move counts as one turn.

🔎 Maze Interaction Commands
  look         - Describe the current room.
  pick         - Pick up visible items or water.
  inventory    - Show what you’re carrying.
  status       - Show health, location, and keys.
  eat          - Eat food to restore 20 health.
  drink        - Drink water to restore 10 health.
  use <item>   - Use an item like 'use blue key'.
  help         - Show this help message.

❤️ Health & Survival
- You start with 100 health.
- Every 3 turns, you lose 5 health due to fatigue.
- Restore health by:
  • Eating food (+20 health)
  • Drinking water (+10 health)
- Water is collected from fountains via 'pick'.
- You can only carry one water at a time.
- If health reaches 0, you die and lose.

🍽️ Food & Water
- 3 foods spawn at game start in random rooms.
- Additional food has a 1% chance to appear in any room.
- There's only one fountain per maze.
- Don’t forget to refill your water!

🧠 Output 

- You control the player by typing simple words commands.
- All your answers will have up to 3 words
  where the allowed words are in the 'Maze Interaction Commands',
- Do not explaing or start a conversation, you're a
  controller for a player, not a reasoner, simply output
  the next command (a single word), nothign more.

🧠 Tips to Win
✔ Explore every room
✔ Move efficiently—wasted moves cost health.
✔ Keep track of visited locations.
✔ Prioritize survival: food and water are rare.
✔ Always get water when you find a fountain.
✔ Only collect keys in order: red → yellow → blue.
✔ Preffer moving around, exploring and picking 
✔ Pick up food before eat
✔ Ask for help frequently

💀 How to Lose
✘ Starving: Health drops to 0 from exhaustion.
✘ Skipping resources when you find them.
✘ Wandering aimlessly without progress.

🔎 Interaction Examples
[Dungeon Master] What is your command? north
[Dungeon Master] What is your command? south
[Dungeon Master] What is your command? east
[Dungeon Master] What is your command? west
[Dungeon Master] What is your command? status
[Dungeon Master] What is your command? eat
[Dungeon Master] What is your command? drink
[Dungeon Master] What is your command? look
[Dungeon Master] What is your command? use yellow key
[Dungeon Master] What is your command? use red key
[Dungeon Master] What is your command? use blue key
[Dungeon Master] What is your command? pick
[Dungeon Master] What is your command? look

[Dungeon Master] You see: food
[Dungeon Master] What is your command? pick
[Dungeon Master] You see: food
[Dungeon Master] What is your command? pick
[Dungeon Master] You see: fontain 
[Dungeon Master] What is your command? pick
[Dungeon Master] You see: key  
[Dungeon Master] What is your command? pick

[Dungeon Master] Inventory: red key, yellow key, blue key
[Dungeon Master] What is your command? use blue key

Think carefully. Move tactically. Watch your health.
Type any command to begin... or type 'help' to see this message again.
"""

def main():
    maze = Maze()
    player = Player(maze)

    print("[Dungeon Master] Welcome to the Maze Escape!")
    print("[Dungeon Master] Commands: north, south, east, west, look, pick, inventory, status, eat, drink, help use <item>\n")
    print(GAME_HELP)

    while True:
        if player.health <= 0:
            print("You collapsed from exhaustion. Game over.")
            break
        print("[Dungeon Master] What is your command?")
        print("THE END OF PROMPT")
        cmd = input(">> ").strip().lower()
        if cmd.startswith("use "):
            item = cmd[4:]
            result = player.use(item)
            print(result)
            if "escaped" in result:
                break
        elif cmd in DIRECTIONS:
            print(player.move(cmd))
        elif cmd == "look":
            print(player.look())
        elif cmd == "pick":
            print(player.pick())
        elif cmd == "inventory":
            print(player.inventory_status())
        elif cmd == "status":
            print(player.status())
        elif cmd == "eat":
            print(player.eat())
        elif cmd == "drink":
            print(player.drink())
        elif cmd == "help":
            print(GAME_HELP)
        else:
            print("[Dungeon Master] Unknown command. Type 'help' for assistance.")


if __name__ == "__main__":
    main()
