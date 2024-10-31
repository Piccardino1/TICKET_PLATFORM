from flask import Flask, render_template_string, request, url_for, send_from_directory, jsonify, session, redirect
from functools import wraps
import ssl
import json
import os
from urllib.parse import unquote
from datetime import datetime, timedelta, timezone

app = Flask(__name__)
app.secret_key = 'una_chiave_segreta_molto_lunga_e_complessa'# Deve essere la stessa di login.py
app.permanent_session_lifetime = timedelta(minutes=5)  

context = ssl.SSLContext(ssl.PROTOCOL_TLSv1_2)
context.load_cert_chain(certfile='./cert/cert.pem', keyfile='./cert/key.pem')

# Configura il percorso per i caricamenti
UPLOAD_FOLDER = 'uploads'
os.makedirs(UPLOAD_FOLDER, exist_ok=True)
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER

# Percorso del file JSON per le segnalazioni
TICKETS_FILE = 'tickets.json'
COUNTER_FILE = 'counter.txt'  # File per il contatore

# Elenco delle segnalazioni
tickets = []
ticket_counter = 1  # Contatore per l'ID segnalazione

def load_tickets():
    global tickets, ticket_counter
    if os.path.exists(TICKETS_FILE):
        with open(TICKETS_FILE, 'r', encoding='utf-8') as f:
            tickets = json.load(f)
            if tickets:  # Se ci sono segnalazioni, imposta il contatore all'ID massimo + 1
                ticket_counter = max(int(ticket['id_seg']) for ticket in tickets) + 1

    # Carica il contatore dal file
    if os.path.exists(COUNTER_FILE):
        with open(COUNTER_FILE, 'r', encoding='utf-8') as f:
            ticket_counter = int(f.read().strip())

def save_tickets():
    try:
        with open(TICKETS_FILE, 'w', encoding='utf-8') as f:
            json.dump(tickets, f, ensure_ascii=False, indent=4)
    except Exception as e:
        print(f"Errore nel salvataggio dei ticket: {str(e)}")

def save_counter():
    with open(COUNTER_FILE, 'w', encoding='utf-8') as f:
        f.write(str(ticket_counter))

# Leggi il codice HTML per la pagina di segnalazione
index = "./html_code.html"
with open(index, "r", encoding='utf-8') as file:
    html_code = file.read()

ticket = "./segnalazioni.html"
with open(ticket, "r", encoding='utf-8') as file:
    segnalazioni = file.read()

def login_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'logged_in' not in session:
            return redirect('https://192.168.160.180:5002/login')
        # Aggiorna il timestamp dell'ultima attività
        session['last_activity'] = datetime.now(timezone.utc)
        return f(*args, **kwargs)
    return decorated_function

def login_required_back(f):
    @wraps(f)
    def decorated_function_back(*args, **kwargs):
        if 'logged_in' not in session:
            return redirect('https://192.168.160.180:5002/login_ticket')
        # Aggiorna il timestamp dell'ultima attività
        session['last_activity'] = datetime.now(timezone.utc)
        return f(*args, **kwargs)
    return decorated_function_back

@app.before_request
def check_session_expiration():
    if 'logged_in' in session and 'last_activity' in session:
        last_activity = session['last_activity']
        now = datetime.now(timezone.utc)
        if now - last_activity > timedelta(minutes=1):
            session.clear()
            return redirect('https://192.168.160.180:5002/login')
    session['last_activity'] = datetime.now(timezone.utc)

@app.route('/segnalazioni', methods=['GET', 'POST'])
@login_required
def home():
    global ticket_counter

    if request.method == 'POST':
        # Gestione con allegato
        oggetto = request.form.get('oggetto')
        dettaglio = request.form.get('dettaglio')
        nome_operatore = request.form.get('nomeOperatore') 
        modulo = request.form.get('modulo') 
        allegato = request.files.get('allegato')
        recapito_telefonico = request.form.get('recapitoTelefonico') 
        recapito_email = request.form.get('recapitoEmail') 

        # Controlla se tutti i campi obbligatori sono compilati
        if not (oggetto and dettaglio and nome_operatore and modulo and recapito_email and recapito_telefonico):
            return "Tutti i campi sono obbligatori", 400  # Bad Request

        # Salva l'allegato se presente
        file_url = None
        if allegato and allegato.filename:
            file_path = os.path.join(app.config['UPLOAD_FOLDER'], allegato.filename)
            allegato.save(file_path)
            file_url = url_for('uploaded_file', filename=allegato.filename)

        # Aggiungi la segnalazione alla lista
        tickets.append({
            'id_seg': str(ticket_counter),  # Usa il contatore per l'ID
            'oggetto': oggetto,
            'dettaglio': dettaglio,
            'nome_operatore': nome_operatore,  # Aggiungi il nome dell'operatore
            'modulo': modulo,  # Aggiungi il modulo
            'recapito_telefonico': recapito_telefonico,
            'recapito_email' : recapito_email,
            'allegato': file_url,
            'seen': False,  # Aggiungi un campo per lo stato di visualizzazione
            'stato': 'Inserito'  # Aggiungi un campo per lo stato del ticket
        })
        save_tickets()  # Salva le segnalazioni
        ticket_counter += 1  # Incrementa il contatore
        save_counter()  # Salva il contatore

    # Passa l'ID segnalazione al template
    return render_template_string(html_code, ticket_id=ticket_counter)

