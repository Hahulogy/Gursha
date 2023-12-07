import telebot
from telebot import types
import random
import sqlite3
from sqlite3 import Error
import threading
import uuid
import datetime
import time

bot = telebot.TeleBot("6320669658:AAEwUvkCY6EJauFd17MSGUzxyOhG-wGets4")

tls = threading.local()
def get_connection():
    # Retrieve the thread-local connection or create a new one
    if not hasattr(tls, "connection"):
        tls.connection = create_connection()
    return tls.connection


def create_connection():
    # Create a new database connection
    conn = None
    try:
        conn = sqlite3.connect('user_data.db')
        return conn
    except Error as e:
        print(e)
    return conn


def get_cursor():
    # Retrieve the thread-local cursor or create a new one
    if not hasattr(tls, "cursor"):
        tls.cursor = get_connection().cursor()
    return tls.cursor


def create_table():
    # Drop the tables if they exist
    cursor = get_cursor()
    cursor.execute('DROP TABLE IF EXISTS users')
    cursor.execute('DROP TABLE IF EXISTS invitations')

    # Create the users table with the updated schema
    cursor.execute('''CREATE TABLE users
                      (user_id INTEGER PRIMARY KEY, balance REAL, referral_code TEXT, last_played_time TEXT)''')

    # Create the invitations table with the schema
    cursor.execute('''CREATE TABLE invitations
                      (inviter_id INTEGER, invitee_id INTEGER, deposit_amount REAL, 
                      PRIMARY KEY (inviter_id, invitee_id),
                      FOREIGN KEY (inviter_id) REFERENCES users(user_id),
                      FOREIGN KEY (invitee_id) REFERENCES users(user_id))''')

    get_connection().commit()


def generate_referral_link(user_id):
    # Retrieve the referral code for the user
    cursor = get_cursor()
    cursor.execute('SELECT referral_code FROM users WHERE user_id = ?', (user_id,))
    result = cursor.fetchone()

    if result is not None:
        referral_code = result[0]
    else:
        # Generate a new referral code using UUID
        referral_code = str(uuid.uuid4())

        # Store the referral code in the database
        cursor.execute('UPDATE users SET referral_code = ? WHERE user_id = ?', (referral_code, user_id))
        get_connection().commit()

    # Create the referral link based on the user ID and referral code
    if referral_code is not None:
        referral_link = f"https://t.me/cachilupibot?ref={user_id}-{referral_code}"
    else:
        referral_link = f"https://t.me/cachilupibot?ref={user_id}"

    return referral_link


def update_invitation_stats(inviter_id, invitee_id, deposit_amount):
    cursor = get_cursor()
    cursor.execute('INSERT OR IGNORE INTO invitations (inviter_id, invitee_id, deposit_amount) VALUES (?, ?, ?)',
                   (inviter_id, invitee_id, deposit_amount))
    cursor.execute('UPDATE users SET balance = balance + ? WHERE user_id = ?', inviter_id)
    get_connection().commit()

def get_invitation_stats(user_id):
    cursor = get_cursor()

    # Get the total number of invitations
    cursor.execute('SELECT COUNT(*) FROM invitations WHERE inviter_id = ?', (user_id,))
    total_invitations = cursor.fetchone()[0]

    # Get the total earnings
    cursor.execute('SELECT SUM(deposit_amount) FROM invitations WHERE inviter_id = ?', (user_id,))
    total_earnings = cursor.fetchone()[0]

    if total_earnings is None:
        total_earnings = 0

    return {
        'total_invitations': total_invitations,
        'total_earnings': total_earnings
    }

# Call the create_table function to create the table if it doesn't exist

def update_last_played_time(user_id):
    conn = create_connection()
    if conn is not None:
        try:
            current_time = datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')
            cursor = conn.cursor()
            cursor.execute('''
                UPDATE users
                SET last_played_time = ?
                WHERE user_id = ?
            ''', (current_time, user_id))
            conn.commit()
            print(f'Last played time updated: User ID - {user_id}, Time - {current_time}')
        except Error as e:
            print(f'Error updating last played time: {e}')
        finally:
            conn.close()


def get_last_played_time(user_id):
    conn = create_connection()
    if conn is not None:
        try:
            cursor = conn.cursor()
            cursor.execute('''
                SELECT last_played_time
                FROM users
                WHERE user_id = ?
            ''', (user_id,))
            row = cursor.fetchone()
            if row:
                last_played_time = row[0]
                print(f'Last played time retrieved: User ID - {user_id}, Time - {last_played_time}')
                return last_played_time
            else:
                print(f'No last played time found for User ID - {user_id}')
        except Error as e:
            print(f'Error retrieving last played time: {e}')
        finally:
            conn.close()

    return None


