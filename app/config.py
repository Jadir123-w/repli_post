
import environ # type: ignore
from dotenv import load_dotenv

load_dotenv()

env = environ.Env()

environ.Env.read_env()

GOOGLE_CREDENTIALS_PATH = env('GOOGLE_CREDENTIALS_PATH', None)
GOOGLE_APPLICATION_CREDENTIALS = env('GOOGLE_APPLICATION_CREDENTIALS', None)
MARCELLA_GOOGLE_API_KEY = env('MARCELLA_GOOGLE_API_KEY', None)
CREDENTIALS_PATH = env('CREDENTIALS_PATH', None)


MONGO_DB = env('MONGO_DB', None)