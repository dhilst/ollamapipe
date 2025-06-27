import time
import random

class VirtualPet:
    def __init__(self, name):
        self.name = name
        self.hunger = 0
        self.max_hunger = 10
        self.health = 100
        self.weight = 5.0
        self.diseased = False
        self.disease_duration = 0
        self.mood = "happy"

    def feed(self):
        if self.hunger > 0:
            self.hunger -= 1
            self.weight += 0.2
            print(f"You fed {self.name}. Hunger: {self.hunger}, Weight: {self.weight:.1f}kg")
            if self.weight > 8.0:
                self.health -= 5
                print(f"{self.name} is overweight! Health drops to {self.health}")
        else:
            self.health -= 5
            print(f"{self.name} didn't need food. Health drops to {self.health}")

    def play(self):
        if self.mood == "happy":
            print(f"You played with {self.name} it is happier now")
            self.health += 5
            self.weight -= 1
        else:
            print(f"{self.name} is {self.mood}, it does not want to play now")

    def get_hungry(self):
        self.hunger += 1
        if self.hunger >= self.max_hunger:
            self.health -= 10
            print(f"{self.name} is starving! Health drops to {self.health}")
        elif self.hunger > 4:
            print(f"{self.name} is hungry! Feed it!")
        else:
            print(f"{self.name} is satisfied. Hunger level: {self.hunger}")

    def maybe_get_sick(self):
        if not self.diseased and random.random() < 0.1:
            self.diseased = True
            self.disease_duration = 0
            self.health -= 20
            print(f"{self.name} caught a disease! Health: {self.health}")

    def treat(self, current_minute):
        if not self.diseased:
            print(f"{self.name} is not sick.")
            return

        if current_minute % 3 == 0:
            self.diseased = False
            self.disease_duration = 0
            print(f"You successfully treated {self.name}. They're feeling better!")
        else:
            self.health -= 10
            next_time = current_minute + (current_minute % 3)
            print(f"The medicine didn’t work. Wrong timing! Next time is {next_time} Health: {self.health}")

    def worsen_disease(self):
        if self.diseased:
            self.disease_duration += 1
            if self.disease_duration % 3 == 0:
                self.health -= 5
                print(f"{self.name}'s disease is getting worse... Health: {self.health}")

    def status(self):
        self.mood = "happy" if self.hunger < 5 and self.health > 70 else "unwell"
        weight_status = "normal"
        if self.weight < 4.0:
            weight_status = "underweight"
        elif self.weight > 8.0:
            weight_status = "overweight"

        disease_status = "Yes" if self.diseased else "No"

        print(f"\nStatus of {self.name}:")
        print(f"  Hunger: {self.hunger}/{self.max_hunger}")
        print(f"  Health: {self.health}/100")
        print(f"  Weight: {self.weight:.1f}kg ({weight_status})")
        print(f"  Diseased: {disease_status}")
        print(f"  Mood: {self.mood}")

    def is_alive(self):
        return self.health > 0

def main():
    pet = VirtualPet(random.choice(["Fluffy", "Sparky", "Nibbles", "Mochi"]))

    minute = 1
    while pet.is_alive():
        print("--------START OF ROUND -----------")
        print(f"You adopted {pet.name}!")
        print("Commands: feed, treat, status, play\n")
        print("Help:")
        print("""
Your pet need to be feed and maintained happy. But take caution,
the vet said that overfeeding may cause overweigth which can causes
dieases. It may ocasionally get sick too, you need to treat it multiple
times so it get better. You can also play with your pet, it will
increase health if it is not tired, and descrease the weight.
              """)
        print(f"\n--- Minute {minute} ---")
        pet.get_hungry()
        pet.maybe_get_sick()
        pet.worsen_disease()

        print("THE END OF PROMPT")
        cmd = input("Command: ").strip().lower()

        if cmd == "feed":
            pet.feed()
        elif cmd == "treat":
            pet.treat(minute)
        elif cmd == "play":
            pet.play(minute)
        elif cmd == "status":
            pet.status()
        else:
            print("Unknown command. Use: feed, treat, status")

        minute += 1
        print("--------END OF ROUND -----------")

    if not pet.is_alive():
        print(f"\n💀 {pet.name} has passed away. Game over.")

if __name__ == "__main__":
    main()
