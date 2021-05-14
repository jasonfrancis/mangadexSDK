import json
from typing import Any, List

class SerializableProperty:
	def __init__(self, cls:Any, propName:str):
		self.cls = cls
		self.propName = propName

class Serializable:
	def __init__(self, serializableProperties:List[SerializableProperty] = None):
		self.serializableProperties = [] if serializableProperties == None else serializableProperties
	@classmethod
	def fromDict(cls, dict:dict):
		output = None
		if(isinstance(dict, list)):
			output = []
			for item in dict:
				output.append(cls.fromDict(item))
		else:
			output = cls(**dict)
			if(hasattr(output, "serializableProperties")):
				for sp in output.serializableProperties:
					setattr(output, sp.propName, sp.cls.fromDict(getattr(output, sp.propName)))
		return output
	@classmethod
	def fromJson(cls, jsonString:str):
		dict = json.loads(jsonString)
		return cls.fromDict(dict)
	def toJson(self) -> str:
		temp = dict()
		for prop in self.__dict__:
			# never try to serialize SerializableProperties metadata
			if(not prop == "serializableProperties"):
				temp[prop] = self.__dict__[prop]
		return json.dumps(temp, default=lambda o: o.__dict__)
	
	def getAttributeName(self, attr:Any) -> str:
		for prop in self.__dict__:
			if(self.__dict__[prop] == attr):
				return prop
		raise Exception(f"Serializable.getAttributeName - Could not find match for provided attr.")