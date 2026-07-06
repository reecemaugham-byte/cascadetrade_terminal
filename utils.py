import streamlit as st
import openai
from openai import OpenAI
import asyncio
import requests
import os
import random
import re
import json
import sqlite3
from datetime import datetime
from pathlib import Path
import pandas as pd
import numpy as np
import io
import base64
import time

try:
    import edge_tts
    EDGE_TTS_AVAILABLE = True
except ImportError:
    EDGE_TTS_AVAILABLE = False

try:
    from PIL import Image
    if not hasattr(Image, 'ANTIALIAS'):
        Image.ANTIALIAS = Image.LANCZOS
except ImportError:
    Image = None

try:
    import yfinance as yf
except ImportError:
    yf = None

try:
    import alpaca_trade_api as tradeapi
except ImportError:
    tradeapi = None

try:
    from duckduckgo_search import DDGS
except ImportError:
    DDGS = None

# --- DATA IMPORTS ---
try:
    from plants_data import UK_PLANTS
except ImportError:
    UK_PLANTS = {"edible": [], "poisonous": []}

try:
    from lessons_data import LESSON_CONTENT
except ImportError:
    LESSON_CONTENT = {}

try:
    from game_config import (ACHIEVEMENTS, HABITAT_ICONS, SEASON_ICONS,
                             SEASON_MONTHS, SURVIVAL_DIFFICULTY,
                             VILLAGE_ITEMS, VILLAGE_BUILDINGS,
                             VILLAGE_PRODUCTION, BASE_PRICES,
                             KITCHEN_RECIPES, BASICS)
except ImportError:
    ACHIEVEMENTS = {}
    HABITAT_ICONS = {}
    SEASON_ICONS = {}
    SEASON_MONTHS = {}
    SURVIVAL_DIFFICULTY = {}
    VILLAGE_ITEMS = {}
    VILLAGE_BUILDINGS = {}
    VILLAGE_PRODUCTION = {}
    BASE_PRICES = {}
    KITCHEN_RECIPES = {}
    BASICS = {}

# ==========================================
# CONFIGURATION
# ==========================================

try:
    api_key = st.secrets["OPENAI_API_KEY"]
except Exception:
    api_key = ""

if not api_key:
    client = None
else:
    try:
        client = OpenAI(api_key=api_key)
    except Exception:
        client = None

try:
    PEXELS_API_KEY = st.secrets["PEXELS_API_KEY"]
except Exception:
    PEXELS_API_KEY = ""

# Alpaca connection is handled per-user via connect_with_keys()
# No global API object — each user connects with their own keys
alpaca_api = None

try:
    TAVILY_API_KEY = st.secrets["TAVILY_API_KEY"]
except Exception:
    TAVILY_API_KEY = ""

# ==========================================
# DATABASE
# ==========================================
DB_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'rocen_save.db')


def init_db():
    try:
        conn = sqlite3.connect(DB_PATH)
        c = conn.cursor()
        c.execute('''CREATE TABLE IF NOT EXISTS saves
                     (username TEXT PRIMARY KEY, data TEXT, last_saved TEXT)''')
        conn.commit()
        conn.close()
    except Exception as e:
        print(f"DB Init Error: {e}")


def save_game(username, data):
    if not username:
        return False
    try:
        conn = sqlite3.connect(DB_PATH)
        c = conn.cursor()
        c.execute(
            "INSERT OR REPLACE INTO saves (username, data, last_saved) VALUES (?, ?, ?)",
            (username, json.dumps(data), datetime.now().isoformat())
        )
        conn.commit()
        conn.close()
        return True
    except Exception as e:
        print(f"Save Error: {e}")
        return False


def load_game(username):
    if not username:
        return None
    try:
        conn = sqlite3.connect(DB_PATH)
        c = conn.cursor()
        c.execute("SELECT data FROM saves WHERE username=?", (username,))
        row = c.fetchone()
        conn.close()
        if row:
            return json.loads(row[0])
        return None
    except Exception as e:
        print(f"Load Error: {e}")
        return None


