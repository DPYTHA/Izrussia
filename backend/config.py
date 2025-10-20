import os

class Config:
    SECRET_KEY = os.environ.get("SECRET_KEY", "your-secret-key")
    SQLALCHEMY_DATABASE_URI = os.environ.get("DATABASE_URL", "postgresql://postgres:Pytha1991@localhost:5432/izrussia")
    MAIL_SERVER = 'smtp.gmail.com'
    MAIL_PORT = 587
    MAIL_USE_TLS = True
    MAIL_USERNAME = 'moua19878@gmail.com'  
    MAIL_PASSWORD = 'upqc fxna tvyr xwvp'
    MAIL_DEFAULT_SENDER = ('IZRUSSIA', 'moua19878@gmail.com')




