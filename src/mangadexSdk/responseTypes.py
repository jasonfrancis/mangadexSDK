from .mangaDex import MangaDexSdk
from typing import List
from .serializable import Serializable, SerializableProperty
from enum import Enum

def getFromDict(collection:"dict[str, any]", key:str, default:any = None) -> any:
	return default if not key in collection else collection[key]

class Result(Enum):
	ok = 1
	error = 2

class Relationship(Serializable):
	def __init__(self, id:str, type:str, **kwargs):
		self.id = id
		self.type = type

# At-Home/Server
class AtHomeServer(Serializable):
	def __init__(self, baseUrl:str, **kwargs):
		self.baseUrl = baseUrl
		self.chapterId = None
		super().__init__([])
	def setChapterId(self, value:str):
		self.chapterId = value

# Chapter responses
class ChapterAttributes(Serializable):
	def __init__(self, volume:int, chapter:str, title:str, translatedLanguage:str, hash:str, data:List[str], dataSaver:List[str], publishAt:str, createdAt:str, updatedAt:str, version:int, **kwargs):
		self.volume = volume
		self.chapter = chapter
		self.title = title
		self.translatedLanguage = translatedLanguage
		self.hash = hash
		self.data = data
		self.dataSaver = dataSaver
		self.publishAt = publishAt
		self.createdAt = createdAt
		self.updatedAt = updatedAt
		self.version = version
		self.externalUrl = getFromDict(kwargs, "externalUrl")

class Chapter(Serializable):
	def __init__(self, id:str, type:str, attributes:ChapterAttributes, relationships:List[Relationship], **kwargs):
		self.id = id
		self.type = type
		self.attributes = attributes
		self.relationships = relationships
		# Instructions about how to deserialize attributes
		super().__init__([SerializableProperty(ChapterAttributes, self.getAttributeName(self.attributes)), SerializableProperty(Relationship, self.getAttributeName(self.relationships))])
	def getPageUrls(self, atHomeServer:AtHomeServer) -> dict:
		if atHomeServer.chapterId != self.id:
			raise Exception(f"Chapter.getPageUrls(): Attempting to set page urls for chapter {self.id}, but the provided atHomeServer is for chapter {atHomeServer.chapterId}")
		output = { "data": [], "dataSaver": [] }
		for page in self.attributes.data:
			output["data"].append(f"{atHomeServer.baseUrl}/data/{self.attributes.hash}/{page}")
		for page in self.attributes.dataSaver:
			output["dataSaver"].append(f"{atHomeServer.baseUrl}/data-saver/{self.attributes.hash}/{page}")
		return output

class ChapterResult(Serializable):
	def __init__(self, result:Result, data:Chapter, **kwargs):
		self.result = result
		self.data = data
		# Instrutions to deserialize data and relationships correctly.
		super().__init__([SerializableProperty(Chapter, self.getAttributeName(self.data))])

class FeedResult(Serializable):
	def __init__(self, data:List[Chapter], limit:int, offset:int, total:int, **kwargs):
		self.data = data
		self.limit = limit
		self.offset = offset
		self.total = total
		self.result = getFromDict(kwargs, "result", Result.ok)
		# Instructions about how to deserialize attributes
		super().__init__([SerializableProperty(Chapter, self.getAttributeName(self.data))])

#Tags
class TagAttributes(Serializable):
	def __init__(self, name:dict, version:int, description:dict, group:str, **kwargs):
		self.name = name
		self.version = version
		self.description = description
		self.group = group
		super().__init__([])
class Tag(Serializable):
	def __init__(self, id:str, type:str, attributes:TagAttributes, **kwargs):
		self.id = id
		self.type = type
		self.attributes = attributes
		super().__init__([SerializableProperty(TagAttributes, self.getAttributeName(self.attributes))])

# Manga Responses
class MangaAttributes(Serializable):
	def __init__(self, title:dict, altTitles:List[dict], description:dict, isLocked:bool, links:dict,
				originalLanguage:str, lastVolume:str, lastChapter:str, publicationDemographic:str,
				status:str, year:int, contentRating:str, tags:List[Tag], createdAt:str, updatedAt:str,
				version:int, modNotes:str=None, **kwargs):
		self.title = title
		self.altTitles = altTitles
		self.description = description
		self.isLocked = isLocked
		self.links = links
		self.originalLanguage = originalLanguage
		self.lastVolume = lastVolume
		self.lastChapter = lastChapter
		self.publicationDemographic = publicationDemographic
		self.status = status
		self.year = year
		self.contentRating = contentRating
		self.tags = tags
		self.createdAt = createdAt
		self.updatedAt = updatedAt
		self.modNotes = modNotes
		self.version = version
		super().__init__([SerializableProperty(Tag, self.getAttributeName(self.tags))])

class Manga(Serializable):
	def __init__(self, id:str, type:str, attributes:MangaAttributes, **kwargs):
		self.id = id
		self.type = type
		self.attributes = attributes
		super().__init__([SerializableProperty(MangaAttributes, self.getAttributeName(self.attributes))])

class MangaResult(Serializable):
	def __init__(self, result:Result, data:Manga, relationships:List[Relationship], **kwargs):
		self.result = result
		self.data = data
		self.relationships = relationships
		super().__init__([SerializableProperty(Manga, self.getAttributeName(self.data)), SerializableProperty(Relationship, self.getAttributeName(self.relationships))])

class MangaListResult(Serializable):
	def __init__(self, results:List[MangaResult], limit:int, offset:int, total:int, **kwargs):
		self.results = results
		self.limit = limit
		self.offset = offset
		self.total = total
		# Instructions about how to deserialize attributes
		super().__init__([SerializableProperty(MangaResult, self.getAttributeName(self.results))])

# Authors
class AuthorAttributes(Serializable):
	def __init__(self, name:str, imageUrl:str, biography:List[dict], createdAt:str, updatedAt:str, version:int, **kwargs):
		self.name = name
		self.imageUrl = imageUrl
		self.biography = biography
		self.createdAt = createdAt
		self.updatedAt = updatedAt
		self.version = version
		super().__init__([])
class Author(Serializable):
	def __init__(self, id:str, type:str, attributes:AuthorAttributes, **kwargs):
		self.id = id
		self.type = type
		self.attributes = attributes
		super().__init__([SerializableProperty(AuthorAttributes, self.getAttributeName(self.attributes))])
class AuthorResult(Serializable):
	def __init__(self, result:Result, data:Author, relationships:List[Relationship], **kwargs):
		self.result = result
		self.data = data
		self.relationships = relationships
		super().__init__([SerializableProperty(Author, self.getAttributeName(self.data)), SerializableProperty(Relationship, self.getAttributeName(self.relationships))])

class AuthorListResult(Serializable):
	def __init__(self, results:List[AuthorResult], limit:int, offset:int, total:int, **kwargs):
		self.results = results
		self.limit = limit
		self.offset = offset
		self.total = total
		super().__init__([SerializableProperty(AuthorResult, self.getAttributeName(self.results))])