# Check if user is on cooldown
def check_lucky_cooldown(user_id):
    last_played_time = get_last_played_time(user_id)
    if last_played_time:
        current_time = datetime.datetime.now()
        cooldown_period = datetime.timedelta(hours=48)
        time_difference = current_time - datetime.datetime.strptime(last_played_time, '%Y-%m-%d %H:%M:%S')
        if time_difference < cooldown_period:
            return True

    return False


# Calculate remaining cooldown time
def get_remaining_time(user_id):
    last_played_time = get_last_played_time(user_id)
    if last_played_time:
        current_time = datetime.datetime.now()
        cooldown_period = datetime.timedelta(hours=48)
        time_difference = current_time - datetime.datetime.strptime(last_played_time, '%Y-%m-%d %H:%M:%S')
        remaining_time = cooldown_period - time_difference

        # Calculate the remaining hours and minutes
        remaining_hours = int(remaining_time.total_seconds() // 3600)
        remaining_minutes = int((remaining_time.total_seconds() % 3600) // 60)

        return remaining_hours, remaining_minutes

    return None, None


def get_balance(user_id):
    # Retrieve the balance for a specific user
    cursor = get_cursor()
    cursor.execute('SELECT balance FROM users WHERE user_id = ?', (user_id,))
    result = cursor.fetchone()
    balance = result[0] if result else 0
    return balance


def update_balance(user_id, new_balance):
    cursor = get_cursor()
    cursor.execute('SELECT balance FROM users WHERE user_id = ?', (user_id,))
    result = cursor.fetchone()

    if result is None:
        cursor.execute('INSERT INTO users (user_id, balance) VALUES (?, ?)', (user_id, new_balance))
        get_connection().commit()
        print("New user inserted and balance updated successfully")
    else:
        existing_balance = result[0]
        if existing_balance != new_balance:
            cursor.execute('UPDATE users SET balance = ? WHERE user_id = ?', (new_balance, user_id))
            get_connection().commit()
            updated_rows = cursor.rowcount
            if updated_rows > 0:
                return True  # Return True if the balance was updated
            else:
                print("Failed to update balance")
        else:
            print("No change in balance")

    return False  # Return False if the balance was not updated
create_table()

def close_connection():
    # Close the database connection
    conn = get_connection()

    if conn:
        conn.close()

@bot.message_handler(commands=['start'])
def start(message):
    if message.chat.id not in user_details:
        # Initialize the user's details dictionary
        user_details[message.chat.id] = {}

        # Set the initial values for the user's details
        user_details[message.chat.id]["current_balance"] = 0

    user_id = message.from_user.id
    balance = get_balance(user_id)
    if balance == 0:
        # New user, assign initial balance of 10
        update_balance(user_id, 10)
        bot.send_message(user_id, "👋 Welcome! Enjoy Your First 10 ጉርሻ😋 \nClick 💳 Balance to Check")
    show_menu(user_id)


def show_menu(user_id):
    balance = get_balance(user_id)
    keyboard = types.InlineKeyboardMarkup()
    button1 = types.InlineKeyboardButton(text="🕹 Play Game", callback_data="play_game")
    button2 = types.InlineKeyboardButton(text="💰 Deposit", callback_data="deposit")
    button3 = types.InlineKeyboardButton(text="💵 Withdraw", callback_data="withdraw")
#    button4 = types.InlineKeyboardButton(text="🍷 Invite", callback_data="invite")
    button5 = types.InlineKeyboardButton(text="💳 Balance", callback_data="my_balance")
    button6 = types.InlineKeyboardButton(text="🍀 Lucky", callback_data="my_luck")

    keyboard.row(button1)
    keyboard.row(button2, button3)
    keyboard.row(button5, button6)
#   keyboard.row(button6)

    bot.send_photo(user_id, open('C:\\Users\\HahuLogy\\Desktop\\pic.jpg', 'rb'), reply_markup=keyboard)

@bot.message_handler(commands=['update'])
def update_balance_command(message):
    # Check if the message sender is authorized to use this command
    authorized_user_ids = [626003565, 73883978, 346407386, 939071496]  # Replace with your authorized user ID(s)

    if message.from_user.id not in authorized_user_ids:
        bot.reply_to(message, "You are not authorized to use this command.")
        return

    # Extract user ID and new balance from the message
    command_parts = message.text.split()
    if len(command_parts) != 3:
        bot.reply_to(message, "Invalid command format. Please use /update user_id balance.")
        return

    user_id = int(command_parts[1])
    new_balance = float(command_parts[2])

    try:
        if update_balance(user_id, new_balance):
            bot.send_message(user_id, "Your request has been seen and your balance is updated.")
            bot.reply_to(message, f"Balance updated successfully for user {user_id}.")
        else:
            bot.reply_to(message, "No change in balance.")
    except Exception as e:
        bot.reply_to(message, f"An error occurred: {str(e)}")

@bot.callback_query_handler(func=lambda call: call.data == "my_luck")
def lucky_button_handler(call):
    user_id = call.from_user.id

    # Check if the user is on cooldown for the lucky event
    if check_lucky_cooldown(user_id):
        message = bot.send_message(user_id, "Sorry, you need to wait 48 hours before the next lucky draw.")
        time.sleep(3)  # Wait for 3 seconds
        bot.delete_message(chat_id=user_id, message_id=message.message_id)
        return

    # Generate a list of random numbers from 1 to 9
    numbers = random.sample(range(1, 10), 9)

    # Create a 3x3 inline markup keyboard with gift emojis
    keyboard = types.InlineKeyboardMarkup(row_width=3)
    for i in range(0, 9, 3):
        keyboard.add(
            types.InlineKeyboardButton("🎁", callback_data=f"lucky_number_{numbers[i]}"),
            types.InlineKeyboardButton("🎁", callback_data=f"lucky_number_{numbers[i+1]}"),
            types.InlineKeyboardButton("🎁", callback_data=f"lucky_number_{numbers[i+2]}")
        )

    # Send the lucky event message as a dialogue box with the inline keyboard
    bot.send_message(user_id, "Try your luck! 🍀", reply_markup=keyboard, parse_mode="HTML")


@bot.callback_query_handler(func=lambda call: call.data.startswith("lucky_number_"))
def lucky_number_handler(callback_query):
    user_id = callback_query.from_user.id

    # Check if user is on cooldown
    if check_lucky_cooldown(user_id):
        remaining_time = get_remaining_time(user_id)
        bot.answer_callback_query(callback_query.id, f"You have already drawn your luck. Please wait for {remaining_time} before playing again.", show_alert=True, cache_time=5)
    else:
        lucky_number = int(callback_query.data.split("_")[2])

        # Display the lucky number in a dialogue box
        bot.answer_callback_query(callback_query.id, f"You have Got {lucky_number} ጉርሻ😋! Please check your balance", show_alert=True)

        # Get the user's old balance
        old_balance = get_balance(user_id)

        # Calculate the new balance
        new_balance = old_balance + lucky_number

        # Update the balance in the database
        update_balance(user_id, new_balance)

        # Update the last played time for the user
        update_last_played_time(user_id)
        
@bot.callback_query_handler(func=lambda call: call.data == "play_game")
def play_game_handler(call):
    user_id = call.from_user.id
    balance = get_balance(user_id)
    if balance >= 1:
        # Generate a random number between 1 and 5
        correct_number = random.randint(1, 5)

        # Create the inline keyboard with number options and cancel button
        keyboard = types.InlineKeyboardMarkup()
        for number in range(1, 6):
            button = types.InlineKeyboardButton(text=str(number), callback_data=str(number))
            keyboard.add(button)
        cancel_button = types.InlineKeyboardButton(text="Cancel", callback_data="cancel")
        keyboard.add(cancel_button)

        # Send the message to select a number
        bot.send_message(user_id, "Guess a number between 1 and 5:", reply_markup=keyboard)
    else:
        bot.send_message(user_id, "⚠️ You don't have sufficient ጉርሻ to play the game.\nYou need at least 1 ጉርሻ to play.")

@bot.callback_query_handler(func=lambda call: call.data in ["1", "2", "3", "4", "5"])
def number_selection_handler(call):
    user_id = call.from_user.id
    selected_number = int(call.data)

    # Generate a random number between 1 and 5
    correct_number = random.randint(1, 5)

    if selected_number == correct_number:
        # Increase user balance by 2
        new_balance = get_balance(user_id) + 2
        update_balance(user_id, new_balance)
        bot.send_message(user_id, "✨You've got 2 ጉርሻ😋.")
    else:
        # Decrease user balance by 1
        new_balance = max(get_balance(user_id) - 1, 0)
        update_balance(user_id, new_balance)
        bot.send_message(user_id, f"Oops! The correct number was {correct_number}. You have lost 1 ጉርሻ😔")

    # Check user balance
    balance = get_balance(user_id)
    if balance >= 1:
        # Generate a random number between 1 and 5 for the next round
        correct_number = random.randint(1, 5)

        # Create the inline keyboard with number options and cancel button
        keyboard = types.InlineKeyboardMarkup()
        for number in range(1, 6):
            button = types.InlineKeyboardButton(text=str(number), callback_data=str(number))
            keyboard.add(button)
        cancel_button = types.InlineKeyboardButton(text="Cancel Game", callback_data="cancel")
        keyboard.add(cancel_button)

        # Send the message to select a number for the next round
        bot.send_message(user_id, "Guess a number between 1 and 5:", reply_markup=keyboard)
    else:
        # Show the balance and go back to the main menu
        show_menu(user_id)

@bot.callback_query_handler(func=lambda call: call.data == "cancel")
def cancel_handler(call):
    user_id = call.from_user.id
    bot.send_message(user_id, "You canceled the game.")
    show_menu(user_id)

user_details = {}

@bot.message_handler(commands=['deposit'])
def deposit(message):
    markup = types.InlineKeyboardMarkup()
    deposit_button = types.InlineKeyboardButton("Deposit", callback_data="deposit")
    markup.add(deposit_button)
    bot.send_message(message.chat.id, "Welcome! Please select an option:", reply_markup=markup)

@bot.callback_query_handler(func=lambda call: call.data == "deposit")
def deposit_callback(call):
    bot.send_message(call.message.chat.id, "How much Gursha do you want to deposit? (Minimum amount: 10ETB, 1ETB = 1 Gursha)")

@bot.message_handler(func=lambda message: message.text.isdigit())
def amount_handler(message):
    amount = int(message.text)
    if amount < 10:
        bot.send_message(message.chat.id, "Minimum deposit amount is 10 Gursha. Please enter a valid amount.")
    else:
        user_details[message.chat.id] = {"amount": amount}
        markup = types.InlineKeyboardMarkup()
        telebirr_button = types.InlineKeyboardButton("TeleBirr", callback_data="telebirr")
        cbe_button = types.InlineKeyboardButton("CBE", callback_data="cbe")
        dashen_button = types.InlineKeyboardButton("Dashen Bank", callback_data="dashen")
        boa_button = types.InlineKeyboardButton("BOA", callback_data="boa")
        markup.add(telebirr_button, cbe_button, dashen_button, boa_button)
        bot.send_message(message.chat.id, "Please select a payment method:", reply_markup=markup)

@bot.callback_query_handler(func=lambda call: call.data in ["telebirr", "cbe", "dashen", "boa"])
def payment_method_callback(call):
    payment_method = call.data
    user_details[call.message.chat.id]["payment_method"] = payment_method

    # Get the user's current balance (assuming it's stored somewhere)
    current_balance = get_balance(call.message.chat.id)
    user_details[call.message.chat.id]["current_balance"] = current_balance

    deposit_amount = user_details[call.message.chat.id]["amount"]
    if payment_method == "telebirr":
        deposit_instructions = "Please send the deposit amount to 0924337490 via TeleBirr."
    elif payment_method == "cbe":
        deposit_instructions = "Please send the deposit amount to 12456 via CBE."
    elif payment_method == "dashen":
        deposit_instructions = "Please send the deposit amount to 0514322 via Dashen Bank."
    elif payment_method == "boa":
        deposit_instructions = "Please send the deposit amount to 011543 via BOA."
    else:
        deposit_instructions = ""

    bot.send_message(call.message.chat.id, f"You selected {payment_method} and want to deposit {deposit_amount} ETB.")
    bot.send_message(call.message.chat.id, deposit_instructions)
    bot.send_message(call.message.chat.id, "Please send a proof of payment after you pay (image).")

@bot.message_handler(content_types=['photo'])
def proof_of_payment_handler(message):
    # Save the image or process it as per your requirements
    user_details[message.chat.id]["proof_of_payment"] = message.photo[-1].file_id

    # Send the user's details to your chat ID
    chat_id = "626003565, 1365237189"
    amount = user_details[message.chat.id]["amount"]
    payment_method = user_details[message.chat.id]["payment_method"]
    current_balance = user_details[message.chat.id]["current_balance"]
    proof_of_payment_file_id = user_details[message.chat.id]["proof_of_payment"]

    bot.send_message(chat_id, f"User ID: {message.chat.id}\nAmount: {amount}ETB.\nPayment Method: {payment_method}.\nCurrent Balance: {current_balance} Gursha.\nProof of Payment:")
    bot.send_photo(chat_id, proof_of_payment_file_id)

    bot.send_message(message.chat.id, "Thank you for your deposit! Your payment is being processed.")

@bot.callback_query_handler(func=lambda call: call.data == "withdraw")
def withdraw_handler(call):
    user_id = call.from_user.id

    balance = get_balance(user_id)

    if balance < 15:
        bot.send_message(user_id, "⚠️ Your balance is below 15 ጉርሻ. You cannot make a withdrawal.")
        show_menu(user_id)
    else:
        # Ask the user to select a payment method
        reply_markup = types.InlineKeyboardMarkup(row_width=2)
        telebirr_button = types.InlineKeyboardButton("TeleBirr", callback_data="tele")
        cbe_button = types.InlineKeyboardButton("CBE", callback_data="cbee")
        dashen_button = types.InlineKeyboardButton("Dashen Bank", callback_data="dashenn")
        abyssinia_button = types.InlineKeyboardButton("Abyssinia Bank", callback_data="abyssiniaa")
        reply_markup.add(telebirr_button, cbe_button, dashen_button, abyssinia_button)

        bot.send_message(user_id, "Please select your payment method:", reply_markup=reply_markup)

@bot.callback_query_handler(func=lambda call: call.data in ["tele", "cbee", "dashenn", "abyssiniaa"])
def payment_method_handler(call):
    user_id = call.from_user.id
    payment_method = call.data

    # Ask the user for their phone number
    bot.send_message(user_id, "Please enter your phone number/account number and Full Name:")

    # Register the next step handler
    bot.register_next_step_handler(call.message, process_phone_number, payment_method)

def process_phone_number(message, payment_method):
    user_id = message.from_user.id
    phone_number = message.text

    # Ask the user for their withdrawal details
    bot.send_message(user_id, "Please enter How much Gursha/ETB you want to withdraw:")

    # Register the next step handler
    bot.register_next_step_handler(message, process_withdrawal_details, payment_method, phone_number)

def process_withdrawal_details(message, payment_method, phone_number):
    user_id = message.from_user.id
    withdrawal_details = message.text

    # Extract the withdrawal amount
    try:
        withdrawal_amount = float(withdrawal_details)
    except ValueError:
        bot.send_message(user_id, "⚠️ Invalid withdrawal amount. Please enter a valid number.")
        show_menu(user_id)
        return

    balance = get_balance(user_id)

    if balance < 15:
        bot.send_message(user_id, "⚠️ Your balance is below 15 ጉርሻ. You cannot make a withdrawal.")
    elif withdrawal_amount > balance:
        bot.send_message(user_id, "⚠️ The withdrawal amount cannot exceed your balance.")
    else:
        # Perform the withdrawal
        new_balance = balance - withdrawal_amount
        update_balance(user_id, new_balance)

        # Send the withdrawal message
        withdrawal_message = f"Withdrawal request:\nUser ID: {user_id}\nBalance: {new_balance} ጉርሻ\nPayment Method: {payment_method}\nWithdrawal Details: {withdrawal_details}\nPhone Number: {phone_number}"
        bot.send_message(626003565, withdrawal_message)  # Replace YOUR_CHAT_ID with your desired destination chat ID

        bot.send_message(user_id, f"Your withdrawal request has been processed. Your new balance is {new_balance} ጉርሻ.")

    # Show the menu
    show_menu(user_id)
@bot.callback_query_handler(func=lambda call: call.data == "my_balance")
def balance_handler(call):
    user_id = call.from_user.id
    balance = get_balance(user_id)
    formatted_balance = "{:,.0f}".format(balance)  # Format the balance with no decimal places
    bot.answer_callback_query(callback_query_id=call.id, text=f"You have {formatted_balance} ጉርሻ😋.", show_alert=True)

@bot.message_handler(content_types=['text'])
def handle_text(message):
    user_id = message.from_user.id
    show_menu(user_id)

# Stop the bot and close the database connection
@bot.callback_query_handler(func=lambda call: call.data == "stop")
def stop_handler(call):
    user_id = call.from_user.id
    bot.send_message(user_id, "Bot stopped.")
    close_connection()
    bot.stop_polling()

bot.polling()