# Rotta per visualizzare i file caricati
@app.route('/uploads/<filename>')
def uploaded_file(filename):
    return send_from_directory(app.config['UPLOAD_FOLDER'], filename)

# Rotta per visualizzare tutte le segnalazioni
@app.route('/tickets')
@login_required_back
def view_tickets():
    return render_template_string (segnalazioni, tickets=tickets)

@app.route('/update_ticket', methods=['POST'])
def update_ticket():
    id_seg = request.form.get('idSeg')
    seen = request.form.get('seen') == 'true'
    # Logica per aggiornare la segnalazione in base all'ID
    for ticket in tickets:
        if ticket['id_seg'] == id_seg:
            ticket['seen'] = seen  # Aggiorna il campo 'seen'
            break
    save_tickets()  # Salva le segnalazioni
    return '', 204  # No content response

@app.route('/delete_ticket', methods=['POST'])
def delete_ticket():
    id_seg = request.form.get('idSeg')
    global tickets
    print(f"Richiesta di eliminazione per ID: {id_seg}")  # Debugging

    # Trova il ticket da eliminare
    ticket_to_delete = next((ticket for ticket in tickets if ticket['id_seg'] == id_seg), None)
    
    if ticket_to_delete:
        print(f"Ticket trovato: {ticket_to_delete}")  # Debugging
        # Se esiste un allegato, eliminalo
        if ticket_to_delete.get('allegato'):
            try:
                # Estrai il nome del file dall'URL e decodifica i caratteri speciali
                filename = unquote(os.path.basename(ticket_to_delete['allegato']))
                file_path = os.path.join(app.config['UPLOAD_FOLDER'], filename)
                # Normalizza il percorso del file
                file_path = os.path.normpath(file_path)
                
                print(f"Tentativo di eliminazione file: {file_path}")  # Debug
                
                if os.path.exists(file_path):
                    os.remove(file_path)  # Elimina il file
                    print(f"File allegato eliminato: {file_path}")  # Debugging
                else:
                    print(f"File non trovato: {file_path}")
            except Exception as e:
                print(f"Errore durante l'eliminazione del file: {str(e)}")

        # Filtra i ticket per rimuovere quello selezionato
        tickets_prima = len(tickets)
        tickets = [ticket for ticket in tickets if ticket['id_seg'] != id_seg]
        tickets_dopo = len(tickets)
        
        if tickets_prima == tickets_dopo:
            print(f"ATTENZIONE: Il ticket non è stato rimosso dalla lista!")
        else:
            print(f"Ticket rimosso dalla lista. Prima: {tickets_prima}, Dopo: {tickets_dopo}")

        save_tickets()  # Salva le segnalazioni aggiornate
        print(f"Ticket eliminato: {id_seg}")  # Debugging
        return jsonify({'success': True, 'message': 'Ticket eliminato con successo'}), 200
    else:
        print(f"Nessun ticket trovato con ID: {id_seg}")  # Debugging
        return jsonify({'success': False, 'message': 'Ticket non trovato'}), 404

@app.route('/clear_data', methods=['POST'])
def clear_data():
    # Cancellare il contenuto del file JSON
    if os.path.exists(TICKETS_FILE):
        with open(TICKETS_FILE, 'w', encoding='utf-8') as f:
            f.write('[]')  # Scrive un array vuoto nel file

    # Cancellare il contenuto della cartella uploads
    if os.path.exists(UPLOAD_FOLDER):
        for filename in os.listdir(UPLOAD_FOLDER):
            file_path = os.path.join(UPLOAD_FOLDER, filename)
            try:
                if os.path.isfile(file_path):
                    os.remove(file_path)  # Rimuove il file
            except Exception as e:
                print(f"Errore durante la rimozione del file {file_path}: {e}")

    return '', 204  # No content response

@app.route('/update_ticket_state', methods=['POST'])
def update_ticket_state():
    try:
        data = request.get_json()
        id_seg = data.get('idSeg')
        nuovo_stato = data.get('stato')
        
        # Trova e aggiorna il ticket
        for ticket in tickets:
            if ticket['id_seg'] == id_seg:
                ticket['stato'] = nuovo_stato
                break
        
        # Salva le modifiche nel file JSON
        save_tickets()
        
        return jsonify({'success': True, 'message': f'Stato del ticket {id_seg} aggiornato a {nuovo_stato}'}), 200
    except Exception as e:
        print(f"Errore nell'aggiornamento dello stato: {str(e)}")
        return jsonify({'success': False, 'error': str(e)}), 500

if __name__ == '__main__':
    load_tickets()  # Carica le segnalazioni all'avvio
    app.run(debug=True, host='0.0.0.0', port=5001, ssl_context=context)