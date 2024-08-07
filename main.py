from flask import Flask, request, render_template, redirect, url_for, jsonify
import bleach

import json
import os

app = Flask(__name__)

data_file = 'games.json'

# Ensure the data file exists and initialize it if it's empty
if not os.path.exists(data_file):
    with open(data_file, 'w') as f:
        json.dump([], f)

id_file = 'game_id.txt'

def get_next_id():
    if not os.path.exists(id_file):
        with open(id_file, 'w') as f:
            f.write('10000')
        return 10000
    else:
        with open(id_file, 'r') as f:
            current_id = int(f.read().strip())
        with open(id_file, 'w') as f:
            f.write(str(current_id + 1))
        return current_id + 1

@app.route('/api/submit-your-bingo', methods=['POST'])
def submit_bingo():
    theme = request.form['theme']
    items = request.form['items'].strip().split('\n')
    author = request.form.get('author', 'Anonymous')

    # Sanitize inputs to remove potentially harmful HTML/JavaScript
    theme = bleach.clean(theme, strip=True)
    author = bleach.clean(author, strip=True)
    items = [bleach.clean(item.strip(), strip=True) for item in items]
    
    # Validate input lengths
    if len(theme) > 50 or len(author) > 50:
        return jsonify({"error": "Theme and author name must be less than 50 characters."}), 400
    
    max_item_length = 30
    if len(items) != 25 or any(len(item.strip()) > max_item_length for item in items):
        return jsonify({"error": f"Each item must be less than {max_item_length} characters and you must have exactly 25 items."}), 400

    game_id = get_next_id()
    game_data = {
        'theme': theme,
        'items': items,
        'game_id': game_id,
        'author': author
    }
    
    # Append the new game data to the JSON file
    with open(data_file, 'r', encoding='utf-8') as f:
        games = json.load(f)
    
    games.append(game_data)
    
    with open(data_file, 'w', encoding='utf-8') as f:
        json.dump(games, f, ensure_ascii=False)
    
    return jsonify({'game_id': game_id})


@app.route('/api/game/<int:game_id>')
def show_game(game_id):
    try:
        with open(data_file, 'r', encoding='utf-8') as f:
            games = json.load(f)
        
        # Find the game with the specified game_id
        game_data = next((game for game in games if game['game_id'] == game_id), None)
        
        if not game_data:
            return jsonify({"error": "Game not found"}), 404

        return jsonify(game_data)
    
    except FileNotFoundError:
        return jsonify({"error": "Game data file not found"}), 404


if __name__ == '__main__':
    app.run(debug=True, port=9001)
