import time
import config
import random
import pytz
import logging
from datetime import datetime
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from pypushover import Client  # Mise à jour de l'import
from apscheduler.schedulers.blocking import BlockingScheduler

# Configuration du logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

# Initialisation des paramètres
USE_TIME_WINDOW = config.use_time_window
login = config.login
mdp = config.mdp
id_discord = config.id_discord
pushover_user_key = config.pushover_user_key
pushover_api_token = config.pushover_api_token
seen_ids = set()

# Initialisation du client Pushover
client = Client(user_key=pushover_user_key, api_token=pushover_api_token)

# Fonction pour envoyer une notification via Pushover
def send_notification(title, message):
    client.send_message(message, title=title)
    logging.info(f"Notification envoyée: {title} - {message}")

# Fonction pour convertir une chaîne datetime en timestamp
def parse_datetime(datetime_str):
    try:
        time_str = datetime_str.split(' CEST')[0]
        dt = datetime.strptime(time_str, '%Y-%m-%d %H:%M')
        tz = pytz.timezone('Europe/Paris')
        dt = tz.localize(dt)
        timestamp = int(dt.timestamp())
        return timestamp
    except Exception as e:
        logging.error(f"Erreur lors de la conversion de la date: {e}")
        return None

# Fonction pour récupérer les nouveaux projets/évaluations
def get_new_projects(driver):
    global seen_ids
    project_items = driver.find_elements(By.CLASS_NAME, "project-item.reminder")
    new_items = []

    for item in project_items:
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
                new_items.append([project_id, project_part, timestamp])

    return new_items

# Fonction pour lancer la vérification des évaluations
def check_evaluations():
    logging.info("Début de la vérification des évaluations.")

    now = datetime.now(pytz.timezone('Europe/Paris')).time()
    if USE_TIME_WINDOW and (now < datetime.strptime('08:30', '%H:%M').time() or now > datetime.strptime('19:30', '%H:%M').time()):
        logging.info("Hors de la plage horaire définie. Vérification annulée.")
        return

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
            for project_id, project_name, timestamp in new_projects:
                if timestamp:
                    timestamp_format = f"<t:{timestamp}:F>"
                    message = f"📝 Vous allez évaluer quelqu'un pour le projet **{project_name}** à {timestamp_format}."
                else:
                    message = f"📝 Vous allez évaluer quelqu'un pour le projet **{project_name}**."
                send_notification("Nouvelle Évaluation", message)
        else:
            logging.info("Aucune nouvelle évaluation trouvée.")
    except Exception as e:
        logging.error(f"Une erreur s'est produite: {e}")
    finally:
        driver.quit()

# Scheduler pour exécuter les vérifications à des intervalles aléatoires
scheduler = BlockingScheduler()

@scheduler.scheduled_job('interval', minutes=10)
def random_check():
    interval = random.randint(10, 16) * 60
    logging.info(f"Nouvel intervalle de vérification défini: {interval // 60} minutes.")
    scheduler.modify_job('random_check', trigger='interval', seconds=interval)
    check_evaluations()

# Envoi de la notification à l'activation du bot
send_notification("Activation du Bot", "🚀 Le bot est maintenant **actif** et surveille les nouvelles évaluations.")

# Démarrage du scheduler
scheduler.start()