def get_save_data():
    keys_to_save = [
        'game_score', 'game_lives', 'game_streak', 'total_plants_identified',
        'player_title', 'total_xp', 'master_inventory', 'achievements',
        'unlocked_recipes', 'kitchen_score', 'kitchen_inventory',
        'season_badge_progress', 'survival_lives', 'survival_score',
        'survival_correct_count', 'survival_level', 'survival_cases_solved',
        'quiz_score', 'daily_streak', 'village', 'farm_game',
        'challenge_completed', 'completed_modules',
    ]
    data = {}
    for key in keys_to_save:
        if key in st.session_state:
            val = st.session_state[key]
            if isinstance(val, set):
                val = list(val)
            data[key] = val

    for title in LESSON_CONTENT.keys():
        progress_key = f"module_progress_{title}"
        if progress_key in st.session_state:
            data[progress_key] = st.session_state[progress_key]

    return data


def apply_save_data(data):
    if data:
        for key, val in data.items():
            if isinstance(val, list) and key in ['season_badge_progress']:
                val = list(val)
            st.session_state[key] = val


# ==========================================
# THEMES
# ==========================================

def apply_forest_theme():
    st.markdown("""
    <style>
    .stApp {
        background-color: #F5F5DC;
        background-image: radial-gradient(#E8E8D0 1px, transparent 1px);
        background-size: 20px 20px;
    }
    .stMarkdown, .stHeader, p, label {
        color: #2E4A3E !important;
    }
    h1, h2, h3 {
        color: #5D4037 !important;
        font-family: 'Georgia', serif !important;
        border-bottom: 2px solid #A5D6A7;
        padding-bottom: 10px;
    }
    .stButton > button {
        background-color: #4CAF50;
        color: white;
        border-radius: 20px;
        border: 2px solid #388E3C;
        padding: 10px 24px;
        font-weight: bold;
        transition: all 0.3s;
        box-shadow: 2px 2px 5px rgba(0,0,0,0.1);
    }
    .stButton > button:hover {
        background-color: #388E3C;
        transform: scale(1.02);
        box-shadow: 4px 4px 8px rgba(0,0,0,0.2);
    }
    .element-container {
        background-color: rgba(255, 255, 255, 0.8);
        border-radius: 10px;
        border-left: 5px solid #4CAF50;
        padding: 15px;
        margin: 10px 0;
        box-shadow: 2px 2px 10px rgba(0,0,0,0.05);
    }
    [data-testid="stSidebar"] {
        background-color: #E8F5E9;
    }
    [data-testid="stMetric"] {
        background-color: #FFFFFF;
        border-radius: 10px;
        padding: 10px;
        box-shadow: 0 0 0 1px #C8E6C9;
    }
    .stTabs [data-badges="badge"] {
        background-color: #F1F8E9;
        color: #2E4A3E;
    }
    button[aria-selected="true"] {
        background-color: #66BB6A !important;
        color: white !important;
    }
    .warning-box {
        background-color: #FFF3E0;
        border-left: 5px solid #FF9800;
        padding: 10px;
        border-radius: 5px;
    }
    </style>
    """, unsafe_allow_html=True)


