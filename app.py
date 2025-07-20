import os
import json
import uuid
from flask import Flask, request, render_template, redirect, url_for, flash
import boto3
from botocore.exceptions import BotoCoreError, ClientError

# === Configuration ===
S3_BUCKET = 'pet-adoption-uploads'
S3_REGION = 'us-east-2'
S3_FOLDER = 'img/'
LOCAL_DATA_FILE = 'pets.json'
ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'gif'}

# Initialize app
app = Flask(__name__)
app.secret_key = os.environ.get('FLASK_SECRET_KEY', os.urandom(24))

# Initialize S3 client using IAM role credentials
s3 = boto3.client('s3', region_name=S3_REGION)

# Ensure data file exists
if not os.path.exists(LOCAL_DATA_FILE):
    with open(LOCAL_DATA_FILE, 'w') as f:
        json.dump([], f)

def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

def load_pets():
    try:
        with open(LOCAL_DATA_FILE, 'r') as f:
            return json.load(f)
    except Exception:
        return []

def save_pets(pets):
    with open(LOCAL_DATA_FILE, 'w') as f:
        json.dump(pets, f, indent=2)

@app.route('/', methods=['GET', 'POST'])
def index():
    errors = []
    if request.method == 'POST':
        name = request.form.get('name', '').strip()
        breed = request.form.get('breed', '').strip()
        age = request.form.get('age', '').strip()
        photo = request.files.get('photo')

        if not name or not breed or not age:
            errors.append("All fields (name, breed, age) are required.")
        if not photo or photo.filename == '':
            errors.append("A photo file is required.")
        elif not allowed_file(photo.filename):
            errors.append("Unsupported file type. Allowed: .jpg, .jpeg, .png, .gif")

        if errors:
            pets = load_pets()
            available_pets = [{'pet': p, 'idx': i} for i, p in enumerate(pets) if not p.get('adopted', False)]
            adopted_pets = [{'pet': p, 'idx': i} for i, p in enumerate(pets) if p.get('adopted', False)]
            return render_template("index.html", pets=available_pets, adopted_pets=adopted_pets, errors=errors)

        ext = photo.filename.rsplit('.', 1)[1].lower()
        unique_filename = f"{uuid.uuid4()}.{ext}"
        s3_key = f"{S3_FOLDER}{unique_filename}"
        try:
            photo.stream.seek(0)
            s3.upload_fileobj(
                photo,
                S3_BUCKET,
                s3_key,
                ExtraArgs={'ContentType': photo.content_type}
            )
            image_url = f"https://{S3_BUCKET}.s3.{S3_REGION}.amazonaws.com/{s3_key}"
        except (BotoCoreError, ClientError) as e:
            errors.append(f"Failed to upload image to S3: {str(e)}")
            pets = load_pets()
            available_pets = [{'pet': p, 'idx': i} for i, p in enumerate(pets) if not p.get('adopted', False)]
            adopted_pets = [{'pet': p, 'idx': i} for i, p in enumerate(pets) if p.get('adopted', False)]
            return render_template("index.html", pets=available_pets, adopted_pets=adopted_pets, errors=errors)

        new_pet = {
            'name': name,
            'breed': breed,
            'age': age,
            'image_url': image_url,
            'adopted': False
        }

        pets = load_pets()
        pets.append(new_pet)
        save_pets(pets)
        flash("Pet added successfully!", "success")
        return redirect(url_for('index'))

    pets = load_pets()
    available_pets = [{'pet': p, 'idx': i} for i, p in enumerate(pets) if not p.get('adopted', False)]
    adopted_pets = [{'pet': p, 'idx': i} for i, p in enumerate(pets) if p.get('adopted', False)]
    return render_template("index.html", pets=available_pets, adopted_pets=adopted_pets)

@app.route('/adopt', methods=['POST'])
def mark_as_adopted():
    idx = int(request.form.get('pet_index'))
    pets = load_pets()
    if 0 <= idx < len(pets):
        pets[idx]['adopted'] = True
        save_pets(pets)
        flash('Pet marked as adopted.', 'success')
    return redirect(url_for('index'))

@app.route('/delete', methods=['POST'])
def delete_pet():
    idx = int(request.form.get('pet_index'))
    pets = load_pets()
    if 0 <= idx < len(pets):
        pets.pop(idx)
        save_pets(pets)
        flash('Pet deleted.', 'success')
    return redirect(url_for('index'))

@app.route('/edit', methods=['POST'])
def edit_pet():
    idx = int(request.form.get('pet_index'))
    name = request.form.get('edit_name', '').strip()
    breed = request.form.get('edit_breed', '').strip()
    age = request.form.get('edit_age', '').strip()

    pets = load_pets()
    if 0 <= idx < len(pets):
        pets[idx]['name'] = name
        pets[idx]['breed'] = breed
        pets[idx]['age'] = age
        save_pets(pets)
        flash('Pet details updated.', 'success')
    return redirect(url_for('index'))

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000)
