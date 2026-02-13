from decouple import config
from fastapi.security import OAuth2PasswordBearer
from pydantic_settings import BaseSettings
from fastapi import Request


TITLE = config('TITLE')
VERSION = config('VERSION')
ACCESS_TOKEN_EXPIRE = config('ACCESS_TOKEN_EXPIRE', cast=int)
SECRET_KEY = config('SECRET_KEY')
ALGORITHM = config('ALGORITHM')
TOKEN_URL = config('TOKEN_ENDPOINT')

# DATABASE CONFIG
DB_USER = config('DB_USER')
DB_PASSWORD = config('DB_PASSWORD')
DB_HOST = config('DB_HOST')
DB_PORT = config('DB_PORT', cast=int)
DB_NAME = config('DB_NAME')

# SUPERUSER CONFIG
SU_FIRST_NAME = config('SU_FIRST_NAME')
SU_LAST_NAME = config('SU_LAST_NAME')
SU_USERNAME = config('SU_USERNAME')
SU_EMAIL = config('SU_EMAIL')
SU_MOBILE = config('SU_MOBILE')
SU_PASSWORD = config('SU_PASSWORD')

DATABASE_URL = f"mysql+pymysql://{DB_USER}:{DB_PASSWORD}@{DB_HOST}:{DB_PORT}/{DB_NAME}"

oauth2_scheme = OAuth2PasswordBearer(tokenUrl=TOKEN_URL)

# EMAIL CONFIG
EMAIL_SERVICE = config('EMAIL_SERVICE')
EMAIL_PORT = config('EMAIL_PORT', cast=int)
EMAIL_ID = config('EMAIL_ID')
EMAIL_PASSWORD = config('EMAIL_PASSWORD')
EMAIL_FROM_NAME = config('EMAIL_FROM_NAME') 
SUPPORT_EMAIL = config('SUPPORT_EMAIL') 


