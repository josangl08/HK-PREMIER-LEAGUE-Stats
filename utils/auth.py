import os
from flask_login import UserMixin
from dotenv import load_dotenv

# Cargar variables de entorno
load_dotenv()

# Definir clase User para Flask-Login
class User(UserMixin):
    def __init__(self, id):
        self.id = id
        self.name = "admin"
        self.password = os.getenv("ADMIN_PASSWORD")
        
    def get_id(self):
        return self.id
    
    @property
    def is_authenticated(self):
        return True
    
    @property
    def is_active(self):
        return True
    
    @property
    def is_anonymous(self):
        return False

# Esta función simplificada imita la consulta a una base de datos
def load_user(user_id):
    if user_id == os.getenv("ADMIN_USER"):
        return User(user_id)
    return None

# Función para verificar las credenciales del usuario
def validate_credentials(username, password):
    if username == os.getenv("ADMIN_USER") and password == os.getenv("ADMIN_PASSWORD"):
        return User(username)
    return None