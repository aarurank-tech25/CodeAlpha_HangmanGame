
import random

# Predefined words
words = ["python", "computer", "program", "science", "developer"]

# Select a random word
secret_word = random.choice(words)

# Store guessed letters
guessed_letters = []

# Maximum incorrect attempts
attempts = 6

print("================================")
print("       HANGMAN GAME")
print("================================")
print("Guess the hidden word!")
print("You have 6 incorrect attempts.")

# Game loop
while attempts > 0:

    # Display current word
    display_word = ""

    for letter in secret_word:
        if letter in guessed_letters:
            display_word = display_word + letter
        else:
            display_word = display_word + "_"

    print("\nWord:", " ".join(display_word))
    print("Remaining attempts:", attempts)

    # Check whether the player won
    if "_" not in display_word:
        print("\nCongratulations! You won!")
        break

    # Get user input
    guess = input("Enter a letter: ").lower()

    # Validate input
    if len(guess) != 1 or not guess.isalpha():
        print("Please enter a single alphabet!")
        continue

    if guess in guessed_letters:
        print("You already guessed this letter!")
        continue

    guessed_letters.append(guess)

    # Check the guessed letter
    if guess in secret_word:
        print("Correct guess!")
    else:
        print("Wrong guess!")
        attempts = attempts - 1

# Check game result
if attempts == 0:
    print("\nGame Over!")
    print("The correct word was:", secret_word)