def apply_brand_theme():
    st.markdown("""
    <style>
    .stApp, section.main > div { background-color: #3A2416; }
    .stMarkdown, .stHeader, p, label,
    .stTextInput > div > div > input,
    .stTextArea > div > div > textarea { color: #FFFFFF !important; }
    h1, h2, h3 { color: #B87333 !important; font-family: 'Georgia', serif !important;
                 border-bottom: 2px solid #6B4226; padding-bottom: 10px; }
    .stButton > button { background-color: #6B4226; color: white !important;
                         border-radius: 20px; border: 1px solid #B87333;
                         padding: 10px 24px; font-weight: bold;
                         box-shadow: 2px 2px 5px rgba(0,0,0,0.2); }
    .stButton > button:hover { background-color: #B87333; color: #FFFFFF !important;
                               transform: scale(1.02); }
    [data-testid="stSidebar"] { background-color: #1B3A28; }
    [data-testid="stSidebar"] * { color: #FFFFFF !important; }
    [data-testid="stSidebar"] .stMarkdown hr { border-color: #B87333; }
    [data-testid="stMetric"] { background-color: #6B4226; border-radius: 10px;
                               padding: 15px; box-shadow: 0 0 0 1px #B87333;
                               border-left: 5px solid #B87333; color: white; }
    [data-testid="stMetric"] label { color: #B87333 !important; }
    [data-testid="stMetric"] [data-testid="stMetricValue"] { color: white !important; }
    .stTabs [data-badges="badge"] { background-color: #3F5F2A; color: #FFFFFF; }
    button[aria-selected="true"] { background-color: #B87333 !important;
                                   color: #FFFFFF !important;
                                   border-bottom: 2px solid #6B4226; }
    .streamlit-expanderHeader { background-color: #6B4226 !important;
                                border-radius: 10px; border-left: 5px solid #B87333;
                                color: #FFFFFF !important; font-weight: bold; }
    .stTextInput > div > div > input,
    .stTextArea > div > div > textarea,
    .stSelectbox > div > div { background-color: #3F5F2A !important;
                               color: #FFFFFF !important; border: 1px solid #B87333; }
    @media (max-width: 768px) {
        .plant-card { padding: 10px !important; }
        div.grid-game div.stButton > button { font-size: 1em !important; }
    }
    </style>
    """, unsafe_allow_html=True)


# ==========================================
# DATA
# ==========================================
UK_ENVIRONMENTS = {
    "Woodlands": {"description": "Areas covered with trees, including forests and copses. Rich in fungi, nuts, and shade-loving plants.", "risk_level": "Medium", "icon": "🌲"},
    "Hedgerows": {"description": "Borders of fields and roads. Often the best places for berries and nuts.", "risk_level": "Low", "icon": "🤠"},
    "Meadows & Grassland": {"description": "Open fields, pastures, and grassy areas. Good for salad greens and flowers.", "risk_level": "Low", "icon": "🌸"},
    "Coastal": {"description": "Beaches, cliffs, sand dunes, and salt marshes. Unique saline plants and seaweeds.", "risk_level": "Medium", "icon": "🏖️"},
    "Riverbanks & Wetlands": {"description": "Edges of rivers, streams, and marshes. Abundant but home to the most dangerous plants.", "risk_level": "High", "icon": "💧"},
    "Urban & Gardens": {"description": "Parks, allotments, and waste ground in cities. Often overlooked foraging spots.", "risk_level": "Medium", "icon": "🏙️"}
}


# ==========================================
# SESSION STATE
# ==========================================
def init_session_state():
    defaults = {
        'game_score': 0, 'game_lives': 3, 'game_streak': 0,
        'current_question': None, 'bonus_round': False,
        'village': None, 'farm_game': None,
        'survival_lives': 3, 'survival_score': 0,
        'survival_correct_count': 0, 'survival_level': 1,
        'survival_current_case': None, 'survival_result': None,
        'survival_cases_solved': 0,
        'quiz_score': 0, 'quiz_q_num': 0, 'quiz_max': 5,
        'q_data': None, 'daily_streak': 0,
        'challenge_completed': False,
        'active_season': "Summer", 'season_badge_progress': [],
        'player_title': "Novice Gatherer",
        'total_plants_identified': 0, 'total_xp': 0,
        'master_inventory': {}, 'kitchen_inventory': {},
        'achievements': {k: False for k in ACHIEVEMENTS.keys()} if ACHIEVEMENTS else {},
        'unlocked_recipes': [], 'kitchen_score': 0,
        'completed_modules': [],
        'chat_language': 'English', 'messages': [],
        'selected_page': "Home", 'book_content': {}, 'book_outline': "",
        'username': '', 'game_loaded': False,
    }
    for key, value in defaults.items():
        if key not in st.session_state:
            st.session_state[key] = value
    init_db()


