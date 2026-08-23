from config import CHAT_ID_FILE


def save_chat_id(chat_id):
    with open(CHAT_ID_FILE, "w") as f:
        f.write(str(chat_id))


def load_chat_id():
    try:
        with open(CHAT_ID_FILE) as f:
            return int(f.read().strip())
    except (FileNotFoundError, ValueError):
        return None
