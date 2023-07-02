# Import the required libraries
from datetime import datetime
import json
import time
import requests
import importlib.util
import os
import discord
from discord.ext import commands
import asyncio
from dotenv import load_dotenv
import re
import urllib.request
import tempfile

# Grab the environment variables for the bot
load_dotenv()
OPENAI_API_KEY = os.getenv('OPENAI_API_KEY')
DISCORD_TOKEN = os.getenv('DISCORD_TOKEN')
LLM_ENDPOINT = os.getenv('LLM_ENDPOINT')
LLM_MODEL = os.getenv('LLM_MODEL')
GOOGLESEARCH_API_KEY = os.getenv('GOOGLESEARCH_API_KEY')
GOOGLESEARCH_CSE_ID = os.getenv('GOOGLESEARCH_CSE_ID')
YOUTUBE_API_KEY = os.getenv('YOUTUBE_API_KEY')
FURAFFINITY_A_COOKIE = os.getenv('FURAFFINITY_A_COOKIE')
FURAFFINITY_B_COOKIE = os.getenv('FURAFFINITY_B_COOKIE')


variables_list = f"""OPENAI_API_KEY = {OPENAI_API_KEY}
DISCORD_TOKEN = {DISCORD_TOKEN}
LLM_ENDPOINT = {LLM_ENDPOINT}
LLM MODEL = {LLM_MODEL}
GOOGLESEARCH_API_KEY = {GOOGLESEARCH_API_KEY}
GOOGLESEARCH_CSE_ID = {GOOGLESEARCH_CSE_ID}
YOUTUBE_API_KEY = {YOUTUBE_API_KEY}
FURAFFINITY_A_COOKIE = {FURAFFINITY_A_COOKIE}
FURAFFINITY_B_COOKIE = {FURAFFINITY_B_COOKIE}"""

# Define the Discord intents
intents = discord.Intents.default()
intents.messages = True
intents.message_content = True

# Define the bot
bot = commands.Bot(command_prefix='!', intents=intents)

# Print when the Discord bot has connected
@bot.event
async def on_ready():
    print(f'{bot.user} has connected to Discord!')

# Define an empty functions dictionary
functions_list = []

# Set whether functions are enabled or not
FUNCTIONS_ENABLED=True

# Define a function which grabs the list of functions found in the plugins folder
def get_functions():
    if FUNCTIONS_ENABLED == True:
        plugins_folder = "plugins"
        functions = []
        # Repeats for every plugin found
        for root, dirs, files in os.walk(plugins_folder):
            for file in files:
                if file.endswith(".json"):
                    # Remove the .json extension
                    function_name = file[:-5]
                    file_path = os.path.join(root, file)
                    with open(file_path) as f:
                        function_data = json.load(f)
                        function_data["name"] = function_name
                        functions.append(function_data)
        # Return the full list of functions
        return functions
    else:
        # If functions are disabled, return an empty dictionary
        return []