# ==========================================
# AI FUNCTIONS
# ==========================================
def generate_text(prompt, system_role="You are a helpful assistant.", history=None, tools=None, force_tool_use=False, model="gpt-4o"):
    """Generate text using GPT-4o or GPT-4o-mini. Supports native function calling when tools are provided."""
    if client is None:
        return "⚠️ AI Content Unavailable (API Key missing)."
    try:
        messages = [{"role": "system", "content": system_role}]

        if history:
            for msg in history:
                if msg.get("role") in ("user", "assistant", "tool"):
                    messages.append(msg)

        messages.append({"role": "user", "content": prompt})

        kwargs = {
            "model": model,
            "messages": messages,
            "temperature": 0.3,
        }

        if tools:
            kwargs["tools"] = tools
            if force_tool_use:
                kwargs["tool_choice"] = "required"
            else:
                kwargs["tool_choice"] = "auto"

        response = client.chat.completions.create(**kwargs)
        return response
    except Exception as e:
        class FakeResponse:
            class Choice:
                class Message:
                    content = f"Error: {str(e)}"
                    tool_calls = None
                message = Message()
            choices = [Choice()]
        return FakeResponse()



def generate_voice(text, filename="temp_audio.mp3", language="en"):
    if not EDGE_TTS_AVAILABLE:
        return None
    try:
        voice = "vi-VN-HoaiMyNeural" if language == "Vietnamese" else "en-GB-SoniaNeural"
        communicate = edge_tts.Communicate(text, voice)
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        loop.run_until_complete(communicate.save(filename))
        loop.close()
        return filename
    except Exception as e:
        return None


def clean_text_for_audio(text):
    if not text:
        return ""
    text = text.replace("**", "").replace("##", "").replace("*", "")
    icon_map = {
        "🌿": "Plant", "🌲": "Woodland", "☠️": "Poison", "✅": "Correct",
        "❌": "Wrong", "🕵️": "Inspector", "⚡": "Bonus", "🎓": "Graduate",
        "🌱": "Seedling", "🍄": "Mushroom", "🏖️": "Coastal", "🏡": "Urban",
        "🌾": "Meadow", "💧": "Water", "🪨": "Rock",
    }
    for icon, word in icon_map.items():
        text = text.replace(icon, word)
    return text.strip()


# ==========================================
# IMAGE & VIDEO
# ==========================================
def analyze_image_plant(image_data):
    try:
        base64_image = base64.b64encode(image_data).decode('utf-8')
        response = client.chat.completions.create(
            model="gpt-4o",
            messages=[
                {
                    "role": "user",
                    "content": [
                        {"type": "text", "text": "Identify this plant:"},
                        {
                            "type": "image_url",
                            "image_url": {
                                "url": f"data:image/jpeg;base64,{base64_image}"
                            },
                        },
                    ],
                }
            ],
            max_tokens=300,
        )
        return response.choices[0].message.content
    except Exception as e:
        return f"Error: {e}"


def get_pexels_video(query):
    if not PEXELS_API_KEY or PEXELS_API_KEY == "YOUR_PEXELS_KEY_HERE":
        return None
    try:
        url = (
            f"https://api.pexels.com/videos/search?query={query}"
            f"&per_page=5&orientation=portrait"
        )
        headers = {"Authorization": PEXELS_API_KEY}
        response = requests.get(url, headers=headers)
        data = response.json()
        if data.get('videos'):
            for video in data['videos']:
                video_files = video.get('video_files', [])
                hd_video = [
                    v for v in video_files
                    if v.get('quality') == 'hd' and v.get('width', 0) >= 720
                ]
                if hd_video:
                    return hd_video[0]['link']
                if video_files:
                    return video_files[0]['link']
        return None
    except Exception as e:
        print(f"Pexels Error: {e}")
        return None


