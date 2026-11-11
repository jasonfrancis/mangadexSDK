from datetime import datetime
import logging
from typing import Any, Optional
from .serializable import Serializable, SerializableProperty
from .constants import Constants
from .errors import MangaDexHttpError
from .httpClient import HttpClient
from os import path
import sys
import keyring
import getpass
import requests
import jwt

log = logging.getLogger("mangadexSdk")

# Module-level singleton HttpClient. All classmethod shims on MangaDexSdk
# delegate to this so anonymous (non-instantiated) usage keeps working while
# still benefiting from shared rate-limit state, connection pooling, and the
# retry/backoff policy.
_default_client: Optional[HttpClient] = None


def get_default_client() -> HttpClient:
	"""Return the process-wide shared ``HttpClient``.

	The first call constructs one with SDK defaults; subsequent calls return
	the same instance so rate-limit buckets are honored across every request
	the SDK makes.
	"""
	global _default_client
	if _default_client is None:
		_default_client = HttpClient()
	return _default_client


def set_default_client(client: HttpClient) -> None:
	"""Replace the process-wide shared ``HttpClient``. Useful for tests and
	for power users who want to tune retry/backoff behavior globally."""
	global _default_client
	_default_client = client


class TokenResponse(Serializable):
	def __init__(self, session:str = None, refresh:str = None, tokensAssigned:float = None):
		self.session = session
		self.refresh = refresh
		self.tokensAssigned = datetime.utcnow().timestamp() if tokensAssigned == None else tokensAssigned
	def tokenExpired(self) -> bool:
		#tokens expire after 15 minutes
		decoded = jwt.decode(self.session, algorithms=["RS256"], options={"verify_signature": False})
		if("exp" not in decoded):
			return True
		expires = datetime.utcfromtimestamp(decoded["exp"])
		
		result = datetime.utcnow() >= expires
		return result
	def refreshExpired(self) -> bool:
		#refresh tokens expire after 4 hours
		decoded = jwt.decode(jwt=self.refresh, algorithms=["RS256"], options={"verify_signature": False})
		if("exp" not in decoded):
			return True
		expires = datetime.utcfromtimestamp(decoded["exp"])
		return datetime.utcnow() >= expires

class Settings(Serializable):
	def __init__(self, username:str = None, token:TokenResponse = None):
		self.username = username
		self.token = token
		# make sure our seriealizer knows how to handle child objects.
		super().__init__([SerializableProperty(TokenResponse, self.getAttributeName(self.token))])

	@staticmethod
	def getSettings():
		if(path.exists(Constants.SETTINGS_FILE)):
			log.info("%s exists", Constants.SETTINGS_FILE)
			settings = Settings.readFromFile()
			if(not settings.username):
				log.info("Username not found in settings file.")
				settings.setUsername()
			return settings
		else:
			log.info("%s does not exist", Constants.SETTINGS_FILE)
			settings = Settings()
			settings.setUsername()
			return settings
	
	def setUsername(self):
		self.username = input("Enter your MangaDex username: ")
		log.info("Saving username \"%s\" to %s ...", self.username, Constants.SETTINGS_FILE)
		self.writeToFile()
		log.info("Done.")

	def updateSession(self, token:TokenResponse):
		self.token = token
		log.info("Writing updated token to settings")
		self.writeToFile()

	def writeToFile(self):
		settingsJson = self.toJson()
		with open(Constants.SETTINGS_FILE, "w") as writer:
			writer.write(settingsJson)
	
	@staticmethod
	def readFromFile():
		with open(Constants.SETTINGS_FILE, "r") as reader:
			settingsString = reader.read()
			return Settings.fromJson(settingsString)

class Credentials:
	def __init__(self, settings:Settings):
		if("--update-username" in sys.argv):
			settings.setUsername()
		self.username = settings.username
		
		if("--update-password" in sys.argv):
			self.deletePassword()
		self.password = keyring.get_password(Constants.SERVICE_ID, self.username)

		if(not self.password):
			log.info("Password for user \"%s\" not found in the keyring.  Enter password.", self.username)
			self.setPassword()
	
	def setPassword(self):
		self.password = getpass.getpass()
		keyring.set_password(Constants.SERVICE_ID, self.username, self.password)
	
	def deletePassword(self):
		keyring.delete_password(Constants.SERVICE_ID, self.username)


class MangaDexSdk:
	def __init__(self):
		self.settings = Settings.getSettings()
		self.credentials = Credentials(self.settings)
		self.session = Session(self.settings, self.credentials)

	@classmethod
	def postJson(cls, path:str, content:Any) -> requests.Response:
		"""POST ``content`` as JSON to ``path``. Delegates to the shared
		``HttpClient`` singleton so rate-limit buckets and retries are
		honored.

		Raises ``MangaDexHttpError`` (or a subclass such as
		``MangaDexRateLimitError`` / ``MangaDexAuthError``) on failure.
		"""
		return get_default_client().post_json(path, content)

	@classmethod
	def get(cls, path:str) -> requests.Response:
		"""GET ``path``. Delegates to the shared ``HttpClient`` singleton.

		Raises ``MangaDexHttpError`` (or a subclass) on failure.
		"""
		return get_default_client().get(path)

	def getAuthenticated(self, path:str) -> requests.Response:
		headers = { "Authorization": f"Bearer {self.session.getBearerToken()}"}
		return get_default_client().get(path, headers=headers)



class LoginResponse(Serializable):
	def __init__(self, result:str = None, token:TokenResponse = None, message:str = None):
		self.result = result
		self.token = token
		self.message = message
		# Instructions about how to deserialize attributes
		super().__init__([SerializableProperty(TokenResponse, self.getAttributeName(self.token))])

class Session:
	def __init__(self, settings:Settings, credentials:Credentials):
		self.settings = settings
		self.credentials = credentials
		
	def getBearerToken(self) -> str:
		if(self.settings.token == None or self.settings.token.refreshExpired()):
			self.login()
		elif(self.settings.token.tokenExpired()):
			log.info("Token has expired, attempting to refresh.")
			self.refresh()
		return self.settings.token.session
		
	def login(self):
		content = { "username": self.credentials.username, "password": self.credentials.password }
		resp = MangaDexSdk.postJson("auth/login", content)
		result = LoginResponse.fromJson(resp.text)
		self.settings.updateSession(result.token)
	def refresh(self):
		resp = MangaDexSdk.postJson("auth/refresh", { "token": self.settings.token.refresh })
		result = LoginResponse.fromJson(resp.text)
		self.settings.updateSession(result.token)