# Define a function which accepts a function and its arguments and calls it
def run_function(function_name, arguments):
    plugin_path = f"plugins/{function_name}/{function_name}.py"
    spec = importlib.util.spec_from_file_location(function_name, plugin_path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    function = getattr(module, "run")
    try:
        # Try to call the function
        function_response = function(**arguments)
        return function_response
    except Exception as e:
        #If an error occurs, return an error instead
        function_error = str(e)
        print()
        print(f"Function error: {function_error}")
        return f"{function_name} returned an error: {function_error}"

# Global messages group
messages = []  

# Define a global dictionary to store lists of messages by conversation ID
messages_dict = {}

# Define a function to add a new message to the end of a list by conversation ID
def add_msg(conversation_id, message):
  # Check if the conversation ID exists in the dictionary
  if conversation_id in messages_dict:
    # Append the message to the existing list
    messages_dict[conversation_id].append(message)
  else:
    # Create a new list with the message and assign it to the conversation ID
    messages_dict[conversation_id] = [message]

# Define a function to get the list of messages by conversation ID
def get_msg(conversation_id, info):
    with open('initial_prompt.txt', 'r') as file:
        initial_prompt = file.read() + info
    # Check if the conversation ID exists in the dictionary
    if conversation_id in messages_dict:
        # Get the list of messages
        messages = messages_dict[conversation_id]
        # Remove the existing system message, if it exists
        messages = [msg for msg in messages if msg['role'] != 'system']
        # Insert the new initial_prompt variable as the first message in the list
        messages.insert(0, {'role': 'system', 'content': initial_prompt})
        # Return the list of messages
        return messages
    else:
        # Return an empty list
        return []

def clean_list(conversation_id, message_limit):
    if conversation_id in messages_dict:
        messages = messages_dict[conversation_id]
        cleaned_messages = []
        for message in messages:
            if message['role'] == 'function':
                message['content'] = 'This function\'s response has been cleared to save on token usage'
            cleaned_messages.append(message)
        messages_dict[conversation_id] = cleaned_messages[-message_limit:]

async def ai_reply(input, message, conversation_id, info):
    # Add the input arg to the list of messages and then clean the list (removes the oldest messages)
    add_msg(conversation_id, input)
    # Define the payload which will be sent to the AI
    payload = {
      "model": LLM_MODEL,
      "functions": get_functions(),
      "messages": get_msg(conversation_id, info)
    }
    # Define the authorization header for the API key
    headers = {
        "Authorization": f"Bearer {OPENAI_API_KEY}",
        "Content-Type": "application/json"
    }

    response = requests.post(LLM_ENDPOINT, json=payload, headers=headers)
    response_dict = json.loads(response.text)
    try:
        choice = response_dict["choices"]
        if choice:
            # If "choices" exists in the AI's response, define the finish reason variable
            finish_reason = choice[0]["finish_reason"]
            if finish_reason:
                # Continue with further actions
                pass
            else:
                # Sends an error in case of an exception
                await send_message(f"It seems that {bot.user.name} has encountered an error! Check the output for details.", message)
                print(response.text)
        else:
            await send_message(f"It seems that {bot.user.name} has encountered an error! Check the output for details.", message)
            print(response.text)
    except KeyError:
        await send_message(f"It seems that {bot.user.name} has encountered an error! Check the output for details.", message)
        print(response.text)

    try:
        choice = response_dict["choices"]
        if choice:
            # Check the finish reason
            finish_reason = choice[0]["finish_reason"]
            if finish_reason == "stop":
                # Take the AI's response and send that through Discord
                ai_response = response_dict["choices"][0]["message"]["content"]
                add_msg(conversation_id, {"role": "assistant", "content": f"{ai_response}"})
                # Print token usage
                prompt_tokens = response_dict["usage"]["prompt_tokens"]
                completion_tokens = response_dict["usage"]["completion_tokens"]
                print()
                print(bot.user.name + ' replied: ' + ai_response)
                print(f"Prompt Tokens: {prompt_tokens}")
                print(f"Completion Tokens: {completion_tokens}")
                # Clear out old messages and function outputs
                clean_list(conversation_id, 8)
                await send_message(ai_response, message)
            elif finish_reason == "function_call":
                # Take the function details and call it
                func_name = response_dict["choices"][0]["message"]["function_call"]["name"]
                func_args = response_dict["choices"][0]["message"]["function_call"]["arguments"]
                print()
                print(f"""Calling function `{func_name}` with the arguments:
                      {func_args}""")
                # Send the functions response back to the AI for another response
                parsed_argument = json.loads(func_args)
                function_response = run_function(func_name,parsed_argument)
                add_msg(conversation_id, {"role": "assistant", "content": "", "function_call": {"name": f"{func_name}", "arguments": f"{func_args}"}})
                await ai_reply({"role": "function", "name": f"{func_name}", "content": f"{function_response}"}, message, conversation_id, info)
            else:
                # Handle other cases
                print("Unexpected finish reason!")
        else:
            error_msg = response_dict["error"]["message"]
            await send_message(f"***{bot.user.name} has encountered an error!***", message)
            print(error_msg)
    except KeyError:
        error_msg = response_dict["error"]["message"]
        await send_message(f"***{bot.user.name} has encountered an error!***", message)
        print(error_msg)

async def send_message(message, message_obj):
    # Define the size of the message's individual chunks
    size = 48
    img_url = extract_image_url(message)
    if img_url:
        message_stripped = message.replace(img_url, "[IMAGE]")
    # Check if the message contains a valid image URL
    if has_valid_image_url(message):
        url = img_url
        response = requests.get(url)

        open('tempimage.png', 'wb').write(response.content)
        # Send the message with the attached image:
        imgfile = discord.File("tempimage.png")
        msg = await message_obj.channel.send(message_stripped[:size], file=imgfile)
        os.remove('tempimage.png')
        i = size
        while i < len(message) + size:
            await msg.edit(content=message_stripped[:i])
            i += size
            await asyncio.sleep(0.2)
    else:
        # Send the message as normal
        msg = await message_obj.channel.send(message[:size])
        i = size
        while i < len(message) + size:
            await msg.edit(content=message[:i])
            i += size
            await asyncio.sleep(0.2)

def extract_image_url(message):
    # Use regular expressions to extract the image URL
    pattern = r"(http[s]?:\/\/.*\.(?:png|jpg|jpeg|gif|bmp))"
    matches = re.findall(pattern, message)
    if matches:
        return matches[0]
    else:
        return None
    
def has_valid_image_url(message):
    # Use regular expressions to check for a valid image URL
    pattern = r"(http[s]?:\/\/.*\.(?:png|jpg|jpeg|gif|bmp))"
    matches = re.findall(pattern, message)
    return len(matches) > 0

# Define  a function which creates a "Bot is typing..." indicator in the Discord channel
async def TriggerTyping(secs, message):
    async with message.channel.typing():
        await asyncio.sleep(secs)

@bot.event
async def on_message(message):
    if message.author == bot.user:
        # If the message came from the bot, ignore it
        return
    if f'<@{bot.user.id}>' in message.content:
        # If the message received contains a ping to the bot (@Bot), strip the ping from the message before continuing
        content = message.content.replace(f'<@{bot.user.id}>', '').lstrip()
        # Set a nickname
        nickname = run_function("user_nickname", {'action': 'get_nickname', 'user_id': f'{message.author.id}', 'server_id': f'{message.guild.id}'})
        if nickname != f"No nickname found for user {message.author.id} in server {message.guild.id}":
            # If a nickname is found, append it to the message
            content = f"[ID: {message.author.id}, Name: {nickname}]: {content}"
        else:
            # If a nickname is not found, leave the message as is
            content = f"[ID: {message.author.id}, Name: No name is found, ask for the users name by pinging them like \"<@{message.author.id}>\" and set it as their nickname]: {content}"
        # Trigger the typing indicator
        await TriggerTyping(1, message)
        # Get the channel ID of the message which will become the Conversation ID
        channel = message.channel.id
        conversation_id = message.channel.id
        # Print the users message
        print()
        print(f'{content}')
        # Grab all the custom emojis from the current server
        emojis = message.guild.emojis
        emoji_list = []
        for emoji in emojis:
            # Append each emoji found to a list
            emoji_list.append(f"<:{emoji.name}:{emoji.id}>")
        # Define some extra info which will be sent to the AI for additional context
        info = f"""

You have access to the following server emojis:
{emoji_list}

Current message context:
Message ID: "{message.id}"
Message Author: "{message.author.name}"
Message Author's Traits: {run_function("user_traits", {"action": "get_traits", "user_id": message.author.name})}
Message Author User ID: "{message.author.id}"
Message origins: From channel "{message.channel.name}" in server "{message.guild.name}"
Channel ID: "{message.channel.id}"
Server ID: "{message.guild.id}"
"""
        # Send the users message to the AI, alongside the conversation ID and info
        await ai_reply(({"role": "user", "content": content}), message, conversation_id, info)

# Run the Discord Bot
bot.run(DISCORD_TOKEN)