# ==========================================
# SEARCH
# ==========================================
def search_internet(query, max_results=3):
    try:
        from duckduckgo_search import DDGS
        with DDGS() as ddgs:
            results = []
            search_gen = ddgs.text(query, max_results=max_results)
            if search_gen:
                for r in search_gen:
                    results.append(r.get('body', ''))
            return results
    except Exception as e:
        print(f"Search error: {e}")
        return []


# ==========================================
# JOURNAL
# ==========================================
CHAT_DIR = Path("chat_history")
CHAT_DIR.mkdir(exist_ok=True)
JOURNAL_DIR = Path("foraging_journal")
JOURNAL_DIR.mkdir(exist_ok=True)


def save_journal_entry(entry):
    try:
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = JOURNAL_DIR / f"entry_{timestamp}.json"
        with open(filename, 'w', encoding='utf-8') as f:
            json.dump(entry, f, ensure_ascii=False, indent=2)
        return True
    except Exception:
        return False


def load_journal_entries():
    entries = []
    try:
        for file in sorted(JOURNAL_DIR.glob("*.json"), reverse=True):
            with open(file, 'r', encoding='utf-8') as f:
                entries.append(json.load(f))
    except Exception:
        pass
    return entries


# ==========================================
# DYNAMIC SURVIVAL CASE GENERATION
# ==========================================
def generate_survival_cases():
    cases = []

    fallback_cases = [
        {
            "level": 1,
            "clue": "You find a tall plant with white umbrella-shaped flowers. The stem is smooth with purple spots.",
            "rule": "In the Carrot family, purple spots usually mean POISON.",
            "safe_plant": "Wild Carrot", "danger_plant": "Hemlock",
            "safe_icon": "🥕", "danger_icon": "☠️",
            "fact": "Hemlock has smooth stems with purple spots. Wild Carrot has hairy stems.",
            "safe_habitat": "Meadows",
        },
        {
            "level": 1,
            "clue": "You find a plant with big green leaves. You squash a leaf and it smells strongly of garlic!",
            "rule": "A strong garlic smell is usually a good sign.",
            "safe_plant": "Wild Garlic", "danger_plant": "Lily of the Valley",
            "safe_icon": "🌿", "danger_icon": "☠️",
            "fact": "Wild Garlic smells of garlic. Lily of the Valley does not.",
            "safe_habitat": "Woodland",
        },
    ]

    for plant in UK_PLANTS.get('edible', []):
        lookalikes = plant.get('lookalikes', [])
        for la in lookalikes:
            danger_level = la.get('danger', '') if isinstance(la, dict) else ''
            if danger_level not in ['POISONOUS', 'DEADLY', 'HIGH', 'EXTREME']:
                continue

            danger_name = la.get('name', 'Unknown') if isinstance(la, dict) else str(la)
            safe_name = plant['name']
            plant_difficulty = plant.get('difficulty', 2)

            level = 1
            if plant.get('category') == 'Fungi' or plant_difficulty >= 3:
                level = 2 if plant_difficulty == 2 else 3

            id_keys = plant.get('id_keys', {})
            if id_keys:
                features = list(id_keys.items())[:3]
                clue_parts = []
                for k, v in features:
                    clue_parts.append(f"{k}: {v}")
                clue = "You find a plant. " + ". ".join(clue_parts) + "."
            else:
                clue = f"You find {safe_name}. {plant.get('description', '')[:100]}..."

            danger_diff = la.get('diff', '') if isinstance(la, dict) else ''
            rule = f"Key Difference: {danger_diff}" if danger_diff else f"{safe_name} has special identifying features."

            confusion_notes = plant.get('confusion_notes', '')
            if confusion_notes:
                fact = confusion_notes
            else:
                fact = f"{safe_name} is SAFE. {danger_name} is {danger_level}."

            raw_habitat = plant.get('habitat', 'Various').split(',')[0].strip()
            habitat_map = {
                "Woodlands": "Woodland", "Woods": "Woodland", "Wood": "Woodland",
                "Hedgerows": "Hedgerow", "Hedgerow": "Hedgerow",
                "Meadows": "Meadow", "Grassland": "Meadow", "Fields": "Meadow",
                "Coastal": "Coastal", "Urban": "Urban", "Gardens": "Urban",
                "Damp": "Woodland", "Riverbanks": "Woodland",
            }
            safe_habitat = habitat_map.get(raw_habitat, "Woodland")

            safe_icon = "🌿"
            danger_icon = "☠️" if danger_level in ['DEADLY', 'EXTREME'] else "⚠️"
            cat = plant.get('category', '')
            if cat == 'Fungi':
                safe_icon = "🍄"
            elif cat == 'Tree':
                safe_icon = "🌲"

            cases.append({
                "level": level,
                "clue": clue,
                "rule": rule,
                "safe_plant": safe_name,
                "danger_plant": danger_name,
                "safe_icon": safe_icon,
                "danger_icon": danger_icon,
                "fact": fact,
                "safe_habitat": safe_habitat,
            })

    if not cases:
        cases = fallback_cases

    return cases


