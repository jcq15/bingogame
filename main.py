from flask import Flask, request, render_template, redirect, url_for, jsonify
from PIL import Image, ImageDraw, ImageFont
import bleach
import qrcode

import json
import os
import random
import traceback
from uuid import uuid4

app = Flask(__name__)

data_file = 'games.json'

# Ensure the data file exists and initialize it if it's empty
if not os.path.exists(data_file):
    with open(data_file, 'w') as f:
        json.dump([], f)

id_file = 'game_id.txt'


# https://stackoverflow.com/questions/77038132/python-pillow-pil-doesnt-recognize-the-attribute-textsize-of-the-object-imag
def textsize(text, font):
    im = Image.new(mode="P", size=(0, 0))
    draw = ImageDraw.Draw(im)
    _, _, width, height = draw.textbbox((0, 0), text=text, font=font)
    return width, height

def wrap_text(text, font, max_width):
    """Wrap text to fit within a given width."""
    lines = []
    words = text
    while words:
        # print(words)
        line = ''
        while words and font.getlength(line + words[0]) <= max_width:
            line += words[0]
            words = words[1:]
        lines.append(line)
    return lines

def generate_bingo_result_image(game_data, selections, output_path):
    # Unpack game data
    title = game_data['title'] + '宾果图'
    describe = '连成一条线我就是' + game_data['describe']
    shape = game_data['shape']
    content = game_data['content']
    url = 'https://bingo.shadiao.win/play.html?game_id=' + str(game_data['game_id'])  # URL to the game

    # Create an image with white background
    img_size = 600
    img_height = int(img_size * 1.8)  # Use a golden ratio or similar aspect for aesthetic reasons
    img = Image.new('RGB', (img_size, img_height), 'white')
    draw = ImageDraw.Draw(img)

    # Set up font
    font_title = ImageFont.truetype("resources/fonts/SourceHanSerifSC-VF.ttf", 24)
    font_desc = ImageFont.truetype("resources/fonts/SourceHanSerifSC-VF.ttf", 16)
    font_content = ImageFont.truetype("resources/fonts/SourceHanSerifSC-VF.ttf", 12)

    # Calculate grid position for center alignment
    cell_size = img_size // (shape + 2)
    grid_width = cell_size * shape
    grid_left = (img_size - grid_width) // 2
    grid_top = (img_height - grid_width) // 2

    # Draw the grid and mark selected cells
    for i in range(shape):
        for j in range(shape):
            x0 = grid_left + j * cell_size
            y0 = grid_top + i * cell_size
            x1 = x0 + cell_size
            y1 = y0 + cell_size
            fill_color = "green" if (i * shape + j) in selections else "white"
            draw.rectangle([x0, y0, x1, y1], outline="black", fill=fill_color)
            item_text = content[i * shape + j]
            lines = wrap_text(item_text, font_content, cell_size - 10)  # Wrap text within cell width

            # Calculate total height of text block
            text_height = len(lines) * textsize('屎', font_content)[1]
            current_y = y0 + (cell_size - text_height) / 2  # Center text vertically

            for line in lines:
                text_width, text_height = textsize(line, font=font_content)
                draw.text((x0 + (cell_size - text_width) / 2, current_y), line, fill="black", font=font_content)
                current_y += text_height

    # Add title and description centered above the grid
    desc_width, desc_height = textsize(describe, font=font_desc)
    draw.text(((img_size - desc_width) / 2, grid_top - desc_height - 20), describe, fill="black", font=font_desc)
    title_width, title_height = textsize(title, font=font_title)
    draw.text(((img_size - title_width) / 2, grid_top - title_height - desc_height - 40), title, fill="black", font=font_title)

    # Generate QR code
    qr = qrcode.QRCode(version=1, error_correction=qrcode.constants.ERROR_CORRECT_L, box_size=10, border=2)
    qr.add_data(url)
    qr.make(fit=True)
    qr_img = qr.make_image(fill='black', back_color='white')
    qr_img = qr_img.resize((100, 100), Image.Resampling.LANCZOS)
    img.paste(qr_img, (img_size - 120, grid_top + grid_width + 20))  # Positioned below the grid

    # Save the result
    img.save(output_path)


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
    title = request.form['title']
    describe = request.form['describe']
    shape = int(request.form['shape'])  # Shape should be a number
    content = request.form['content'].strip().split('\n')
    author = request.form.get('author', 'Anonymous')

    # Sanitize inputs to remove potentially harmful HTML/JavaScript
    title = bleach.clean(title, strip=True)
    describe = bleach.clean(describe, strip=True)
    author = bleach.clean(author, strip=True)
    content = [bleach.clean(item.strip(), strip=True) for item in content]
    
    # Validate input lengths
    if len(title) > 50 or len(describe) > 100 or len(author) > 50:
        return jsonify({"error": "Title, description, and author name must be within their respective character limits."}), 400
    
    max_item_length = 30
    if len(content) != shape * shape or any(len(item.strip()) > max_item_length for item in content):
        return jsonify({"error": f"Each item must be less than {max_item_length} characters and you must have exactly {shape * shape} items."}), 400

    game_id = get_next_id()
    game_data = {
        'game_id': game_id,
        'title': title,
        'describe': describe,
        'shape': shape,
        'content': content,
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


@app.route('/api/popular-games')
def popular_games():
    # Example logic to fetch popular games
    # 从games.json里随机选10个，不足则全选
    with open(data_file, 'r', encoding='utf-8') as f:
        games = json.load(f)
    if len(games) > 10:
        popular_games = random.sample(games, 10)
    else:
        popular_games = games
    response = [{'game_id': game['game_id'], 'title': game['title']} for game in popular_games]
    return jsonify(response)


@app.route('/api/get-result', methods=['POST'])
def generate_image():
    #data = request.json
    #game_id = data['game_id']
    #selections = data['selections']
    try:
        game_id = int(request.form['game_id'])
        selections = [int(i) for i in request.form['selections'].split(',')]
        
        with open(data_file, 'r', encoding='utf-8') as f:
            games = json.load(f)
        game_data = next((game for game in games if game['game_id'] == game_id), None)
        
        if not game_data:
            return jsonify({"error": "Game not found"}), 404

        # Generate the image
        image_url = f'images/{uuid4().hex}.png'
        generate_bingo_result_image(game_data, selections, 'static/' + image_url)
        
        return jsonify({"image_url": image_url})
    except Exception as e:
        traceback.print_exc()
        return jsonify({"error": "An error occurred while generating the image"}), 500


if __name__ == '__main__':
    app.run(debug=True, port=9001)
