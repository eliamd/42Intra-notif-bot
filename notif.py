import discord
import getpass
import time
import config
from datetime import datetime, timedelta
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
        # Supprimer les informations de fuseau horaire et analyser la chaîne datetime
        time_str = datetime_str.split(' CEST')[0]
        dt = datetime.strptime(time_str, '%Y-%m-%d %H:%M')
        # Ajouter les informations de fuseau horaire
        tz = pytz.timezone('Europe/Paris')  # Ajustez le fuseau horaire si nécessaire
        dt = tz.localize(dt)
        # Convertir en timestamp Unix
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
                    timestamp_format = f"<t:{timestamp}:F>"  # Format 'F' pour une date et heure complètes
                    messages.append(f"{mention}, **Nouvelle évaluation trouvée :** Vous allez évaluer quelqu'un pour le projet {project[0]} à {timestamp_format}.")
                    # Créer une tâche pour envoyer un rappel à l'heure de l'évaluation
                    bot.loop.call_later(timestamp - int(time.time()), lambda: bot.loop.create_task(channel.send(f"{mention}, **Rappel :** L'évaluation pour {project[0]} est maintenant.")))
                else:
                    messages.append(f"{mention}, **Nouvelle évaluation trouvée :** Vous allez évaluer quelqu'un pour le projet {project[0]}.")
            return messages
        else:
            return [f"Aucune nouvelle évaluation trouvée pour {login}."]
    except Exception as e:
        print(f"Une erreur s'est produite: {e}")
        return [f"Une erreur s'est produite lors de la vérification des nouvelles évaluations."]
    finally:
        driver.quit()

intents = discord.Intents.default()
intents.message_content = True

bot = commands.Bot(command_prefix='!', intents=intents)

@bot.event
async def on_ready():
    print(f'Bot connecté en tant que {bot.user.name}')
    await bot.get_channel(CHANNEL_ID).send(embed=discord.Embed(
        title="Activation du Bot",
        description=":robot: Le bot est maintenant **actif** !",
        color=discord.Color.green()
    ))
    check_eval.start()
    check_activation_status.start()

@tasks.loop(minutes=10)
async def check_eval():
    now = datetime.now(pytz.timezone('Europe/Paris')).time()
    if now >= datetime.strptime('08:00', '%H:%M').time() and now <= datetime.strptime('20:00', '%H:%M').time():
        channel = bot.get_channel(CHANNEL_ID)
        if channel:
            messages = get_eval()
            for message in messages:
                await channel.send(embed=discord.Embed(
                    title="Nouvelle Évaluation",
                    description=message,
                    color=discord.Color.blue()
                ))

@tasks.loop(hours=24)
async def check_activation_status():
    # Envoyer un message d'activation à 8h00 et un message de désactivation à 20h00
    now = datetime.now(pytz.timezone('Europe/Paris')).time()
    if now == datetime.strptime('08:00', '%H:%M').time():
        await bot.get_channel(CHANNEL_ID).send(embed=discord.Embed(
            title="Activation du Bot",
            description=":robot: Le bot est maintenant **actif** !",
            color=discord.Color.green()
        ))
    elif now == datetime.strptime('20:00', '%H:%M').time():
        await bot.get_channel(CHANNEL_ID).send(embed=discord.Embed(
            title="Désactivation du Bot",
            description=":sleeping: Le bot est maintenant **inactif**.",
            color=discord.Color.red()
        ))

@bot.command(name='start')
async def start_task(ctx):
    check_eval.start()
    await ctx.send(embed=discord.Embed(
        title="Tâche démarrée",
        description=":arrow_forward: La vérification des évaluations a été démarrée.",
        color=discord.Color.green()
    ))

@bot.command(name='stop')
async def stop_task(ctx):
    check_eval.stop()
    await ctx.send(embed=discord.Embed(
        title="Tâche arrêtée",
        description=":stop_sign: La vérification des évaluations a été arrêtée.",
        color=discord.Color.red()
    ))

bot.run(TOKEN)