# ==========================================
# DYNAMIC FORAGING QUESTION GENERATION
# ==========================================
def generate_foraging_question(plant, question_type=None):
    all_plants = UK_PLANTS.get('edible', []) + UK_PLANTS.get('poisonous', [])

    if question_type is None:
        has_danger = any(
            (la.get('danger', '') if isinstance(la, dict) else '')
            in ['POISONOUS', 'DEADLY', 'HIGH', 'EXTREME']
            for la in plant.get('lookalikes', [])
        )
        if has_danger:
            question_type = random.choices(
                ['habitat', 'identification', 'lookalike', 'parts', 'season', 'warning'],
                weights=[3, 3, 3, 2, 2, 1], k=1
            )[0]
        else:
            question_type = random.choices(
                ['habitat', 'identification', 'parts', 'season', 'warning'],
                weights=[3, 3, 2, 2, 1], k=1
            )[0]

    if question_type == 'habitat':
        raw_habitat = plant['habitat'].split(',')[0].strip()
        habitat_map = {
            "Woodlands": "Woodland", "Woods": "Woodland", "Wood": "Woodland",
            "Hedgerows": "Hedgerow", "Hedgerow": "Hedgerow",
            "Meadows": "Meadow", "Grassland": "Meadow", "Fields": "Meadow",
            "Coastal": "Coastal", "Urban": "Urban", "Gardens": "Urban",
            "Damp": "Woodland", "Riverbanks": "Woodland",
        }
        correct = habitat_map.get(raw_habitat, "Woodland")
        all_habitats = ["Woodland", "Coastal", "Hedgerow", "Urban", "Meadow"]
        wrong = [h for h in all_habitats if h != correct]
        options = [correct] + random.sample(wrong, min(3, len(wrong)))
        random.shuffle(options)
        return {
            'type': 'habitat', 'plant': plant,
            'question': f"Where does {plant['name']} typically grow?",
            'correct': correct, 'options': options,
            'explanation': f"{plant['name']} grows in {plant['habitat']}.",
            'points': 10,
        }

    elif question_type == 'identification':
        id_keys = plant.get('id_keys', {})
        if not id_keys:
            return generate_foraging_question(plant, 'habitat')
        correct_key, correct_value = random.choice(list(id_keys.items()))
        wrong_options = []
        used_values = {correct_value}
        for other_plant in random.sample(all_plants, min(len(all_plants), 8)):
            if other_plant['name'] == plant['name']:
                continue
            other_keys = other_plant.get('id_keys', {})
            for k, v in other_keys.items():
                if v not in used_values and len(wrong_options) < 3:
                    wrong_options.append(v)
                    used_values.add(v)
                    break
        while len(wrong_options) < 3:
            wrong_options.append("Unknown feature")
        options = [correct_value] + wrong_options[:3]
        random.shuffle(options)
        return {
            'type': 'identification', 'plant': plant,
            'question': f"Which is a key identifier for {plant['name']}?",
            'correct': correct_value, 'options': options,
            'explanation': f"{plant['name']}: {correct_key} - {correct_value}",
            'points': 12,
        }

    elif question_type == 'lookalike':
        dangerous_lookalikes = [
            la for la in plant.get('lookalikes', [])
            if (la.get('danger', '') if isinstance(la, dict) else '')
            in ['POISONOUS', 'DEADLY', 'HIGH', 'EXTREME']
        ]
        if not dangerous_lookalikes:
            return generate_foraging_question(plant, 'identification')
        chosen = random.choice(dangerous_lookalikes)
        correct = chosen['name'] if isinstance(chosen, dict) else str(chosen)
        wrong_options = []
        used_names = {correct, plant['name']}
        for other_plant in random.sample(all_plants, min(len(all_plants), 10)):
            if other_plant['name'] not in used_names and len(wrong_options) < 2:
                wrong_options.append(other_plant['name'])
                used_names.add(other_plant['name'])
        while len(wrong_options) < 2:
            wrong_options.append("Unknown plant")
        options = [correct] + wrong_options[:2]
        random.shuffle(options)
        explanation = plant.get('confusion_notes', '')
        if not explanation and isinstance(chosen, dict):
            explanation = chosen.get('diff', 'Check carefully!')
        return {
            'type': 'lookalike', 'plant': plant,
            'question': f"Which plant is a DANGEROUS lookalike of {plant['name']}?",
            'correct': correct, 'options': options,
            'explanation': explanation,
            'points': 15,
        }

    elif question_type == 'parts':
        raw_parts = plant.get('parts', 'Leaves')
        if isinstance(raw_parts, str):
            parts = [p.strip() for p in raw_parts.split(',')]
        else:
            parts = raw_parts
        if not parts:
            parts = ['Leaves']
        correct = parts[0]
        wrong_parts = ["Roots", "Berries", "Flowers", "Seeds", "Bark", "Stem"]
        wrong = [p for p in wrong_parts if p not in parts]
        options = [correct] + random.sample(wrong, min(2, len(wrong)))
        random.shuffle(options)
        return {
            'type': 'parts', 'plant': plant,
            'question': f"Which part of {plant['name']} can you eat?",
            'correct': correct, 'options': options,
            'explanation': f"{plant['name']}: Edible parts are {', '.join(parts)}.",
            'points': 10,
        }

    elif question_type == 'season':
        correct_months = plant.get('months', ['Summer'])
        correct = random.choice(correct_months)
        all_months = ["January", "March", "June", "August", "October", "December"]
        wrong_months = [m for m in all_months if m not in correct_months]
        if not wrong_months:
            wrong_months = ["January", "March"]
        options = [correct] + random.sample(wrong_months, min(2, len(wrong_months)))
        random.shuffle(options)
        return {
            'type': 'season', 'plant': plant,
            'question': f"When is {plant['name']} best harvested?",
            'correct': correct, 'options': options,
            'explanation': f"{plant['name']} is best in {', '.join(correct_months)}.",
            'points': 10,
        }

    elif question_type == 'warning':
        warning = plant.get('warnings', plant.get('description', ''))
        if not warning:
            return generate_foraging_question(plant, 'habitat')
        if random.random() < 0.5:
            return {
                'type': 'warning', 'plant': plant,
                'question': f"True or False: {warning}",
                'correct': "True", 'options': ["True", "False"],
                'explanation': f"This is correct: {warning}",
                'points': 12,
            }
        else:
            false_warning = warning
            swaps = [
                ("edible", "poisonous"), ("safe", "dangerous"),
                ("cook", "eat raw"), ("hairy", "smooth"),
                ("round", "flat"), ("garlic", "onion"),
                ("must", "can skip"),
            ]
            for orig, swap in swaps:
                if orig.lower() in warning.lower():
                    false_warning = warning.lower().replace(orig.lower(), swap.lower())
                    false_warning = false_warning[0].upper() + false_warning[1:]
                    break
            if false_warning == warning:
                return {
                    'type': 'warning', 'plant': plant,
                    'question': f"True or False: {warning}",
                    'correct': "True", 'options': ["True", "False"],
                    'explanation': f"This is correct: {warning}",
                    'points': 12,
                }
            return {
                'type': 'warning', 'plant': plant,
                'question': f"True or False: {false_warning}",
                'correct': "False", 'options': ["True", "False"],
                'explanation': f"The correct warning is: {warning}",
                'points': 12,
            }

    return generate_foraging_question(plant, 'habitat')


