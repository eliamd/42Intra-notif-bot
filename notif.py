# **************************************************************************** #
#                                                                              #
#                                                         :::      ::::::::    #
#    notif.py                                           :+:      :+:    :+:    #
#                                                     +:+ +:+         +:+      #
#    By: ele-lean <ele-lean@student.42.fr>          +#+  +:+       +#+         #
#                                                 +#+#+#+#+#+   +#+            #
#    Created: 2024/08/22 15:04:44 by ele-lean          #+#    #+#              #
#    Updated: 2024/08/22 16:38:36 by ele-lean         ###   ########.fr        #
#                                                                              #
# **************************************************************************** #

import discord
import getpass
import time
import config
from datetime import datetime
import pytz
from discord.ext import commands, tasks
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC

TOKEN = config.api_key
CHANNEL_ID = 1276164721547939855
login = input("Login: ")
mdp = getpass.getpass('Mdp: ')
id_discord = input("Id discord: ")
seen_ids = set()

def parse_datetime(datetime_str):
    try:
        # Remove the timezone info and parse the datetime string
        time_str = datetime_str.split(' CEST')[0]
        dt = datetime.strptime(time_str, '%Y-%m-%d %H:%M')
        # Add timezone information
        tz = pytz.timezone('Europe/Paris')  # Adjust timezone if needed
        dt = tz.localize(dt)
        # Convert to Unix timestamp
        timestamp = int(dt.timestamp())
        return timestamp
    except Exception as e:
        print(f"Erreur lors de la conversion de la date: {e}")
        return None

def get_new_projects(driver):
    global seen_ids
    project_items = driver.find_elements(By.CLASS_NAME, "project-item.reminder")

    new_items = []

    for item in project_items:
        data_scale_team = item.get_attribute("data-scale-team")
        project_id = item.get_attribute("id")
        project_text = item.find_element(By.CLASS_NAME, "project-item-text").text
        if project_id not in seen_ids:
            seen_ids.add(project_id)
            start_index = project_text.find("on C")
            if start_index != -1:

                end_index = project_text.find("\n", start_index)
                if end_index == -1:
                    end_index = len(project_text)
                
                project_part = project_text[start_index:end_index].strip()
                
                time_element = item.find_element(By.CSS_SELECTOR, "span[data-original-title]")
                data_original_title = time_element.get_attribute("data-original-title")
                
                timestamp = parse_datetime(data_original_title)
                new_items.append([project_part, timestamp])

    return new_items

def get_eval():
    driver = webdriver.Chrome()
    try:
        driver.get("https://auth.42.fr/auth/realms/students-42/protocol/openid-connect/auth?client_id=intra")

        username = driver.find_element(By.ID, "username")
        password = driver.find_element(By.ID, "password")

        username.send_keys(login)
        password.send_keys(mdp)
        
        submit_button = driver.find_element(By.ID, "kc-login")
        submit_button.click()
        WebDriverWait(driver, 10).until(
            EC.url_contains("https://profile.intra.42.fr")
        )

        new_projects = get_new_projects(driver)

        if new_projects:
            messages = []
            for project in new_projects:
                mention = f"<@{id_discord}>"
                timestamp = project[1]
                if timestamp:
                    timestamp_format = f"<t:{timestamp}:F>"  # 'F' format for a full date and time
                    messages.append(f"{mention} New evaluation found: You will evaluate someone on {project[0]} at {timestamp_format}")
                else:
                    messages.append(f"{mention} New evaluation found: You will evaluate someone on {project[0]}")
            return "\n".join(messages)
        else:
            return "No new evaluations found for " + login
    except Exception as e:
        print(f"An error occurred: {e}")
        return "An error occurred while checking for new evaluations."
    finally:
        driver.quit()

intents = discord.Intents.default()
intents.message_content = True

bot = commands.Bot(command_prefix='!', intents=intents)

@bot.event
async def on_ready():
    print(f'Bot connecté en tant que {bot.user.name}')
    send_message.start()

@tasks.loop(minutes=5)
async def send_message():
    channel = bot.get_channel(CHANNEL_ID)
    if channel:
        message = get_eval()
        if message:
            await channel.send(message)

@bot.command(name='start')
async def start_task(ctx):
    send_message.start()

@bot.command(name='stop')
async def stop_task(ctx):
    send_message.stop()

bot.run(TOKEN)
