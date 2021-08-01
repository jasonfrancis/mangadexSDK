from datetime import datetime
import json
from typing import Any
from .serializable import Serializable, SerializableProperty
from .constants import Constants
from os import path
import sys
import keyring
import getpass
import requests
import jwt

class TokenResponse(Serializable):
	def __init__(self, session:str = None, refresh:str = None, tokensAssigned:float = None):
		self.session = session
		self.refresh = refresh
		self.tokensAssigned = datetime.utcnow().timestamp() if tokensAssigned == None else tokensAssigned
	def tokenExpired(self) -> bool:
		#tokens expire after 15 minutes
		decoded = jwt.decode(self.session, verify=False)
		if("exp" not in decoded):
			return True
		expires = datetime.fromtimestamp(decoded["exp"])
		return datetime.utcnow() >= expires
	def refreshExpired(self) -> bool:
		#refresh tokens expire after 4 hours
		decoded = jwt.decode(self.refresh, verify=False)
		if("exp" not in decoded):
			return True
		expires = datetime.fromtimestamp(decoded["exp"])
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
			print(f"{Constants.SETTINGS_FILE} exists")
			settings = Settings.readFromFile()
			if(not settings.username):
				print("Username not found in settings file.")
				settings.setUsername()
			return settings
		else:
			print(f"{Constants.SETTINGS_FILE} does not exist")
			settings = Settings()
			settings.setUsername()
			return settings
	
	def setUsername(self):
		self.username = input("Enter your MangaDex username: ")
		print(f"Saving username \"{self.username}\" to {Constants.SETTINGS_FILE} ...")
		self.writeToFile()
		print("Done.")

	def updateSession(self, token:TokenResponse):
		self.token = token
		print("Writing updated token to settings")
		self.writeToFile()

	def writeToFile(self):
		settingsJson = self.toJson()
		with open(Constants.SETTINGS_FILE, "w") as writer:
			writer.write(settingsJson)
	
	@staticmethod
	def readFromFile():
		with open(Constants.SETTINGS_FILE, "r") as reader:
			settingsString = reader.read()
			#settingsDict = json.loads(settingsString, object_hook=Settings.dafuq)
			#return Settings(**settingsDict)
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
			print(f"Password for user \"{self.username}\" not found in the keyring.  Enter password.")
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
		url = f"{Constants.BASE_URI}/{path}"
		contentJson = contentJson = json.dumps(content)
		headers = { "Content-Type": "application/json;charset=utf-8" }
		resp = requests.post(url, contentJson, headers=headers)
		if(resp.status_code != 200):
			raise Exception(f"MangaDexApi.postJson to {url} failed. Status code {resp.status_code} - {resp.text}")
		return resp
	@classmethod
	def get(self, path:str):
		url = f"{Constants.BASE_URI}/{path}"
		resp = requests.get(url)
		if(resp.status_code != 200):
			raise Exception(f"MangaDexApi.get from {url} failed. Status code {resp.status_code} - {resp.text}")
		return resp
	def getAuthenticated(self, path:str):
		url = f"{Constants.BASE_URI}/{path}"
		headers = { "Authorization": f"Bearer {self.session.getBearerToken()}"}
		resp = requests.get(url, headers=headers)
		if(resp.status_code != 200):
			raise Exception(f"MangaDexApi.getAuthenticated from {url} failed. Status code {resp.status_code} - {resp.text}")
		return resp



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
			print("Token has expired, attempting to refresh.")
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