# ==========================================
# SIDEBAR
# ==========================================
def render_sidebar():
    try:
        st.sidebar.image("logo.png", width=150)
    except Exception:
        st.sidebar.title("🌿 Rocen Homesteady")

    st.sidebar.markdown("### 💾 Save Progress")
    username = st.sidebar.text_input(
        "Your Name",
        value=st.session_state.get('username', ''),
        key='username_input',
    )
    if username != st.session_state.get('username', ''):
        st.session_state['username'] = username

    col1, col2 = st.sidebar.columns(2)
    with col1:
        if st.button("💾 Save", key='save_btn_sidebar'):
            if st.session_state.get('username'):
                data = get_save_data()
                if save_game(st.session_state['username'], data):
                    st.sidebar.success("Game saved!")
                else:
                    st.sidebar.error("Save failed!")
            else:
                st.sidebar.warning("Enter a name to save.")
    with col2:
        if st.button("📂 Load", key='load_btn_sidebar'):
            if st.session_state.get('username'):
                data = load_game(st.session_state['username'])
                if data:
                    apply_save_data(data)
                    st.session_state['game_loaded'] = True
                    st.sidebar.success("Game loaded!")
                    st.rerun()
                else:
                    st.sidebar.warning("No save found.")
            else:
                st.sidebar.warning("Enter a name to load.")

    st.sidebar.markdown("---")

    total_edible = len(UK_PLANTS.get('edible', []))
    collected = len(st.session_state.get('master_inventory', {}))
    st.sidebar.metric("🌱 Species Found", f"{collected}/{total_edible}")

    achievements = st.session_state.get('achievements', {})
    unlocked_count = sum(1 for v in achievements.values() if v)
    total_ach = len(ACHIEVEMENTS) if ACHIEVEMENTS else 0
    st.sidebar.metric("🏆 Achievements", f"{unlocked_count}/{total_ach}")

    unlocked_keys = [k for k, v in achievements.items() if v]
    if unlocked_keys:
        st.sidebar.caption("Recently Unlocked:")
        for key in unlocked_keys[-3:]:
            if ACHIEVEMENTS and key in ACHIEVEMENTS:
                st.sidebar.write(f"✅ {ACHIEVEMENTS[key]['name']}")

    st.sidebar.markdown("---")
    st.sidebar.warning("⚠️ **Safety First**")
    st.sidebar.markdown("""
    - Never eat a plant based solely on an app.
    - Always cross-reference with a field guide.
    - **UK Law:** Only pick for personal use.
    - It is illegal to uproot plants without permission.
    """)

    if st.sidebar.button("🔄 Reset All Progress"):
        for key in list(st.session_state.keys()):
            del st.session_state[key]
        st.rerun()

    st.sidebar.markdown("---")
    st.sidebar.markdown("""
    <div style="text-align: center; font-size: 12px; line-height: 1.4;">
        <b>Rocen Homesteady LTD</b><br>
        4th Floor, 14 Museum Place<br>
        Cardiff, CF10 3BH
    </div>
    """, unsafe_allow_html=True)


# ==========================================
# CSS
# ==========================================
def load_css():
    try:
        with open("style.css") as f:
            st.markdown(f"<style>{f.read()}</style>", unsafe_allow_html=True)
    except FileNotFoundError:
        pass
